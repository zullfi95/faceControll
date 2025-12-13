"""
Сервис для генерации ежедневных отчетов по посещаемости.

Функциональность:
- Генерация отчета за предыдущий день
- Поиск незакрытых сессий (сотрудники, которые не вышли)
- Интеграция с телеграм ботом для отправки отчетов
"""
import logging
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_

from .. import models
from .hours_calculation import (
    get_user_shift_for_date,
    get_shift_time_range,
    parse_sessions_from_events,
    calculate_hours_for_sessions
)
from .telegram_bot import TelegramBot, DailyReportFormatter

logger = logging.getLogger(__name__)


class DailyReportService:
    """Сервис для генерации и отправки ежедневных отчетов."""

    def __init__(self, telegram_bot: Optional[TelegramBot] = None):
        """
        Инициализация сервиса.

        Args:
            telegram_bot: Экземпляр телеграм бота для отправки отчетов
        """
        self.telegram_bot = telegram_bot

    async def generate_daily_report(self, db: AsyncSession, report_date: date) -> Tuple[List[Dict], List[Dict]]:
        """
        Генерация отчета за указанную дату.

        Args:
            db: Сессия базы данных
            report_date: Дата для генерации отчета

        Returns:
            Кортеж (список сотрудников, список незакрытых сессий)
        """
        try:
            logger.info(f"Generating daily report for {report_date}")

            # Получаем все события за день
            start_datetime = datetime.combine(report_date, time.min)
            end_datetime = datetime.combine(report_date, time.max)

            events = await self._get_events_for_day(db, start_datetime, end_datetime)
            logger.info(f"Found {len(events)} events for {report_date}")

            # Группируем события по пользователям
            user_events = self._group_events_by_user(events)

            # Генерируем отчет по сотрудникам
            employees_report = await self._generate_employees_report(db, user_events, report_date)

            # Находим незакрытые сессии
            unclosed_sessions = await self._find_unclosed_sessions(db, report_date)

            logger.info(f"Report generated: {len(employees_report)} employees, {len(unclosed_sessions)} unclosed sessions")

            return employees_report, unclosed_sessions

        except Exception as e:
            logger.error(f"Error generating daily report: {e}", exc_info=True)
            return [], []

    async def send_daily_report(self, db: AsyncSession, report_date: Optional[date] = None) -> bool:
        """
        Генерация и отправка ежедневного отчета.

        Args:
            db: Сессия базы данных
            report_date: Дата отчета (по умолчанию - вчера)

        Returns:
            True если отчет отправлен успешно
        """
        if not self.telegram_bot:
            logger.warning("Telegram bot not configured, skipping report sending")
            return False

        # Если дата не указана, берем вчерашний день
        if report_date is None:
            report_date = date.today() - timedelta(days=1)

        try:
            # Генерируем отчет
            employees_report, unclosed_sessions = await self.generate_daily_report(db, report_date)

            # Форматируем сообщение
            message = DailyReportFormatter.format_daily_report(
                report_date, employees_report, unclosed_sessions
            )

            # Отправляем в телеграм
            success = await self.telegram_bot.send_message(message)

            if success:
                logger.info(f"Daily report sent successfully for {report_date}")
            else:
                logger.error(f"Failed to send daily report for {report_date}")

            return success

        except Exception as e:
            logger.error(f"Error sending daily report: {e}", exc_info=True)
            return False

    async def send_unclosed_sessions_alert(self, db: AsyncSession) -> bool:
        """
        Отправка уведомления о незакрытых сессиях на текущий момент.

        Args:
            db: Сессия базы данных

        Returns:
            True если уведомление отправлено успешно
        """
        if not self.telegram_bot:
            logger.warning("Telegram bot not configured, skipping alert")
            return False

        try:
            unclosed_sessions = await self._find_unclosed_sessions(db, date.today())

            if not unclosed_sessions:
                logger.info("No unclosed sessions found, skipping alert")
                return True

            # Форматируем уведомление
            message = DailyReportFormatter.format_unclosed_sessions_alert(unclosed_sessions)

            # Отправляем в телеграм
            success = await self.telegram_bot.send_message(message)

            if success:
                logger.info(f"Unclosed sessions alert sent: {len(unclosed_sessions)} sessions")
            else:
                logger.error("Failed to send unclosed sessions alert")

            return success

        except Exception as e:
            logger.error(f"Error sending unclosed sessions alert: {e}", exc_info=True)
            return False

    async def _get_events_for_day(self, db: AsyncSession, start_datetime: datetime, end_datetime: datetime) -> List[models.AttendanceEvent]:
        """Получение всех событий за день с JOIN к пользователям."""
        from sqlalchemy.orm import joinedload

        result = await db.execute(
            select(models.AttendanceEvent)
            .options(joinedload(models.AttendanceEvent.user))
            .filter(models.AttendanceEvent.timestamp >= start_datetime)
            .filter(models.AttendanceEvent.timestamp <= end_datetime)
            .order_by(models.AttendanceEvent.user_id, models.AttendanceEvent.timestamp.asc())
        )

        return result.unique().scalars().all()

    def _group_events_by_user(self, events: List[models.AttendanceEvent]) -> Dict[int, List[models.AttendanceEvent]]:
        """Группировка событий по пользователям."""
        user_events = {}

        for event in events:
            user_id = event.user_id
            if user_id not in user_events:
                user_events[user_id] = []
            user_events[user_id].append(event)

        return user_events

    async def _generate_employees_report(self, db: AsyncSession, user_events: Dict[int, List[models.AttendanceEvent]], report_date: date) -> List[Dict]:
        """Генерация отчета по сотрудникам."""
        employees_report = []

        for user_id, events in user_events.items():
            try:
                # Получаем информацию о пользователе
                user = events[0].user if events and events[0].user else None
                if not user:
                    continue

                # Парсим сессии
                sessions = parse_sessions_from_events(events)

                # Получаем активную смену пользователя на эту дату
                user_shift = None
                shift_time_range = None

                if user_id:
                    report_datetime = datetime.combine(report_date, time.min)
                    user_shift = await get_user_shift_for_date(db, user_id, report_datetime)
                    if user_shift:
                        shift_time_range = get_shift_time_range(user_shift, report_datetime)

                # Рассчитываем часы в смене и вне смены
                if shift_time_range:
                    shift_start, shift_end = shift_time_range
                    hours_in_shift, hours_outside_shift = calculate_hours_for_sessions(sessions, shift_start, shift_end)
                else:
                    # Нет активной смены - все часы считаем как вне смены
                    hours_in_shift, hours_outside_shift = calculate_hours_for_sessions(sessions, None, None)

                # Общее время работы
                hours_worked = hours_in_shift + hours_outside_shift

                # Определяем статус и время входа/выхода
                entry_time = None
                exit_time = None
                status = "Absent"

                if sessions:
                    # Берем первую сессию для определения времени входа
                    entry_time = sessions[0][0]
                    # Берем последнюю сессию для определения времени выхода
                    exit_time = sessions[-1][1]

                    if hours_worked > 0:
                        if exit_time and exit_time.date() == datetime.now().date():
                            # Есть незакрытая сессия сегодня
                            status = "Present (no exit)"
                        else:
                            status = "Present"
                elif events:
                    # Есть события, но нет полных сессий
                    entry_time = events[0].timestamp
                    status = "Present (no exit)"

                employees_report.append({
                    "user_id": user_id,
                    "user": user.full_name or f"User {user.hikvision_id}",
                    "hikvision_id": user.hikvision_id,
                    "entry_time": entry_time.isoformat() if entry_time else None,
                    "exit_time": exit_time.isoformat() if exit_time else None,
                    "hours_worked": round(hours_worked, 2),
                    "hours_in_shift": round(hours_in_shift, 2),
                    "hours_outside_shift": round(hours_outside_shift, 2),
                    "status": status
                })

            except Exception as e:
                logger.error(f"Error processing user {user_id}: {e}", exc_info=True)
                continue

        # Сортируем по имени пользователя
        employees_report.sort(key=lambda x: x["user"])

        return employees_report

    async def _find_unclosed_sessions(self, db: AsyncSession, target_date: date) -> List[Dict]:
        """
        Поиск незакрытых сессий (сотрудники, которые вошли но не вышли).

        Args:
            db: Сессия базы данных
            target_date: Дата для проверки (обычно сегодня)

        Returns:
            Список незакрытых сессий
        """
        try:
            unclosed_sessions = []

            # Получаем все события за сегодня
            start_datetime = datetime.combine(target_date, time.min)
            end_datetime = datetime.combine(target_date, time.max)

            events = await self._get_events_for_day(db, start_datetime, end_datetime)

            # Группируем по пользователям и ищем незакрытые сессии
            user_events = self._group_events_by_user(events)

            for user_id, user_events_list in user_events.items():
                try:
                    # Парсим сессии для пользователя
                    sessions = parse_sessions_from_events(user_events_list)

                    # Если есть незакрытые сессии (последняя сессия без выхода)
                    if sessions and len(sessions) > 0:
                        last_session_start, last_session_end = sessions[-1]

                        # Проверяем, закрыта ли последняя сессия сегодня
                        # Если время выхода совпадает с текущим временем, значит сессия незакрыта
                        now = datetime.now()
                        if last_session_end.date() == now.date() and abs((now - last_session_end).total_seconds()) < 300:  # 5 минут погрешность
                            user = user_events_list[0].user
                            if user:
                                hours_since_entry = (now - last_session_start).total_seconds() / 3600

                                unclosed_sessions.append({
                                    "user_id": user_id,
                                    "user": user.full_name or f"User {user.hikvision_id}",
                                    "hikvision_id": user.hikvision_id,
                                    "entry_time": last_session_start.strftime("%H:%M"),
                                    "hours_since_entry": round(hours_since_entry, 1)
                                })

                except Exception as e:
                    logger.error(f"Error checking unclosed sessions for user {user_id}: {e}", exc_info=True)
                    continue

            logger.info(f"Found {len(unclosed_sessions)} unclosed sessions")
            return unclosed_sessions

        except Exception as e:
            logger.error(f"Error finding unclosed sessions: {e}", exc_info=True)
            return []
