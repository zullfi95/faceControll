from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, func, and_, or_
from . import models, schemas, schemas_internal
from .utils.crypto import encrypt_password, decrypt_password
from .enums import UserRole
from datetime import datetime
from typing import Optional, List, Tuple
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
        department=user.department,
        role=user.role or UserRole.CLEANER.value
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
    # Находим пользователя по его ID из терминала (если указан)
    user = None
    if event.hikvision_id:
        user = await get_user_by_hik_id(db, event.hikvision_id)
        if not user:
            logger.warning(f"[CREATE_EVENT] Unknown user {event.hikvision_id}")

    db_event = models.AttendanceEvent(
        user_id=user.id if user else None,
        timestamp=event.timestamp,
        event_type=event.event_type,
        terminal_ip=event.terminal_ip,
        employee_no=event.employee_no or event.hikvision_id,
        name=event.name,
        card_no=event.card_no,
        card_reader_id=event.card_reader_id,
        event_type_code=event.event_type_code,
        event_type_description=event.event_type_description,
        remote_host_ip=event.remote_host_ip
    )
    
    db.add(db_event)
    await db.commit()
    await db.refresh(db_event)
    
    logger.info(f"[CREATE_EVENT] ===== EVENT CREATION COMPLETE =====")
    
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

async def update_user(db: AsyncSession, user_id: int, user_update: schemas.UserUpdate) -> Optional[models.User]:
    """Обновление пользователя."""
    db_user = await get_user_by_id(db, user_id)
    if not db_user:
        return None
    
    update_data = user_update.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_user, key, value)
    
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def delete_user(db: AsyncSession, user_id: int) -> bool:
    """Удаление пользователя по ID."""
    try:
        user = await get_user_by_id(db, user_id)
        if not user:
            return False
        
        # Удаляем связанные события и пользователя в одной транзакции
        from sqlalchemy import delete
        await db.execute(delete(models.AttendanceEvent).filter(models.AttendanceEvent.user_id == user_id))
        await db.delete(user)
        await db.commit()
        return True
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}", exc_info=True)
        await db.rollback()
        raise

async def delete_all_users(db: AsyncSession) -> int:
    """Удаление всех пользователей из базы данных."""
    # Сначала удаляем все события
    from sqlalchemy import delete
    await db.execute(delete(models.AttendanceEvent))
    
    # Затем удаляем всех пользователей
    result = await db.execute(delete(models.User))
    await db.commit()
    return result.rowcount

async def get_events(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    event_type: Optional[str] = None,
    employee_no: Optional[str] = None
) -> tuple[List[models.AttendanceEvent], int]:
    """
    Получение событий с поддержкой пагинации и фильтрации.
    
    Returns:
        Кортеж (список событий, общее количество)
    """
    query = select(models.AttendanceEvent)
    count_query = select(func.count(models.AttendanceEvent.id))
    
    # Применяем фильтры
    conditions = []
    
    if start_date:
        conditions.append(models.AttendanceEvent.timestamp >= start_date)
    if end_date:
        conditions.append(models.AttendanceEvent.timestamp <= end_date)
    if event_type:
        conditions.append(
            or_(
                models.AttendanceEvent.event_type == event_type,
                models.AttendanceEvent.event_type_description.ilike(f"%{event_type}%")
            )
        )
    if employee_no:
        conditions.append(models.AttendanceEvent.employee_no == employee_no)
    
    if conditions:
        query = query.filter(and_(*conditions))
        count_query = count_query.filter(and_(*conditions))
    
    # Получаем общее количество
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Применяем сортировку и пагинацию
    query = query.order_by(models.AttendanceEvent.timestamp.desc())
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    events = result.scalars().all()
    
    return events, total

# --- System User Operations (Authentication) ---
async def get_system_user_by_username(db: AsyncSession, username: str) -> Optional[models.SystemUser]:
    """Получение пользователя системы по username."""
    result = await db.execute(
        select(models.SystemUser).filter(models.SystemUser.username == username)
    )
    return result.scalars().first()

