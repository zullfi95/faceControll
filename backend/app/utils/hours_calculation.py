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
        logger.error(f"Error getting user shift for date {date}: {e}", exc_info=True)
        return None


def get_shift_time_range(shift: models.WorkShift, date: datetime) -> Optional[Tuple[datetime, datetime]]:
    """
    Получение временного диапазона смены для конкретной даты.

    Args:
        shift: Модель смены
        date: Дата для получения расписания

    Returns:
        Кортеж (начало смены, конец смены) или None если смена не работает в этот день
    """
    try:
        # Получаем день недели (0=понедельник, 6=воскресенье)
        weekday = str(date.weekday())

        if not shift.schedule or weekday not in shift.schedule:
            return None

        day_schedule = shift.schedule[weekday]
        if not day_schedule.get("enabled", False):
            return None

        start_time_str = day_schedule.get("start")
        end_time_str = day_schedule.get("end")

        if not start_time_str or not end_time_str:
            return None

        # Парсим время
        start_time = datetime.strptime(start_time_str, "%H:%M").time()
        end_time = datetime.strptime(end_time_str, "%H:%M").time()

        # Создаем datetime объекты
        start_datetime = datetime.combine(date.date(), start_time)
        end_datetime = datetime.combine(date.date(), end_time)

        # Если смена переходит через полночь (время окончания раньше времени начала)
        if end_time < start_time:
            end_datetime = datetime.combine(date.date() + timedelta(days=1), end_time)

        return (start_datetime, end_datetime)

    except Exception as e:
        logger.error(f"Error getting shift time range for date {date}: {e}", exc_info=True)
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
        # Определяем полночь между началом и концом смены
        midnight = datetime.combine(shift_start.date(), time.max).replace(hour=23, minute=59, second=59)

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
                                shift_end: Optional[datetime]) -> Tuple[float, float]:
    """
    Расчет часов в смене и вне смены для списка сессий работы.

    Args:
        sessions: Список кортежей (начало сессии, конец сессии)
        shift_start: Начало смены или None если нет смены
        shift_end: Конец смены или None если нет смены

    Returns:
        Кортеж (общие часы в смене, общие часы вне смены)
    """
    try:
        total_hours_in_shift = 0.0
        total_hours_outside_shift = 0.0

        if not shift_start or not shift_end:
            # Нет активной смены - все часы считаем как вне смены
            for session_start, session_end in sessions:
                session_duration = session_end - session_start
                total_hours_outside_shift += session_duration.total_seconds() / 3600
            return (0.0, total_hours_outside_shift)

        # Для каждой сессии рассчитываем часы в смене и вне смены
        for session_start, session_end in sessions:
            hours_in_shift, hours_outside_shift = split_session_across_midnight(
                session_start, session_end, shift_start, shift_end
            )

            total_hours_in_shift += hours_in_shift
            total_hours_outside_shift += hours_outside_shift

        return (total_hours_in_shift, total_hours_outside_shift)

    except Exception as e:
        logger.error(f"Error calculating hours for sessions: {e}", exc_info=True)
        return (0.0, 0.0)


def parse_sessions_from_events(events: List[models.AttendanceEvent]) -> List[Tuple[datetime, datetime]]:
    """
    Преобразование списка событий в сессии работы (пары вход-выход).

    Логика:
    - Каждый "entry" начинает новую сессию
    - Каждый "exit" закрывает текущую сессию
    - Если есть незакрытая сессия - закрываем текущим временем
    - Никаких автоматических обедов - обед должен быть как обычный выход/вход

    Args:
        events: Список событий, отсортированных по времени

    Returns:
        Список кортежей (начало сессии, конец сессии)
    """
    try:
        # Валидация входных данных
        if not events:
            return []

        # Проверяем корректность timestamp'ов
        for event in events:
            if not hasattr(event, 'timestamp') or not isinstance(event.timestamp, datetime):
                logger.warning(f"Invalid event timestamp: {event}")
                continue

            # Приводим к единому часовому поясу для сравнения
            event_time = event.timestamp
            if event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=BAKU_TZ)

            if event_time > datetime.now(BAKU_TZ):
                logger.warning(f"Event timestamp is in the future: {event.timestamp}")
                continue

        sessions = []
        current_entry = None

        for event in events:
            if event.event_type == "entry":
                # Если есть незакрытая сессия, игнорируем новый вход
                # (сотрудник уже внутри, второй вход - ошибка или повторное сканирование)
                if not current_entry:
                    current_entry = event.timestamp

            elif event.event_type == "exit" and current_entry:
                # Закрываем текущую сессию
                sessions.append((current_entry, event.timestamp))
                current_entry = None

        # Если осталась незакрытая сессия (сотрудник не вышел)
        if current_entry:
            # Для незакрытых сессий используем текущее время (в часовом поясе Baku)
            now = datetime.now(BAKU_TZ)
            # Если событие сегодняшнее, используем текущее время
            if current_entry.date() == now.date():
                sessions.append((current_entry, now))
            # Для прошлых дней НЕ считаем незакрытые сессии -
            # мы не знаем, когда сотрудник фактически ушел

        return sessions

    except Exception as e:
        logger.error(f"Error parsing sessions from events: {e}", exc_info=True)
        return []
