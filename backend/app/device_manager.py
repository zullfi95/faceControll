"""
Device Manager - централизованное управление всеми терминалами Hikvision.

Функционал:
- Кеширование HikvisionClient для каждого устройства
- Автозапуск подписок на события от всех активных терминалов
- Мониторинг статуса подключения
- Автоматическое переподключение при обрывах связи
"""

import asyncio
import logging
from typing import Dict, Optional, List
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from .hikvision_client import HikvisionClient
from .utils.crypto import decrypt_password
from . import models, crud
from . import event_service
from .database import get_db_session

logger = logging.getLogger(__name__)


class DeviceManager:
    """Менеджер для управления всеми устройствами Hikvision."""
    
    def __init__(self):
        self._clients: Dict[int, HikvisionClient] = {}  # device_id -> client
        self._devices: Dict[int, models.Device] = {}     # device_id -> device model
        self._subscription_active: Dict[int, bool] = {}  # device_id -> is_active
        self._last_event: Dict[int, Optional[datetime]] = {}  # device_id -> last_event_time
        self._initialized = False
    
    async def initialize(self, db: AsyncSession):
        """
        Инициализация Device Manager.
        Загружает все устройства из БД и создает клиенты.
        """
        try:
            devices = await crud.get_all_devices(db)
            
            for device in devices:
                self._devices[device.id] = device
                self._subscription_active[device.id] = False
                self._last_event[device.id] = None
                
                if device.is_active:
                    # Создаем клиент только для активных устройств
                    try:
                        client = self._create_client(device)
                        self._clients[device.id] = client
                        logger.info(f"✓ Created client for device {device.id} ({device.name})")
                    except Exception as e:
                        logger.error(f"✗ Failed to create client for device {device.id}: {e}")
            
            self._initialized = True
            logger.info(f"Device Manager initialized with {len(self._clients)} active devices")
            
        except Exception as e:
            logger.error(f"Error initializing Device Manager: {e}", exc_info=True)
            raise
    
    def _create_client(self, device: models.Device) -> HikvisionClient:
        """Создание HikvisionClient для устройства."""
        try:
            password = decrypt_password(device.password_encrypted)
            client = HikvisionClient(
                ip=device.ip_address,
                username=device.username,
                password=password,
                use_https=True
            )
            return client
        except Exception as e:
            logger.error(f"Error creating client for device {device.id}: {e}")
            raise
    
    async def get_client(self, device_id: int, db: Optional[AsyncSession] = None) -> Optional[HikvisionClient]:
        """
        Получение HikvisionClient для устройства.
        Если клиента нет в кеше, создает его.
        """
        # Проверяем кеш
        if device_id in self._clients:
            return self._clients[device_id]
        
        # Если нет в кеше, пытаемся создать
        if db:
            device = await crud.get_device_by_id(db, device_id)
            if device and device.is_active:
                try:
                    client = self._create_client(device)
                    self._clients[device_id] = client
                    self._devices[device_id] = device
                    return client
                except Exception as e:
                    logger.error(f"Failed to create client for device {device_id}: {e}")
                    return None
        
        return None
    
    async def start_subscription(self, device_id: int) -> bool:
        """
        Запуск подписки на события для устройства.
        
        Returns:
            True если подписка успешно запущена, False иначе
        """
        try:
            # Проверяем, не запущена ли уже подписка
            if self._subscription_active.get(device_id, False):
                if event_service.is_subscription_active(device_id):
                    logger.debug(f"Subscription already active for device {device_id}")
                    return True
            
            # Получаем клиент
            client = self._clients.get(device_id)
            if not client:
                logger.error(f"No client found for device {device_id}")
                return False
            
            # Запускаем подписку через event_service
            success = await event_service.start_device_subscription(
                device_id=device_id,
                client=client,
                get_db_session=get_db_session
            )
            
            if success:
                self._subscription_active[device_id] = True
                logger.info(f"✓ Started subscription for device {device_id}")
            else:
                logger.warning(f"✗ Failed to start subscription for device {device_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error starting subscription for device {device_id}: {e}", exc_info=True)
            return False
    
    async def stop_subscription(self, device_id: int) -> bool:
        """
        Остановка подписки на события для устройства.
        
        Returns:
            True если подписка успешно остановлена, False иначе
        """
        try:
            success = await event_service.stop_device_subscription(device_id)
            if success:
                self._subscription_active[device_id] = False
                logger.info(f"✓ Stopped subscription for device {device_id}")
            return success
        except Exception as e:
            logger.error(f"Error stopping subscription for device {device_id}: {e}")
            return False
    
    async def reconnect_device(self, device_id: int, db: AsyncSession) -> bool:
        """
        Переподключение к устройству.
        Останавливает старую подписку, создает новый клиент и запускает подписку снова.
        """
        try:
            logger.info(f"Reconnecting to device {device_id}...")
            
            # Останавливаем старую подписку
            await self.stop_subscription(device_id)
            
            # Закрываем старый клиент
            old_client = self._clients.get(device_id)
            if old_client:
                try:
                    await old_client.close()
                except Exception:
                    pass
                del self._clients[device_id]
            
            # Создаем новый клиент
            device = await crud.get_device_by_id(db, device_id)
            if not device or not device.is_active:
                logger.warning(f"Device {device_id} not found or inactive")
                return False
            
            client = self._create_client(device)
            self._clients[device_id] = client
            self._devices[device_id] = device
            
            # Проверяем подключение
            connected, error = await client.check_connection()
            if not connected:
                logger.error(f"Failed to connect to device {device_id}: {error}")
                return False
            
            # Запускаем подписку
            success = await self.start_subscription(device_id)
            if success:
                logger.info(f"✓ Successfully reconnected to device {device_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error reconnecting to device {device_id}: {e}", exc_info=True)
            return False
    
    async def get_device_status(self, device_id: int) -> Dict:
        """
        Получение статуса устройства.
        
        Returns:
            Словарь с информацией о статусе
        """
        device = self._devices.get(device_id)
        if not device:
            return {
                "device_id": device_id,
                "status": "not_found",
                "connection_status": "unknown",
                "subscription_active": False
            }
        
        client = self._clients.get(device_id)
        connection_status = "disconnected"
        error_message = None
        
        if client:
            try:
                connected, error = await client.check_connection()
                connection_status = "connected" if connected else "error"
                error_message = error if not connected else None
            except Exception as e:
                connection_status = "error"
                error_message = str(e)
        
        return {
            "device_id": device_id,
            "name": device.name,
            "device_type": device.device_type,
            "location": device.location,
            "is_active": device.is_active,
            "connection_status": connection_status,
            "subscription_active": self._subscription_active.get(device_id, False),
            "last_event_at": self._last_event.get(device_id),
            "error_message": error_message
        }
    
    async def get_all_statuses(self) -> List[Dict]:
        """Получение статусов всех устройств."""
        statuses = []
        for device_id in self._devices.keys():
            status = await self.get_device_status(device_id)
            statuses.append(status)
        return statuses
    
    async def stop_all(self):
        """Остановка всех подписок и закрытие всех клиентов."""
        logger.info("Stopping all device subscriptions...")
        
        # Останавливаем все подписки
        await event_service.stop_all_subscriptions()
        
        # Закрываем всех клиентов
        for device_id, client in self._clients.items():
            try:
                await client.close()
                logger.debug(f"Closed client for device {device_id}")
            except Exception as e:
                logger.error(f"Error closing client for device {device_id}: {e}")
        
        self._clients.clear()
        self._subscription_active.clear()
        logger.info("All device connections closed")
    
    def update_last_event(self, device_id: int):
        """Обновление времени последнего события для устройства."""
        self._last_event[device_id] = datetime.now()
    
    def is_initialized(self) -> bool:
        """Проверка, инициализирован ли менеджер."""
        return self._initialized


# Глобальный экземпляр Device Manager
device_manager = DeviceManager()

