"""
Миграция существующих пользователей с synced_to_device=True.
Создает записи в user_device_sync для всех активных устройств.

Запуск:
    python -m backend.scripts.migrate_existing_users_to_devices
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app import models, database, crud
from sqlalchemy import select
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_synced_users():
    """Миграция пользователей с synced_to_device=True в таблицу user_device_sync."""
    
    async with database.AsyncSessionLocal() as db:
        try:
            # Получаем всех пользователей с synced_to_device=True
            result = await db.execute(
                select(models.User).filter(models.User.synced_to_device == True)
            )
            synced_users = result.scalars().all()
            
            logger.info(f"Найдено {len(synced_users)} пользователей с synced_to_device=True")
            
            if not synced_users:
                logger.info("Нет пользователей для миграции")
                return
            
            # Получаем все активные устройства
            devices = await crud.get_all_devices(db)
            active_devices = [d for d in devices if d.is_active]
            
            logger.info(f"Найдено {len(active_devices)} активных устройств")
            
            if not active_devices:
                logger.warning("Нет активных устройств для миграции")
                return
            
            # Создаем записи синхронизации
            migrated_count = 0
            for user in synced_users:
                for device in active_devices:
                    # Проверяем, есть ли уже запись
                    existing = await db.execute(
                        select(models.UserDeviceSync).filter(
                            models.UserDeviceSync.user_id == user.id,
                            models.UserDeviceSync.device_id == device.id
                        )
                    )
                    
                    if existing.scalars().first():
                        logger.debug(f"Запись уже существует: user {user.id} -> device {device.id}")
                        continue
                    
                    # Создаем новую запись
                    sync_record = models.UserDeviceSync(
                        user_id=user.id,
                        device_id=device.id,
                        sync_status='synced',  # Предполагаем, что они были синхронизированы
                        last_sync_at=user.created_at  # Используем дату создания пользователя
                    )
                    db.add(sync_record)
                    migrated_count += 1
                    logger.info(f"Создана запись: user {user.hikvision_id} -> device {device.name}")
            
            await db.commit()
            logger.info(f"✓ Миграция завершена: создано {migrated_count} записей")
            
        except Exception as e:
            logger.error(f"Ошибка миграции: {e}", exc_info=True)
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(migrate_synced_users())

