"""
Утилиты для расчета часов работы в смене и вне смены.

Логика работы:
- Получение активной смены пользователя на конкретную дату
- Расчет времени смены с учетом дня недели
- Разделение сессий работы на части в смене и вне смены
- Обработка смен через полночь
"""
from datetime import datetime, time, timedelta, timezone
from typing import Optional, List, Dict, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_
import logging

from .. import models

logger = logging.getLogger(__name__)

# Константы
DEFAULT_END_OF_WORKDAY = time(18, 0)  # 18:00 - конец рабочего дня по умолчанию
WORKDAY_START = time.min  # 00:00
WORKDAY_END = time.max    # 23:59:59

# Часовой пояс Baku (UTC+4) для согласованности с фронтендом
BAKU_TZ = timezone(timedelta(hours=4))


async def get_user_shift_for_date(db: AsyncSession, user_id: int, date: datetime) -> Optional[models.WorkShift]:
    """
    Получение активной смены пользователя на конкретную дату.

    Args:
        db: Сессия базы данных
        user_id: ID пользователя
        date: Дата для проверки

    Returns:
        Активная смена или None если нет активной смены
    """
    try:
        # Находим активную привязку пользователя к смене на указанную дату
        result = await db.execute(
            select(models.UserShiftAssignment)
            .join(models.WorkShift)
            .filter(
                and_(
                    models.UserShiftAssignment.user_id == user_id,
                    models.UserShiftAssignment.is_active == True,
                    models.WorkShift.is_active == True,
                    or_(
                        models.UserShiftAssignment.start_date.is_(None),
                        models.UserShiftAssignment.start_date <= date.date()
                    ),
                    or_(
                        models.UserShiftAssignment.end_date.is_(None),
                        models.UserShiftAssignment.end_date >= date.date()
                    )
                )
            )
        )

        assignment = result.scalars().first()
        if assignment:
            return assignment.shift

        return None

    except Exception as e:
        logger.error(f"Error getting user shift for date {date} (user_id={user_id}): {e}", exc_info=True)
        return None


def get_shift_time_range(shift: models.WorkShift, date: datetime) -> Optional[Tuple[datetime, datetime]]:
    """
    Получение временного диапазона смены для конкретной даты.

    Args:
        shift: Модель смены
        date: Дата для получения расписания (должна быть в BAKU_TZ)

    Returns:
        Кортеж (начало смены, конец смены) или None если смена не работает в этот день
    """
    try:
        # Валидация входных данных
        if not shift or not shift.schedule:
            logger.warning(f"get_shift_time_range: Shift {shift.id if shift else 'None'} has no schedule")
            return None

        # Получаем день недели (0=понедельник, 6=воскресенье)
        weekday = str(date.weekday())

        if weekday not in shift.schedule:
            return None

        day_schedule = shift.schedule[weekday]
        if not day_schedule.get("enabled", False):
            return None

        start_time_str = day_schedule.get("start")
        end_time_str = day_schedule.get("end")

        if not start_time_str or not end_time_str:
            logger.warning(
                f"get_shift_time_range: Shift {shift.id} has incomplete schedule for weekday {weekday}. "
                f"Start={start_time_str}, End={end_time_str}"
            )
            return None

        # Парсим время
        try:
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
            end_time = datetime.strptime(end_time_str, "%H:%M").time()
        except ValueError as e:
            logger.error(
                f"get_shift_time_range: Invalid time format in shift {shift.id} schedule. "
                f"Start='{start_time_str}', End='{end_time_str}': {e}"
            )
            return None

        # Получаем часовой пояс из date или используем BAKU_TZ по умолчанию
        tz = date.tzinfo if date.tzinfo else BAKU_TZ
        
        # Создаем datetime объекты с правильным часовым поясом
        start_datetime = datetime.combine(date.date(), start_time, tzinfo=tz)
        end_datetime = datetime.combine(date.date(), end_time, tzinfo=tz)

        # Если смена переходит через полночь (время окончания раньше времени начала)
        if end_time < start_time:
            end_datetime = datetime.combine(date.date() + timedelta(days=1), end_time, tzinfo=tz)

        return (start_datetime, end_datetime)

    except Exception as e:
        logger.error(
            f"Error getting shift time range for shift_id={shift.id if shift else 'None'} "
            f"on date {date}: {e}", exc_info=True
        )
        return None


