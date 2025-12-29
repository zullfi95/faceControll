"""
Автоматическое закрытие старых незакрытых сессий
Запускается ежедневно:
- В 00:00 проверка и отправка уведомлений
- В 00:01 автоматическое закрытие
"""
import asyncio
import logging
from datetime import datetime, timedelta, time
from sqlalchemy import select
from typing import Optional

logger = logging.getLogger(__name__)


async def check_and_notify_unclosed_sessions(telegram_bot=None):
    """
    Проверяет незакрытые сессии и отправляет уведомления в Telegram.
    Запускается в 00:00.
    """
    from ..database import AsyncSessionLocal
    from .. import models
    
    try:
        async with AsyncSessionLocal() as db:
            logger.info("Checking unclosed sessions for Telegram notifications")
            
            # Получаем всех пользователей
            result = await db.execute(select(models.User))
            users = result.scalars().all()
            
            unclosed_sessions = []
            
            for user in users:
                # Получаем последнее событие пользователя
                result = await db.execute(
                    select(models.AttendanceEvent)
                    .filter(models.AttendanceEvent.user_id == user.id)
                    .order_by(models.AttendanceEvent.timestamp.desc())
                    .limit(1)
                )
                last_event = result.scalar_one_or_none()
                
                if last_event and last_event.event_type == 'entry':
                    # Проверяем, что это вчерашняя сессия
                    now = datetime.now()
                    event_date = last_event.timestamp.replace(tzinfo=None).date()
                    today = now.date()
                    
                    # Если событие было вчера (или раньше) - это незакрытая сессия
                    if event_date < today:
                        # Получаем информацию об устройстве для местоположения
                        device_location = "Неизвестно"
                        if last_event.terminal_ip:
                            device_result = await db.execute(
                                select(models.Device)
                                .filter(models.Device.ip_address == last_event.terminal_ip)
                            )
                            device = device_result.scalar_one_or_none()
                            if device and device.location:
                                device_location = device.location
                            elif device:
                                device_location = device.name
                        
                        unclosed_sessions.append({
                            'user': user.full_name,
                            'user_id': user.id,
                            'entry_time': last_event.timestamp,
                            'location': device_location
                        })
            
            # Отправляем уведомление в Telegram, если есть незакрытые сессии
            if unclosed_sessions:
                logger.warning(f"Found {len(unclosed_sessions)} unclosed sessions")
                
                if telegram_bot:
                    try:
                        message = "⚠️ *НЕЗАКРЫТЫЕ СЕССИИ* ⚠️\n\n"
                        message += f"Обнаружено незакрытых сессий: {len(unclosed_sessions)}\n\n"
                        
                        for session in unclosed_sessions:
                            entry_time_str = session['entry_time'].strftime('%d.%m.%Y %H:%M')
                            message += f"• *{session['user']}*\n"
                            message += f"  Вход: {entry_time_str}\n"
                            message += f"  Местоположение: {session['location']}\n\n"
                        
                        message += "Эти сессии будут автоматически закрыты через 1 минуту."
                        
                        await telegram_bot.send_message(message)
                        logger.info("Telegram notification sent successfully")
                    except Exception as e:
                        logger.error(f"Failed to send Telegram notification: {e}", exc_info=True)
                else:
                    logger.warning("Telegram bot not configured, skipping notification")
            else:
                logger.info("No unclosed sessions found")
                
    except Exception as e:
        logger.error(f"Error in check_and_notify_unclosed_sessions: {e}", exc_info=True)


