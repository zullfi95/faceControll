"""
Интерфейс для Hikvision ISAPI клиента.
Позволяет изолировать интеграцию для тестирования.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime


class IHikvisionClient(ABC):
    """Интерфейс для Hikvision ISAPI клиента."""

    @abstractmethod
    async def check_connection(self) -> Tuple[bool, Optional[str]]:
        """Проверка подключения к терминалу."""
        pass

    @abstractmethod
    async def create_user(self, user_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Создание пользователя на терминале."""
        pass

    @abstractmethod
    async def upload_face_photo(self, user_id: str, photo_data: bytes) -> Tuple[bool, Optional[str]]:
        """Загрузка фото лица пользователя."""
        pass

    @abstractmethod
    async def sync_user_to_device(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """Синхронизация пользователя с устройством."""
        pass

    @abstractmethod
    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Получение информации о пользователе."""
        pass

    @abstractmethod
    async def delete_user(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """Удаление пользователя с терминала."""
        pass

    @abstractmethod
    async def get_users_list(self) -> List[Dict[str, Any]]:
        """Получение списка пользователей."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Закрытие соединения."""
        pass