def split_session_by_shift(session_start: datetime, session_end: datetime,
                          shift_start: datetime, shift_end: datetime) -> Tuple[float, float]:
    """
    Разделение сессии работы на части в смене и вне смены.

    Args:
        session_start: Начало сессии работы
        session_end: Конец сессии работы
        shift_start: Начало смены
        shift_end: Конец смены

    Returns:
        Кортеж (часы в смене, часы вне смены)
    """
    try:
        # Нормализуем часовые пояса - используем часовой пояс из shift_start или BAKU_TZ
        tz = shift_start.tzinfo if shift_start.tzinfo else BAKU_TZ
        
        # Убеждаемся, что все datetime объекты имеют одинаковый часовой пояс
        if session_start.tzinfo is None:
            session_start = session_start.replace(tzinfo=tz)
        elif session_start.tzinfo != tz:
            session_start = session_start.astimezone(tz)
            
        if session_end.tzinfo is None:
            session_end = session_end.replace(tzinfo=tz)
        elif session_end.tzinfo != tz:
            session_end = session_end.astimezone(tz)
            
        if shift_start.tzinfo is None:
            shift_start = shift_start.replace(tzinfo=tz)
        elif shift_start.tzinfo != tz:
            shift_start = shift_start.astimezone(tz)
            
        if shift_end.tzinfo is None:
            shift_end = shift_end.replace(tzinfo=tz)
        elif shift_end.tzinfo != tz:
            shift_end = shift_end.astimezone(tz)

        # Валидация входных данных
        if session_start >= session_end:
            logger.warning(
                f"split_session_by_shift: Invalid session duration. "
                f"Start={session_start} >= End={session_end}"
            )
            return (0.0, 0.0)

        if shift_start >= shift_end:
            logger.warning(
                f"split_session_by_shift: Invalid shift range. "
                f"Start={shift_start} >= End={shift_end}"
            )
            # Если смена некорректна, считаем всю сессию вне смены
            session_duration = session_end - session_start
            return (0.0, session_duration.total_seconds() / 3600)

        # Находим пересечение сессии и смены
        overlap_start = max(session_start, shift_start)
        overlap_end = min(session_end, shift_end)

        hours_in_shift = 0.0
        hours_outside_shift = 0.0

        if overlap_start < overlap_end:
            # Есть пересечение - рассчитываем часы в смене
            overlap_duration = overlap_end - overlap_start
            hours_in_shift = overlap_duration.total_seconds() / 3600
        else:
            # Нет пересечения - вся сессия вне смены
            hours_in_shift = 0.0

        # Общее время сессии
        session_duration = session_end - session_start
        total_hours = session_duration.total_seconds() / 3600

        # Остальное время - вне смены
        hours_outside_shift = total_hours - hours_in_shift

        return (hours_in_shift, hours_outside_shift)

    except Exception as e:
        logger.error(f"Error splitting session by shift: {e}", exc_info=True)
        return (0.0, 0.0)


