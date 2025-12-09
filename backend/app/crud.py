from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from . import models, schemas, schemas_internal
from .utils.crypto import encrypt_password, decrypt_password
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# --- User Operations ---
async def get_user_by_hik_id(db: AsyncSession, hik_id: str):
    result = await db.execute(select(models.User).filter(models.User.hikvision_id == hik_id))
    return result.scalars().first()

async def create_user(db: AsyncSession, user: schemas.UserCreate):
    db_user = models.User(
        hikvision_id=user.hikvision_id,
        full_name=user.full_name,
        department=user.department
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100):
    result = await db.execute(select(models.User).offset(skip).limit(limit))
    return result.scalars().all()

# --- Event Operations ---
async def create_event(db: AsyncSession, event: schemas_internal.InternalEventCreate):
    # Сначала находим пользователя по его ID из терминала
    user = await get_user_by_hik_id(db, event.hikvision_id)
    if not user:
        logger.warning(f"Received event for unknown user {event.hikvision_id}")
        return None

    db_event = models.AttendanceEvent(
        user_id=user.id,
        timestamp=event.timestamp,
        event_type=event.event_type,
        terminal_ip=event.terminal_ip
    )
    db.add(db_event)
    await db.commit()
    await db.refresh(db_event)
    return db_event

async def get_user_events_for_day(db: AsyncSession, user_id: int, date_start: datetime, date_end: datetime):
    result = await db.execute(
        select(models.AttendanceEvent)
        .filter(models.AttendanceEvent.user_id == user_id)
        .filter(models.AttendanceEvent.timestamp >= date_start)
        .filter(models.AttendanceEvent.timestamp <= date_end)
        .order_by(models.AttendanceEvent.timestamp.asc())
    )
    return result.scalars().all()

async def get_all_events_for_day(db: AsyncSession, date_start: datetime, date_end: datetime):
    """Оптимизированная функция для получения всех событий за день с JOIN к пользователям."""
    from sqlalchemy.orm import joinedload
    result = await db.execute(
        select(models.AttendanceEvent)
        .options(joinedload(models.AttendanceEvent.user))
        .filter(models.AttendanceEvent.timestamp >= date_start)
        .filter(models.AttendanceEvent.timestamp <= date_end)
        .order_by(models.AttendanceEvent.user_id, models.AttendanceEvent.timestamp.asc())
    )
    return result.unique().scalars().all()

# --- Device Operations ---
async def create_device(db: AsyncSession, device: schemas.DeviceCreate):
    """Создание нового устройства с шифрованием пароля."""
    encrypted_pwd = encrypt_password(device.password)
    db_device = models.Device(
        name=device.name,
        ip_address=device.ip_address,
        username=device.username,
        password_encrypted=encrypted_pwd
    )
    db.add(db_device)
    await db.commit()
    await db.refresh(db_device)
    return db_device

async def get_device_by_id(db: AsyncSession, device_id: int) -> Optional[models.Device]:
    """Получение устройства по ID."""
    result = await db.execute(select(models.Device).filter(models.Device.id == device_id))
    return result.scalars().first()

async def get_active_device(db: AsyncSession) -> Optional[models.Device]:
    """Получение первого активного устройства."""
    result = await db.execute(
        select(models.Device)
        .filter(models.Device.is_active == True)
        .limit(1)
    )
    return result.scalars().first()

async def get_all_devices(db: AsyncSession):
    """Получение всех устройств."""
    result = await db.execute(select(models.Device))
    return result.scalars().all()

async def update_device(db: AsyncSession, device_id: int, device_update: schemas.DeviceUpdate):
    """Обновление устройства."""
    db_device = await get_device_by_id(db, device_id)
    if not db_device:
        return None
    
    update_data = device_update.model_dump(exclude_unset=True)
    
    # Если обновляется пароль, шифруем его
    if "password" in update_data:
        update_data["password_encrypted"] = encrypt_password(update_data.pop("password"))
    
    for key, value in update_data.items():
        setattr(db_device, key, value)
    
    await db.commit()
    await db.refresh(db_device)
    return db_device

async def update_device_sync_time(db: AsyncSession, device_id: int):
    """Обновление времени последней синхронизации."""
    db_device = await get_device_by_id(db, device_id)
    if db_device:
        db_device.last_sync = datetime.now()
        await db.commit()

async def mark_user_synced(db: AsyncSession, user_id: int, synced: bool = True):
    """Отметка пользователя как синхронизированного с устройством."""
    result = await db.execute(select(models.User).filter(models.User.id == user_id))
    user = result.scalars().first()
    if user:
        user.synced_to_device = synced
        await db.commit()
        await db.refresh(user)
    return user

async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[models.User]:
    """Получение пользователя по ID."""
    result = await db.execute(select(models.User).filter(models.User.id == user_id))
    return result.scalars().first()

async def delete_user(db: AsyncSession, user_id: int) -> bool:
    """Удаление пользователя по ID."""
    user = await get_user_by_id(db, user_id)
    if not user:
        return False
    
    # Удаляем связанные события (cascade delete)
    from sqlalchemy import delete
    await db.execute(delete(models.AttendanceEvent).filter(models.AttendanceEvent.user_id == user_id))
    
    await db.delete(user)
    await db.commit()
    return True

async def delete_all_users(db: AsyncSession) -> int:
    """Удаление всех пользователей из базы данных."""
    # Сначала удаляем все события
    from sqlalchemy import delete
    await db.execute(delete(models.AttendanceEvent))
    
    # Затем удаляем всех пользователей
    result = await db.execute(delete(models.User))
    await db.commit()
    return result.rowcount