async def create_system_user(db: AsyncSession, user: schemas.SystemUserCreate):
    """Создание пользователя системы."""
    from .auth import get_password_hash
    
    hashed_password = get_password_hash(user.password)
    db_user = models.SystemUser(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        hashed_password=hashed_password,
        is_active=user.is_active
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def get_system_user_by_id(db: AsyncSession, user_id: int) -> Optional[models.SystemUser]:
    """Получение пользователя системы по ID."""
    result = await db.execute(
        select(models.SystemUser).filter(models.SystemUser.id == user_id)
    )
    return result.scalars().first()

async def get_all_system_users(db: AsyncSession, skip: int = 0, limit: int = 100):
    """Получение всех пользователей системы."""
    result = await db.execute(
        select(models.SystemUser).offset(skip).limit(limit)
    )
    return result.scalars().all()

async def update_system_user(
    db: AsyncSession, 
    user_id: int, 
    user_update: schemas.SystemUserUpdate
) -> Optional[models.SystemUser]:
    """Обновление пользователя системы."""
    from .auth import get_password_hash
    
    db_user = await get_system_user_by_id(db, user_id)
    if not db_user:
        return None
    
    update_data = user_update.model_dump(exclude_unset=True)
    
    # Если обновляется пароль, хешируем его
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    
    for key, value in update_data.items():
        setattr(db_user, key, value)
    
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def delete_system_user(db: AsyncSession, user_id: int) -> bool:
    """Удаление пользователя системы."""
    db_user = await get_system_user_by_id(db, user_id)
    if not db_user:
        return False
    
    await db.delete(db_user)
    await db.commit()
    return True

async def update_last_login(db: AsyncSession, user_id: int):
    """Обновление времени последнего входа."""
    db_user = await get_system_user_by_id(db, user_id)
    if db_user:
        db_user.last_login = datetime.now()
        await db.commit()

# --- Work Shift Operations ---
async def create_work_shift(db: AsyncSession, shift: schemas.WorkShiftCreate) -> models.WorkShift:
    """Создание рабочей смены."""
    # Преобразуем DaySchedule объекты в словари для JSON сериализации
    schedule_dict = {}
    if shift.schedule:
        for day_key, day_schedule in shift.schedule.items():
            if hasattr(day_schedule, 'model_dump'):
                # Это Pydantic модель
                schedule_dict[day_key] = day_schedule.model_dump()
            elif isinstance(day_schedule, dict):
                # Уже словарь
                schedule_dict[day_key] = day_schedule
            else:
                # Объект DaySchedule
                schedule_dict[day_key] = {
                    "start": day_schedule.start,
                    "end": day_schedule.end,
                    "enabled": day_schedule.enabled
                }
    
    db_shift = models.WorkShift(
        name=shift.name,
        description=shift.description,
        schedule=schedule_dict,
        is_active=shift.is_active
    )
    db.add(db_shift)
    await db.commit()
    await db.refresh(db_shift)
    return db_shift

async def get_work_shift_by_id(db: AsyncSession, shift_id: int) -> Optional[models.WorkShift]:
    """Получение рабочей смены по ID."""
    result = await db.execute(
        select(models.WorkShift).filter(models.WorkShift.id == shift_id)
    )
    return result.scalars().first()

async def get_all_work_shifts(db: AsyncSession, skip: int = 0, limit: int = 100, active_only: bool = False):
    """Получение всех рабочих смен."""
    query = select(models.WorkShift)
    if active_only:
        query = query.filter(models.WorkShift.is_active == True)
    query = query.offset(skip).limit(limit).order_by(models.WorkShift.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()

async def update_work_shift(
    db: AsyncSession,
    shift_id: int,
    shift_update: schemas.WorkShiftUpdate
) -> Optional[models.WorkShift]:
    """Обновление рабочей смены."""
    db_shift = await get_work_shift_by_id(db, shift_id)
    if not db_shift:
        return None
    
    update_data = shift_update.model_dump(exclude_unset=True)
    
    # Преобразуем DaySchedule объекты в словари для JSON сериализации
    if "schedule" in update_data and update_data["schedule"]:
        schedule_dict = {}
        for day_key, day_schedule in update_data["schedule"].items():
            if hasattr(day_schedule, 'model_dump'):
                # Это Pydantic модель
                schedule_dict[day_key] = day_schedule.model_dump()
            elif isinstance(day_schedule, dict):
                # Уже словарь
                schedule_dict[day_key] = day_schedule
            else:
                # Объект DaySchedule
                schedule_dict[day_key] = {
                    "start": day_schedule.start,
                    "end": day_schedule.end,
                    "enabled": day_schedule.enabled
                }
        update_data["schedule"] = schedule_dict
    
    for key, value in update_data.items():
        setattr(db_shift, key, value)
    
    db_shift.updated_at = datetime.now()
    await db.commit()
    await db.refresh(db_shift)
    return db_shift

async def delete_work_shift(db: AsyncSession, shift_id: int) -> bool:
    """Удаление рабочей смены."""
    db_shift = await get_work_shift_by_id(db, shift_id)
    if not db_shift:
        return False
    
    await db.delete(db_shift)
    await db.commit()
    return True

# --- User Shift Assignment Operations ---
async def create_user_shift_assignment(
    db: AsyncSession,
    assignment: schemas.UserShiftAssignmentCreate
) -> models.UserShiftAssignment:
    """Создание привязки пользователя к смене."""
    db_assignment = models.UserShiftAssignment(
        user_id=assignment.user_id,
        shift_id=assignment.shift_id,
        start_date=assignment.start_date,
        end_date=assignment.end_date,
        is_active=assignment.is_active
    )
    db.add(db_assignment)
    await db.commit()
    await db.refresh(db_assignment)
    return db_assignment

async def get_user_shift_assignment_by_id(
    db: AsyncSession,
    assignment_id: int
) -> Optional[models.UserShiftAssignment]:
    """Получение привязки по ID."""
    result = await db.execute(
        select(models.UserShiftAssignment).filter(models.UserShiftAssignment.id == assignment_id)
    )
    return result.scalars().first()

async def get_user_shift_assignments(
    db: AsyncSession,
    user_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    active_only: bool = False
):
    """Получение привязок пользователей к сменам."""
    query = select(models.UserShiftAssignment)
    
    if user_id:
        query = query.filter(models.UserShiftAssignment.user_id == user_id)
    if shift_id:
        query = query.filter(models.UserShiftAssignment.shift_id == shift_id)
    if active_only:
        query = query.filter(models.UserShiftAssignment.is_active == True)
    
    query = query.order_by(models.UserShiftAssignment.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()

async def update_user_shift_assignment(
    db: AsyncSession,
    assignment_id: int,
    assignment_update: schemas.UserShiftAssignmentUpdate
) -> Optional[models.UserShiftAssignment]:
    """Обновление привязки пользователя к смене."""
    db_assignment = await get_user_shift_assignment_by_id(db, assignment_id)
    if not db_assignment:
        return None
    
    update_data = assignment_update.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_assignment, key, value)
    
    db_assignment.updated_at = datetime.now()
    await db.commit()
    await db.refresh(db_assignment)
    return db_assignment

async def delete_user_shift_assignment(db: AsyncSession, assignment_id: int) -> bool:
    """Удаление привязки пользователя к смене."""
    db_assignment = await get_user_shift_assignment_by_id(db, assignment_id)
    if not db_assignment:
        return False
    
    await db.delete(db_assignment)
    await db.commit()
    return True