def split_session_across_midnight(session_start: datetime, session_end: datetime,
                                 shift_start: datetime, shift_end: datetime) -> Tuple[float, float]:
    """
    Разделение сессии работы для смены, переходящей через полночь.

    Args:
        session_start: Начало сессии работы
        session_end: Конец сессии работы
        shift_start: Начало смены (может быть в предыдущий день)
        shift_end: Конец смены (может быть в следующий день)

    Returns:
        Кортеж (часы в смене, часы вне смены)
    """
    try:
        # Нормализуем часовые пояса - определяем базовый часовой пояс
        # Используем часовой пояс из shift_start, если есть, иначе BAKU_TZ
        base_tz = shift_start.tzinfo if shift_start.tzinfo is not None else BAKU_TZ
        
        # Убеждаемся, что все datetime объекты имеют одинаковый часовой пояс
        # Просто конвертируем все в base_tz, если они не None
        if session_start.tzinfo is None:
            session_start = session_start.replace(tzinfo=base_tz)
        else:
            session_start = session_start.astimezone(base_tz)
            
        if session_end.tzinfo is None:
            session_end = session_end.replace(tzinfo=base_tz)
        else:
            session_end = session_end.astimezone(base_tz)
            
        if shift_start.tzinfo is None:
            shift_start = shift_start.replace(tzinfo=base_tz)
        else:
            shift_start = shift_start.astimezone(base_tz)
            
        if shift_end.tzinfo is None:
            shift_end = shift_end.replace(tzinfo=base_tz)
        else:
            shift_end = shift_end.astimezone(base_tz)

        # Определяем полночь между началом и концом смены (с правильным часовым поясом)
        # Используем date() от нормализованного shift_start
        shift_date = shift_start.date()
        midnight = datetime.combine(shift_date, time(23, 59, 59), tzinfo=base_tz)

        if shift_start <= midnight < shift_end:
            # Смена переходит через полночь
            # Разделяем на две части: до полуночи и после полуночи

            # Часть до полуночи
            shift_end_part1 = min(shift_end, midnight + timedelta(seconds=1))
            hours_part1_in, hours_part1_out = split_session_by_shift(
                session_start, session_end, shift_start, shift_end_part1
            )

            # Часть после полуночи
            shift_start_part2 = max(shift_start, midnight + timedelta(seconds=1))
            hours_part2_in, hours_part2_out = split_session_by_shift(
                session_start, session_end, shift_start_part2, shift_end
            )

            return (hours_part1_in + hours_part2_in, hours_part1_out + hours_part2_out)
        else:
            # Обычная смена в пределах одного дня
            return split_session_by_shift(session_start, session_end, shift_start, shift_end)

    except Exception as e:
        logger.error(f"Error splitting session across midnight: {e}", exc_info=True)
        return (0.0, 0.0)