async def auto_close_old_sessions():
    """
    Автоматически закрывает незакрытые сессии старше 1 дня.
    Закрывает концом дня или через 8 часов после входа.
    """
    from ..database import AsyncSessionLocal
    from .. import models
    
    try:
        async with AsyncSessionLocal() as db:
            logger.info("Starting auto-close of old sessions")
            
            # Получаем всех пользователей
            result = await db.execute(select(models.User))
            users = result.scalars().all()
            
            closed_count = 0
            
            for user in users:
                # Получаем последнее событие пользователя
                result = await db.execute(
                    select(models.AttendanceEvent)
                    .filter(models.AttendanceEvent.user_id == user.id)
                    .order_by(models.AttendanceEvent.timestamp.desc())
                    .limit(1)
                )
                last_event = result.scalar_one_or_none()
                
                if last_event and last_event.event_type == 'entry':
                    days_ago = (datetime.now() - last_event.timestamp.replace(tzinfo=None)).days
                    
                    # Закрываем только если сессия старше 1 дня
                    if days_ago >= 1:
                        entry_hour = last_event.timestamp.hour
                        
                        # Умное определение времени выхода
                        if entry_hour < 12:
                            # Утренний вход - закрываем вечером (18:00)
                            exit_time = last_event.timestamp.replace(
                                hour=18, minute=0, second=0, microsecond=0
                            )
                        else:
                            # Дневной/вечерний вход - закрываем через 8 часов
                            exit_time = last_event.timestamp + timedelta(hours=8)
                            # Но не позже 23:59 того же дня
                            end_of_day = last_event.timestamp.replace(
                                hour=23, minute=59, second=59, microsecond=0
                            )
                            if exit_time > end_of_day:
                                exit_time = end_of_day
                        
                        # Создаем событие выхода
                        exit_event = models.AttendanceEvent(
                            user_id=user.id,
                            employee_no=last_event.employee_no,
                            name=last_event.name,
                            event_type='exit',
                            event_type_description='Auto-closed by system',
                            timestamp=exit_time,
                            terminal_ip=last_event.terminal_ip,
                            card_no=last_event.card_no
                        )
                        
                        db.add(exit_event)
                        closed_count += 1
                        
                        logger.info(
                            f"Auto-closed session for user {user.id} ({user.full_name}). "
                            f"Entry: {last_event.timestamp}, Exit: {exit_time}"
                        )
            
            if closed_count > 0:
                await db.commit()
                logger.info(f"Auto-closed {closed_count} old sessions")
            else:
                logger.info("No old sessions to close")
                
    except Exception as e:
        logger.error(f"Error in auto_close_old_sessions: {e}", exc_info=True)


async def auto_close_sessions_daily(telegram_bot=None):
    """
    Фоновая задача для автоматической проверки и закрытия старых незакрытых сессий.
    
    График работы:
    - 00:00 - проверка и отправка уведомлений в Telegram
    - 00:01 - автоматическое закрытие сессий
    
    Args:
        telegram_bot: Экземпляр TelegramBot для отправки уведомлений
    """
    from ..utils.hours_calculation import BAKU_TZ
    
    while True:
        try:
            now = datetime.now(BAKU_TZ)
            
            # Вычисляем время следующей проверки (00:00)
            next_check = now.replace(hour=0, minute=0, second=0, microsecond=0)
            if now >= next_check:
                next_check += timedelta(days=1)
            
            sleep_seconds = (next_check - now).total_seconds()
            logger.info(f"Scheduled notification check at {next_check}. Sleeping for {sleep_seconds:.1f} seconds.")
            await asyncio.sleep(sleep_seconds)
            
            # Шаг 1: Проверка и уведомление в 00:00
            logger.info("Running unclosed sessions check and notification...")
            await check_and_notify_unclosed_sessions(telegram_bot)
            
            # Ждем 60 секунд до 00:01
            logger.info("Waiting 60 seconds before auto-closing...")
            await asyncio.sleep(60)
            
            # Шаг 2: Автоматическое закрытие в 00:01
            logger.info("Running auto-close of old sessions...")
            await auto_close_old_sessions()
            
            logger.info("Daily auto-close sessions cycle completed")
            
        except asyncio.CancelledError:
            logger.info("Auto-close sessions task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in auto_close_sessions_daily: {e}", exc_info=True)
            # При ошибке ждем 1 час перед следующей попыткой
            await asyncio.sleep(3600)
