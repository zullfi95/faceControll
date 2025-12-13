"""
Утилиты для определения входа/выхода с одного терминала.

Логика работы:
- Если последнее событие пользователя было "entry" (вход), то следующее событие будет "exit" (выход)
- Если последнее событие пользователя было "exit" (выход), то следующее событие будет "entry" (вход)
- Если у пользователя нет предыдущих событий, первое событие считается "entry" (вход)
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from datetime import datetime
from typing import Optional
from .. import models
import logging

logger = logging.getLogger(__name__)


async def determine_entry_exit(
    db: AsyncSession,
    user_id: Optional[int],
    employee_no: Optional[str],
    terminal_ip: str,
    timestamp: datetime
) -> str:
    """
    Определяет, является ли событие входом или выходом на основе предыдущих событий пользователя.
    
    Args:
        db: Сессия базы данных
        user_id: ID пользователя (если известен)
        employee_no: ID сотрудника из терминала (если user_id неизвестен)
        terminal_ip: IP адрес терминала
        timestamp: Время события
    
    Returns:
        "entry" или "exit"
    """
    try:
        # Ищем последнее событие пользователя на этом терминале
        query = select(models.AttendanceEvent).filter(
            models.AttendanceEvent.terminal_ip == terminal_ip
        ).order_by(desc(models.AttendanceEvent.timestamp))
        
        # Если есть user_id, фильтруем по нему
        if user_id:
            query = query.filter(models.AttendanceEvent.user_id == user_id)
        # Иначе фильтруем по employee_no
        elif employee_no:
            query = query.filter(models.AttendanceEvent.employee_no == employee_no)
        else:
            # Если нет ни user_id, ни employee_no, считаем первым событием (вход)
            logger.info(f"[ENTRY_EXIT] No user_id or employee_no provided, defaulting to 'entry'")
            return "entry"
        
        # Получаем последнее событие
        result = await db.execute(query.limit(1))
        last_event = result.scalars().first()
        
        if not last_event:
            # Нет предыдущих событий - это первое событие (вход)
            logger.info(f"[ENTRY_EXIT] No previous events found for user_id={user_id}, employee_no={employee_no}, defaulting to 'entry'")
            return "entry"
        
        # Определяем тип следующего события на основе последнего
        if last_event.event_type == "entry":
            # Последнее было входом - следующее будет выходом
            logger.info(f"[ENTRY_EXIT] Last event was 'entry' at {last_event.timestamp}, next event is 'exit'")
            return "exit"
        elif last_event.event_type == "exit":
            # Последнее было выходом - следующее будет входом
            logger.info(f"[ENTRY_EXIT] Last event was 'exit' at {last_event.timestamp}, next event is 'entry'")
            return "entry"
        else:
            # Если тип события неизвестен, считаем входом
            logger.warning(f"[ENTRY_EXIT] Last event type '{last_event.event_type}' is unknown, defaulting to 'entry'")
            return "entry"
            
    except Exception as e:
        logger.error(f"[ENTRY_EXIT] Error determining entry/exit: {e}", exc_info=True)
        # В случае ошибки считаем входом
        return "entry"