def calculate_hours_for_sessions(sessions: List[Tuple[datetime, datetime]],
                                shift_start: Optional[datetime],
                                shift_end: Optional[datetime],
                                user_id: Optional[int] = None) -> Tuple[float, float]:
    """
    Расчет часов в смене и вне смены для списка сессий работы.

    Args:
        sessions: Список кортежей (начало сессии, конец сессии)
        shift_start: Начало смены или None если нет смены
        shift_end: Конец смены или None если нет смены
        user_id: ID пользователя для логирования (опционально)

    Returns:
        Кортеж (общие часы в смене, общие часы вне смены)
    """
    try:
        # Валидация входных данных
        if not sessions:
            return (0.0, 0.0)

        # Валидация сессий
        valid_sessions = []
        for idx, (session_start, session_end) in enumerate(sessions):
            if not isinstance(session_start, datetime) or not isinstance(session_end, datetime):
                logger.warning(
                    f"calculate_hours_for_sessions: Invalid session at index {idx} for user_id={user_id}. "
                    f"Start={session_start}, End={session_end}"
                )
                continue

            if session_start >= session_end:
                logger.warning(
                    f"calculate_hours_for_sessions: Invalid session duration at index {idx} for user_id={user_id}. "
                    f"Start={session_start} >= End={session_end}"
                )
                continue

            valid_sessions.append((session_start, session_end))

        if not valid_sessions:
            logger.warning(f"calculate_hours_for_sessions: No valid sessions after validation for user_id={user_id}")
            return (0.0, 0.0)

        total_hours_in_shift = 0.0
        total_hours_outside_shift = 0.0

        if not shift_start or not shift_end:
            # Нет активной смены - все часы считаем как вне смены
            for session_start, session_end in valid_sessions:
                session_duration = session_end - session_start
                hours = session_duration.total_seconds() / 3600
                total_hours_outside_shift += hours
            
            logger.info(
                f"calculate_hours_for_sessions: Completed for user_id={user_id}. "
                f"Total hours outside shift: {total_hours_outside_shift:.2f}"
            )
            return (0.0, total_hours_outside_shift)

        # Валидация диапазона смены
        if shift_start >= shift_end:
            logger.warning(
                f"calculate_hours_for_sessions: Invalid shift range for user_id={user_id}. "
                f"Shift start={shift_start} >= shift end={shift_end}"
            )
            # Если смена некорректна, считаем все часы вне смены
            for session_start, session_end in valid_sessions:
                session_duration = session_end - session_start
                total_hours_outside_shift += session_duration.total_seconds() / 3600
            return (0.0, total_hours_outside_shift)

        # Для каждой сессии рассчитываем часы в смене и вне смены
        for idx, (session_start, session_end) in enumerate(valid_sessions):
            hours_in_shift, hours_outside_shift = split_session_across_midnight(
                session_start, session_end, shift_start, shift_end
            )

            total_hours_in_shift += hours_in_shift
            total_hours_outside_shift += hours_outside_shift

        logger.info(
            f"calculate_hours_for_sessions: Completed for user_id={user_id}. "
            f"Total: In shift={total_hours_in_shift:.2f}h, Outside shift={total_hours_outside_shift:.2f}h, "
            f"Total worked={total_hours_in_shift + total_hours_outside_shift:.2f}h"
        )

        return (total_hours_in_shift, total_hours_outside_shift)

    except Exception as e:
        logger.error(f"Error calculating hours for sessions (user_id={user_id}): {e}", exc_info=True)
        return (0.0, 0.0)


