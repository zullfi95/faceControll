"""
Фоновый сервис для получения событий с терминалов Hikvision в реальном времени.
"""

import asyncio
import logging
from typing import Dict, Optional, Callable
from sqlalchemy.ext.asyncio import AsyncSession

from .hikvision_client import HikvisionClient
from . import crud, schemas_internal

logger = logging.getLogger(__name__)

# Глобальный словарь для хранения активных подписок
_active_subscriptions: Dict[int, asyncio.Task] = {}


async def process_event_callback(
    event_data: Dict,
    device_id: int,
    get_db_session: Callable
) -> None:
    """
    Callback функция для обработки новых событий из потока.
    
    Args:
        event_data: Данные события от Hikvision
        device_id: ID устройства
        get_db_session: Функция для получения новой сессии БД (генератор)
    """
    try:
        # Получаем новую сессию БД для каждого события
        async for db in get_db_session():
            try:
                # Создаем объект события для сохранения
                event_create = schemas_internal.InternalEventCreate(
                    hikvision_id=event_data.get("employee_no"),
                    event_type=event_data.get("event_type", "unknown"),
                    terminal_ip=event_data.get("terminal_ip", ""),
                    timestamp=event_data.get("timestamp"),
                    employee_no=event_data.get("employee_no"),
                    name=event_data.get("name"),
                    card_no=event_data.get("card_no"),
                    card_reader_id=event_data.get("card_reader_id"),
                    event_type_code=event_data.get("event_type_code"),
                    event_type_description=event_data.get("event_type_description"),
                    remote_host_ip=event_data.get("remote_host_ip")
                )
                
                # Сохраняем событие в БД
                await crud.create_event(db, event_create)
                logger.info(f"Event saved: {event_data.get('event_type_description')} for employee {event_data.get('employee_no')}")
                break
            finally:
                await db.close()
        
    except Exception as e:
        logger.error(f"Error processing event callback: {e}", exc_info=True)


async def start_event_listener(
    device_id: int,
    client: HikvisionClient,
    get_db_session: Callable
) -> None:
    """
    Запуск прослушивания событий для устройства.
    
    Args:
        device_id: ID устройства
        client: Клиент Hikvision
        get_db_session: Функция для получения новой сессии БД (генератор)
    """
    logger.info(f"Starting event listener for device {device_id}")
    
    # Сначала подписываемся на события
    subscribe_result = await client.subscribe_to_events()
    if not subscribe_result.get("success"):
        logger.warning(f"Failed to subscribe to events for device {device_id}: {subscribe_result.get('error')}")
        # Продолжаем работу даже если подписка не удалась
    
    # Создаем callback функцию
    async def event_callback(event: Dict) -> None:
        await process_event_callback(event, device_id, get_db_session)
    
    # Запускаем прослушивание потока событий
    try:
        await client.listen_to_alert_stream(event_callback, timeout=None)
    except Exception as e:
        logger.error(f"Error in event listener for device {device_id}: {e}", exc_info=True)
    finally:
        # Удаляем подписку из активных при завершении
        if device_id in _active_subscriptions:
            del _active_subscriptions[device_id]
        logger.info(f"Event listener stopped for device {device_id}")


async def start_device_subscription(
    device_id: int,
    client: HikvisionClient,
    get_db_session: Callable
) -> bool:
    """
    Запуск подписки на события для устройства.
    
    Args:
        device_id: ID устройства
        client: Клиент Hikvision
        get_db_session: Функция для получения новой сессии БД (генератор)
    
    Returns:
        True если подписка успешно запущена, False иначе
    """
    # Проверяем, не запущена ли уже подписка
    if device_id in _active_subscriptions:
        task = _active_subscriptions[device_id]
        if not task.done():
            logger.info(f"Subscription already active for device {device_id}")
            return True
        else:
            # Задача завершена, удаляем её
            del _active_subscriptions[device_id]
    
    # Запускаем новую задачу
    try:
        task = asyncio.create_task(start_event_listener(device_id, client, get_db_session))
        _active_subscriptions[device_id] = task
        logger.info(f"Started subscription for device {device_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to start subscription for device {device_id}: {e}", exc_info=True)
        return False


async def stop_device_subscription(device_id: int) -> bool:
    """
    Остановка подписки на события для устройства.
    
    Args:
        device_id: ID устройства
    
    Returns:
        True если подписка успешно остановлена, False иначе
    """
    if device_id not in _active_subscriptions:
        logger.info(f"No active subscription for device {device_id}")
        return False
    
    try:
        task = _active_subscriptions[device_id]
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        if device_id in _active_subscriptions:
            del _active_subscriptions[device_id]
        logger.info(f"Stopped subscription for device {device_id}")
        return True
    except KeyError:
        # Подписка уже была удалена
        logger.debug(f"Subscription for device {device_id} already removed")
        return False


def is_subscription_active(device_id: int) -> bool:
    """
    Проверка активности подписки для устройства.
    
    Args:
        device_id: ID устройства
    
    Returns:
        True если подписка активна, False иначе
    """
    if device_id not in _active_subscriptions:
        return False
    
    task = _active_subscriptions[device_id]
    return not task.done()


async def stop_all_subscriptions() -> None:
    """Остановка всех активных подписок."""
    device_ids = list(_active_subscriptions.keys())
    for device_id in device_ids:
        await stop_device_subscription(device_id)
    logger.info("All subscriptions stopped")