def parse_sessions_from_events(events: List[models.AttendanceEvent], report_date: Optional[datetime] = None) -> List[Tuple[datetime, datetime]]:
    """
    Преобразование списка событий в сессии работы (пары вход-выход).

    Логика:
    - Каждый "entry" начинает новую сессию
    - Каждый "exit" закрывает текущую сессию
    - Если есть незакрытая сессия - закрываем в зависимости от даты отчета
    - Обрабатывает некорректные последовательности (несколько entry подряд, exit без entry)
    - Никаких автоматических обедов - обед должен быть как обычный выход/вход

    Args:
        events: Список событий, отсортированных по времени
        report_date: Дата отчета для определения обработки незакрытых сессий (опционально)

    Returns:
        Список кортежей (начало сессии, конец сессии)
    """
    try:
        # Валидация входных данных
        if not events:
            return []

        user_id = events[0].user_id if events else None

        # Валидация и нормализация событий
        valid_events = []
        for idx, event in enumerate(events):
            # Проверка наличия timestamp
            if not hasattr(event, 'timestamp') or not isinstance(event.timestamp, datetime):
                logger.warning(f"parse_sessions_from_events: Invalid event timestamp at index {idx}: {event}")
                continue

            # Проверка типа события
            if event.event_type not in ("entry", "exit"):
                logger.warning(f"parse_sessions_from_events: Unknown event_type '{event.event_type}' at index {idx}, skipping")
                continue

            # Приводим к единому часовому поясу для сравнения
            event_time = event.timestamp
            if event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=BAKU_TZ)
                # Обновляем timestamp события для дальнейшей обработки
                event.timestamp = event_time

            # Проверка на будущие события
            now = datetime.now(BAKU_TZ)
            if event_time > now:
                logger.warning(f"parse_sessions_from_events: Event timestamp is in the future: {event.timestamp}, skipping")
                continue

            valid_events.append(event)

        if not valid_events:
            logger.warning(f"parse_sessions_from_events: No valid events after validation for user_id={user_id}")
            return []


        sessions = []
        current_entry = None
        unclosed_entries = []  # Для отслеживания незакрытых входов
        orphan_exits = []  # Для отслеживания выходов без входа

        # Обработка событий
        for idx, event in enumerate(valid_events):
            event_time = event.timestamp

            if event.event_type == "entry":
                if current_entry:
                    # Есть незакрытая сессия - логируем предупреждение
                    logger.warning(
                        f"parse_sessions_from_events: Multiple entry events without exit. "
                        f"User_id={user_id}, Previous entry={current_entry}, New entry={event_time}. "
                        f"Closing previous session with new entry time."
                    )
                    # Закрываем предыдущую сессию временем нового входа
                    # Это обрабатывает случай, когда сотрудник забыл выйти и снова вошел
                    sessions.append((current_entry, event_time))
                    unclosed_entries.append((current_entry, event_time))
                
                current_entry = event_time

            elif event.event_type == "exit":
                if current_entry:
                    # Нормальное закрытие сессии
                    session_duration = (event_time - current_entry).total_seconds() / 3600
                    if session_duration < 0:
                        logger.warning(
                            f"parse_sessions_from_events: Negative session duration detected. "
                            f"User_id={user_id}, Entry={current_entry}, Exit={event_time}"
                        )
                    else:
                        sessions.append((current_entry, event_time))
                    current_entry = None
                else:
                    # Выход без входа - логируем и игнорируем
                    orphan_exits.append(event_time)
                    logger.warning(
                        f"parse_sessions_from_events: Exit event without corresponding entry. "
                        f"User_id={user_id}, Exit time={event_time}, index={idx}"
                    )

        # Обработка незакрытых сессий
        if current_entry:
            now = datetime.now(BAKU_TZ)
            current_entry_date = current_entry.date()
            now_date = now.date()
            
            # Определяем дату отчета, если не указана
            if report_date:
                report_date_obj = report_date if isinstance(report_date, datetime) else datetime.combine(report_date, time.min, tzinfo=BAKU_TZ)
                report_date_only = report_date_obj.date()
            else:
                # Если не указана дата отчета, используем дату последнего события
                report_date_only = valid_events[-1].timestamp.date() if valid_events else now_date

            # Для незакрытых сессий используем разную логику в зависимости от даты
            if current_entry_date == now_date:
                # Сегодняшняя незакрытая сессия - используем текущее время
                sessions.append((current_entry, now))
                logger.info(
                    f"parse_sessions_from_events: Unclosed session for today. "
                    f"User_id={user_id}, Entry={current_entry}, Using current time={now}"
                )
            elif current_entry_date == report_date_only:
                # Незакрытая сессия в день отчета (но не сегодня) - закрываем концом дня
                end_of_day = datetime.combine(current_entry_date, time.max, tzinfo=BAKU_TZ).replace(
                    hour=23, minute=59, second=59
                )
                sessions.append((current_entry, end_of_day))
                logger.info(
                    f"parse_sessions_from_events: Unclosed session for report date. "
                    f"User_id={user_id}, Entry={current_entry}, Closing at end of day={end_of_day}"
                )
            else:
                # Незакрытая сессия в прошлом (не в день отчета) - не учитываем
                logger.warning(
                    f"parse_sessions_from_events: Unclosed session in past (not report date). "
                    f"User_id={user_id}, Entry={current_entry}, Report date={report_date_only}, "
                    f"Not counting hours (unknown exit time)"
                )

        # Логирование итоговой статистики
        if orphan_exits:
            logger.warning(
                f"parse_sessions_from_events: Found {len(orphan_exits)} orphan exit events for user_id={user_id}"
            )
        
        logger.info(
            f"parse_sessions_from_events: Completed. User_id={user_id}, "
            f"Total events={len(valid_events)}, Sessions parsed={len(sessions)}, "
            f"Unclosed entries handled={len(unclosed_entries)}, Orphan exits={len(orphan_exits)}"
        )

        return sessions

    except Exception as e:
        logger.error(f"Error parsing sessions from events: {e}", exc_info=True)
        return []
