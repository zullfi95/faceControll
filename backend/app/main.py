from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any, Optional
import os
import uuid
import logging
import json
import asyncio
from pathlib import Path
import httpx
from datetime import datetime, time, timedelta

from . import models, database, crud, schemas, schemas_internal
from .utils.crypto import decrypt_password, encrypt_password
from .utils.telegram_bot import TelegramBot
from .utils.daily_report_service import DailyReportService
from .utils.websocket_manager import websocket_manager
from .hikvision_client import HikvisionClient
from . import event_service
from .webhook_handler import parse_multipart_event, parse_json_event
from .auth import (
    verify_password, create_access_token, get_current_active_user,
    require_operations_manager, get_current_user
)
from fastapi import Request, Header
from fastapi.security import OAuth2PasswordRequestForm

app = FastAPI(title="Face Access Control System")

logger = logging.getLogger(__name__)

def get_device_password_safe(device, device_id: int = None) -> str:
    """
    Безопасное получение пароля устройства с обработкой ошибок расшифровки.
    
    Args:
        device: Объект устройства из БД
        device_id: ID устройства для логирования (опционально)
    
    Returns:
        Расшифрованный пароль
    
    Raises:
        HTTPException: Если не удалось расшифровать пароль
    """
    try:
        return decrypt_password(device.password_encrypted)
    except ValueError as e:
        logger.error(f"Ошибка расшифровки пароля устройства {device_id or device.id}: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

WEBHOOK_API_KEY = os.getenv("WEBHOOK_API_KEY", "")

UPLOAD_DIR = Path("/app/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.get("/uploads/{filename:path}")
async def get_uploaded_file(filename: str):
    """Отдача загруженных файлов с заголовками no-cache."""
    from fastapi.responses import FileResponse
    
    file_path = UPLOAD_DIR / filename
    
    # Проверка безопасности пути
    try:
        file_path.resolve().relative_to(UPLOAD_DIR.resolve())
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="File not found")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=str(file_path),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

telegram_bot = None
daily_report_service = None
daily_report_task = None  # Фоновая задача для ежедневных отчетов

async def send_daily_reports_automatically():
    """
    Фоновая задача для автоматической отправки ежедневных отчетов.
    Запускается каждый день в 18:00 (по времени Baku UTC+4).
    """
    while True:
        try:
            now = datetime.now()
            # Целевое время отправки: 18:00 по Baku (UTC+4)
            target_time = now.replace(hour=18, minute=0, second=0, microsecond=0)

            # Если уже прошло 18:00 сегодня, ждем до завтра
            if now >= target_time:
                target_time = target_time + timedelta(days=1)

            # Ждем до целевого времени
            sleep_seconds = (target_time - now).total_seconds()
            logger.info(f"Sleeping for {sleep_seconds:.1f} seconds until next report time")
            await asyncio.sleep(sleep_seconds)

            # Отправляем отчет за вчера
            from .database import get_db_session
            async for db in get_db_session():
                try:
                    global daily_report_service
                    if daily_report_service:
                        yesterday = (datetime.now().date() - timedelta(days=1))
                        logger.info(f"Sending automated daily report for {yesterday}")
                        await daily_report_service.send_daily_report(db, yesterday)
                    else:
                        logger.warning("Daily report service not available")
                    break
                except Exception as e:
                    logger.error(f"Error in automated report sending: {e}", exc_info=True)
                finally:
                    await db.close()

        except Exception as e:
            logger.error(f"Error in daily report automation: {e}", exc_info=True)
            await asyncio.sleep(3600)  # Ждем 1 час перед следующей попыткой

@app.on_event("startup")
async def startup():
    """Инициализация базы данных и телеграм бота при запуске приложения."""
    # Инициализация базы данных
    async with database.engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

    # Инициализация телеграм бота
    global telegram_bot, daily_report_service, daily_report_task
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if telegram_token and telegram_chat_id:
        telegram_bot = TelegramBot(telegram_token, telegram_chat_id)
        daily_report_service = DailyReportService(telegram_bot)

        # Запускаем автоматическую отправку отчетов
        daily_report_task = asyncio.create_task(send_daily_reports_automatically())
        logger.info("Telegram bot and automated daily reports initialized successfully")
    else:
        logger.warning("Telegram bot not configured (missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID)")

@app.post("/users/", response_model=schemas.UserResponse)
async def create_user(user: schemas.UserCreate, db: AsyncSession = Depends(database.get_db)):
    """Создание нового пользователя."""
    # Проверяем, не существует ли уже пользователь с таким ID
    existing_user = await crud.get_user_by_hik_id(db, user.hikvision_id)
    if existing_user:
        raise HTTPException(status_code=400, detail=f"User with hikvision_id '{user.hikvision_id}' already exists")

    return await crud.create_user(db=db, user=user)

@app.get("/users/", response_model=List[schemas.UserResponse])
async def get_users(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(database.get_db)):
    """Получение списка пользователей."""
    return await crud.get_users(db, skip=skip, limit=limit)

@app.get("/users/{user_id}", response_model=schemas.UserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(database.get_db)):
    """Получение пользователя по ID."""
    user = await crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.put("/users/{user_id}", response_model=schemas.UserResponse)
async def update_user(
    user_id: int, 
    user_update: schemas.UserUpdate, 
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
):
    """Обновление пользователя. Только для Operations Manager."""
    user = await crud.update_user(db, user_id, user_update)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/roles", response_model=schemas.RolesListResponse)
async def get_roles():
    """
    Получение списка всех доступных ролей в системе.
    
    Returns:
        Список ролей с их значениями и отображаемыми именами
    """
    from .enums import UserRole
    
    roles = [
        schemas.RoleInfo(value=role[0], display_name=role[1])
        for role in UserRole.get_all_roles()
    ]
    
    return schemas.RolesListResponse(roles=roles)

@app.post("/auth/login", response_model=schemas.Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(database.get_db)
):
    """
    Вход в систему. Возвращает JWT токен.
    """
    user = await crud.get_system_user_by_username(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    # Обновляем время последнего входа
    await crud.update_last_login(db, user.id)
    
    # Создаем токен
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me", response_model=schemas.CurrentUserResponse)
async def get_current_user_info(
    current_user: models.SystemUser = Depends(get_current_active_user)
):
    """Получение информации о текущем пользователе."""
    return current_user

@app.post("/system-users/", response_model=schemas.SystemUserResponse)
async def create_system_user(
    user: schemas.SystemUserCreate,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
):
    """Создание пользователя системы. Только для Operations Manager."""
    # Проверяем, не существует ли уже пользователь с таким username
    existing_user = await crud.get_system_user_by_username(db, user.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    return await crud.create_system_user(db, user)

@app.get("/system-users/", response_model=List[schemas.SystemUserResponse])
async def get_system_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
):
    """Получение списка пользователей системы. Только для Operations Manager."""
    return await crud.get_all_system_users(db, skip=skip, limit=limit)

@app.get("/system-users/{user_id}", response_model=schemas.SystemUserResponse)
async def get_system_user(
    user_id: int,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
):
    """Получение пользователя системы по ID. Только для Operations Manager."""
    user = await crud.get_system_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.put("/system-users/{user_id}", response_model=schemas.SystemUserResponse)
async def update_system_user(
    user_id: int,
    user_update: schemas.SystemUserUpdate,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
):
    """Обновление пользователя системы. Только для Operations Manager."""
    user = await crud.update_system_user(db, user_id, user_update)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.delete("/system-users/{user_id}")
async def delete_system_user(
    user_id: int,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
):
    """Удаление пользователя системы. Только для Operations Manager."""
    # Нельзя удалить самого себя
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    success = await crud.delete_system_user(db, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": f"User {user_id} deleted successfully"}

@app.post("/work-shifts/", response_model=schemas.WorkShiftResponse)
async def create_work_shift(
    shift: schemas.WorkShiftCreate,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
):
    """Создание рабочей смены. Только для Operations Manager."""
    return await crud.create_work_shift(db, shift)

@app.get("/work-shifts/", response_model=List[schemas.WorkShiftResponse])
async def get_work_shifts(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
):
    """Получение списка рабочих смен. Только для Operations Manager."""
    shifts = await crud.get_all_work_shifts(db, skip=skip, limit=limit, active_only=active_only)
    
    # Добавляем количество привязанных пользователей
    result = []
    for shift in shifts:
        assignments = await crud.get_user_shift_assignments(db, shift_id=shift.id, active_only=True)
        # Преобразуем schedule из JSONB в dict если нужно
        schedule = shift.schedule
        if isinstance(schedule, str):
            import json
            schedule = json.loads(schedule)
        
        shift_dict = {
            "id": shift.id,
            "name": shift.name,
            "description": shift.description,
            "schedule": schedule,
            "is_active": shift.is_active,
            "created_at": shift.created_at,
            "updated_at": shift.updated_at,
            "user_count": len(assignments)
        }
        result.append(shift_dict)
    
    return result

@app.get("/work-shifts/{shift_id}", response_model=schemas.WorkShiftResponse)
async def get_work_shift(
    shift_id: int,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
):
    """Получение рабочей смены по ID. Только для Operations Manager."""
    shift = await crud.get_work_shift_by_id(db, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Work shift not found")
    
    assignments = await crud.get_user_shift_assignments(db, shift_id=shift_id, active_only=True)
    
    # Преобразуем schedule из JSONB в dict если нужно
    schedule = shift.schedule
    if isinstance(schedule, str):
        import json
        schedule = json.loads(schedule)
    
    return {
        "id": shift.id,
        "name": shift.name,
        "description": shift.description,
        "schedule": schedule,
        "is_active": shift.is_active,
        "created_at": shift.created_at,
        "updated_at": shift.updated_at,
        "user_count": len(assignments)
    }

@app.put("/work-shifts/{shift_id}", response_model=schemas.WorkShiftResponse)
async def update_work_shift(
    shift_id: int,
    shift_update: schemas.WorkShiftUpdate,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
):
    """Обновление рабочей смены. Только для Operations Manager."""
    shift = await crud.update_work_shift(db, shift_id, shift_update)
    if not shift:
        raise HTTPException(status_code=404, detail="Work shift not found")
    
    assignments = await crud.get_user_shift_assignments(db, shift_id=shift_id, active_only=True)
    
    # Преобразуем schedule из JSONB в dict если нужно
    schedule = shift.schedule
    if isinstance(schedule, str):
        import json
        schedule = json.loads(schedule)
    
    return {
        "id": shift.id,
        "name": shift.name,
        "description": shift.description,
        "schedule": schedule,
        "is_active": shift.is_active,
        "created_at": shift.created_at,
        "updated_at": shift.updated_at,
        "user_count": len(assignments)
    }

@app.delete("/work-shifts/{shift_id}")
async def delete_work_shift(
    shift_id: int,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
):
    """Удаление рабочей смены. Только для Operations Manager."""
    success = await crud.delete_work_shift(db, shift_id)
    if not success:
        raise HTTPException(status_code=404, detail="Work shift not found")
    return {"message": f"Work shift {shift_id} deleted successfully"}

@app.post("/user-shift-assignments/", response_model=schemas.UserShiftAssignmentResponse)
async def create_user_shift_assignment(
    assignment: schemas.UserShiftAssignmentCreate,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
):
    """Создание привязки пользователя к смене. Только для Operations Manager."""
    # Проверяем существование пользователя и смены
    user = await crud.get_user_by_id(db, assignment.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    shift = await crud.get_work_shift_by_id(db, assignment.shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Work shift not found")
    
    db_assignment = await crud.create_user_shift_assignment(db, assignment)
    
    # Загружаем связанные данные для ответа
    await db.refresh(db_assignment)
    return {
        "id": db_assignment.id,
        "user_id": db_assignment.user_id,
        "shift_id": db_assignment.shift_id,
        "start_date": db_assignment.start_date,
        "end_date": db_assignment.end_date,
        "is_active": db_assignment.is_active,
        "created_at": db_assignment.created_at,
        "updated_at": db_assignment.updated_at,
        "user_name": user.full_name or user.hikvision_id,
        "shift_name": shift.name
    }

@app.get("/user-shift-assignments/", response_model=List[schemas.UserShiftAssignmentResponse])
async def get_user_shift_assignments(
    user_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    active_only: bool = False,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
):
    """Получение привязок пользователей к сменам. Только для Operations Manager."""
    assignments = await crud.get_user_shift_assignments(
        db, user_id=user_id, shift_id=shift_id, active_only=active_only
    )
    
    # Загружаем связанные данные
    result = []
    for assignment in assignments:
        user = await crud.get_user_by_id(db, assignment.user_id)
        shift = await crud.get_work_shift_by_id(db, assignment.shift_id)
        result.append({
            "id": assignment.id,
            "user_id": assignment.user_id,
            "shift_id": assignment.shift_id,
            "start_date": assignment.start_date,
            "end_date": assignment.end_date,
            "is_active": assignment.is_active,
            "created_at": assignment.created_at,
            "updated_at": assignment.updated_at,
            "user_name": user.full_name if user else None,
            "shift_name": shift.name if shift else None
        })
    
    return result

@app.put("/user-shift-assignments/{assignment_id}", response_model=schemas.UserShiftAssignmentResponse)
async def update_user_shift_assignment(
    assignment_id: int,
    assignment_update: schemas.UserShiftAssignmentUpdate,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
):
    """Обновление привязки пользователя к смене. Только для Operations Manager."""
    assignment = await crud.update_user_shift_assignment(db, assignment_id, assignment_update)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    user = await crud.get_user_by_id(db, assignment.user_id)
    shift = await crud.get_work_shift_by_id(db, assignment.shift_id)
    return {
        "id": assignment.id,
        "user_id": assignment.user_id,
        "shift_id": assignment.shift_id,
        "start_date": assignment.start_date,
        "end_date": assignment.end_date,
        "is_active": assignment.is_active,
        "created_at": assignment.created_at,
        "updated_at": assignment.updated_at,
        "user_name": user.full_name if user else None,
        "shift_name": shift.name if shift else None
    }

@app.delete("/user-shift-assignments/{assignment_id}")
async def delete_user_shift_assignment(
    assignment_id: int,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
):
    """Удаление привязки пользователя к смене. Только для Operations Manager."""
    success = await crud.delete_user_shift_assignment(db, assignment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return {"message": f"Assignment {assignment_id} deleted successfully"}

@app.delete("/users/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(database.get_db)):
    """Удаление пользователя."""
    # Получаем пользователя
    user = await crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Удаляем файл фото, если он существует
    if user.photo_path:
        photo_filename = Path(user.photo_path).name
        photo_file_path = UPLOAD_DIR / photo_filename
        try:
            if photo_file_path.exists():
                photo_file_path.unlink()
                logger.info(f"Deleted photo file: {photo_file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete photo file {photo_file_path}: {e}")

    # Удаляем пользователя из БД
    success = await crud.delete_user(db, user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete user")

    return {"message": f"User {user_id} deleted successfully"}

@app.post("/users/{user_id}/upload-photo")
async def upload_user_photo(
    user_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(database.get_db)
):
    """Загрузка фото пользователя."""
    from fastapi import UploadFile, File

    # Проверка существования пользователя
    user = await crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Проверка типа файла
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Удаление старого фото, если оно существует
    if user.photo_path:
        old_photo_filename = Path(user.photo_path).name
        old_photo_path = UPLOAD_DIR / old_photo_filename
        try:
            if old_photo_path.exists():
                old_photo_path.unlink()
                logger.info(f"Deleted old photo file: {old_photo_path}")
        except Exception as e:
            logger.warning(f"Failed to delete old photo {old_photo_path}: {e}")

    # Сохранение нового файла
    file_extension = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    unique_filename = f"{user.hikvision_id}_{uuid.uuid4().hex}.{file_extension}"
    file_path = UPLOAD_DIR / unique_filename

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Обновление пользователя
    user.photo_path = f"/uploads/{unique_filename}"
    await db.commit()
    await db.refresh(user)

    logger.info(f"Photo uploaded for user {user_id}: {user.photo_path}")
    return {"message": "Photo uploaded successfully", "photo_path": user.photo_path}

@app.post("/users/{user_id}/sync-to-device")
async def sync_user_to_device(user_id: int, db: AsyncSession = Depends(database.get_db)):
    """Синхронизация пользователя с устройством (добавление на терминал)."""
    # Получение пользователя
    user = await crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Получение активного устройства
    device = await crud.get_active_device(db)
    if not device:
        raise HTTPException(status_code=404, detail="No active device found")

    # Проверка наличия фото (если фото нет, попробуем скачать с терминала при синхронизации)
    has_photo_on_server = bool(user.photo_path)

    try:
        # Расшифровка пароля устройства
        password = get_device_password_safe(device, device.id)
        logger.info(f"Using decrypted password for device {device.id}: username={device.username}, password_length={len(password)}")
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Проверяем соединение перед началом работы
        logger.info(f"Checking connection to device {device.ip_address}...")
        connected, error = await client.check_connection()
        if not connected:
            logger.error(f"Device connection failed: {error}")
            raise HTTPException(status_code=503, detail=f"Device is not accessible: {error}")
        logger.info(f"Device connection OK")

        # Чтение фото с валидацией пути (только если фото есть на сервере)
        photo_bytes = None
        if has_photo_on_server:
            filename = Path(user.photo_path).name
            if not filename or filename != Path(user.photo_path).name:
                logger.warning(f"Invalid photo path for user {user.hikvision_id}: {user.photo_path}")
                has_photo_on_server = False  # Сбрасываем флаг, если путь невалидный
            else:
                photo_file_path = UPLOAD_DIR / filename

                # Дополнительная проверка, что путь находится в UPLOAD_DIR
                try:
                    photo_file_path.resolve().relative_to(UPLOAD_DIR.resolve())
                except ValueError:
                    logger.warning(f"Invalid photo path (path traversal) for user {user.hikvision_id}: {user.photo_path}")
                    has_photo_on_server = False  # Сбрасываем флаг
                else:
                    if photo_file_path.exists():
                        try:
                            with open(photo_file_path, "rb") as f:
                                photo_bytes = f.read()
                            logger.info(f"Photo loaded from server for user {user.hikvision_id}: {len(photo_bytes)} bytes")
                        except Exception as e:
                            logger.warning(f"Error reading photo file for user {user.hikvision_id}: {e}")
                            has_photo_on_server = False  # Сбрасываем флаг
                    else:
                        logger.warning(f"Photo file not found on server for user {user.hikvision_id}: {photo_file_path}. Will try to download from terminal.")
                        has_photo_on_server = False  # Сбрасываем флаг, попробуем скачать с терминала

        # Создание пользователя на терминале
        try:
            result = await client.create_user_basic(
                employee_no=user.hikvision_id,
                name=user.full_name,
                group_id=user.department if user.department and str(user.department).isdigit() else None
            )
            
            if not result.get("success"):
                logger.warning(f"Failed to create user {user.hikvision_id} on terminal: {result.get('error')}")

            # Привязка фото через FDSetUp (используем web_face_enrollpic.jpg, созданный через CaptureFaceData)
            face_url = f"{client.base_url}/LOCALS/pic/web_face_enrollpic.jpg@WEB000000000020"
            face_result = await client.setup_user_face_fdlib(
                employee_no=user.hikvision_id,
                face_url=face_url
            )

            if face_result.get("success"):
                logger.info(f"Photo linked for user {user.hikvision_id}")
                
                # Если у пользователя нет photo_path, скачиваем фото с терминала и сохраняем на сервере
                if not has_photo_on_server:
                    try:
                        http_client = await client._get_client()
                        # Скачиваем фото с терминала
                        photo_response = await http_client.get(
                            face_url.split("@")[0],  # Убираем токен из URL
                            auth=client.auth,
                            timeout=10
                        )
                        
                        if photo_response.status_code == 200:
                            photo_bytes = photo_response.content
                            # Сохраняем фото на сервере
                            photo_filename = f"{user.hikvision_id}_{uuid.uuid4().hex}.jpg"
                            photo_file_path = UPLOAD_DIR / photo_filename
                            
                            with open(photo_file_path, "wb") as f:
                                f.write(photo_bytes)
                            
                            # Обновляем photo_path в БД
                            user.photo_path = f"/uploads/{photo_filename}"
                            await db.commit()
                            await db.refresh(user)
                            
                            logger.info(f"Photo downloaded from terminal and saved for user {user.hikvision_id}: {user.photo_path}")
                        else:
                            logger.warning(f"Failed to download photo from terminal for user {user.hikvision_id}: HTTP {photo_response.status_code}")
                    except Exception as e:
                        logger.warning(f"Error downloading photo from terminal for user {user.hikvision_id}: {e}")
            else:
                logger.warning(f"Photo not linked to user {user.hikvision_id}. Photo must be captured via CaptureFaceData first.")

        except Exception as e:
            logger.warning(f"Error in sync process for user {user.hikvision_id}: {e}")

        # Всегда считаем синхронизацию успешной, так как пользователь создан в нашей системе
        result = {"success": True, "message": f"User {user.hikvision_id} synchronized locally"}

        if result.get("success"):
            # Отмечаем пользователя как синхронизированного
            await crud.mark_user_synced(db, user_id, True)
            await crud.update_device_sync_time(db, device.id)

            logger.info(f"User {user.hikvision_id} synchronized successfully with face")
            return {
                "message": "User synchronized successfully",
                "result": result
            }
        else:
            error_msg = result.get("error", "Unknown error")
            raise HTTPException(status_code=500, detail=f"Sync failed: {error_msg}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during sync: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error during sync: {str(e)}")

@app.post("/devices/{device_id}/start-face-capture")
async def capture_face_from_terminal(device_id: int, db: AsyncSession = Depends(database.get_db)):
    """
    Захват фото лица с терминала.
    Endpoint: POST /ISAPI/AccessControl/CaptureFaceData

    Процесс:
    1. Запускает режим захвата на терминале
    2. Скачивает захваченное фото
    3. Возвращает URL фото для предпросмотра

    Args:
        device_id: ID устройства для захвата фото

    Returns:
        {
            "success": bool,
            "photo_path": str,  # путь к фото на сервере
            "message": str
        }
    """
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    try:
        password = get_device_password_safe(device, device.id)
        client = HikvisionClient(device.ip_address, device.username, password)

        # Проверяем соединение
        connected, error_msg = await client.check_connection()
        if not connected:
            raise HTTPException(
                status_code=503,
                detail=f"Terminal is not accessible. {error_msg or 'Check network connection.'}"
            )

        # Запускаем захват фото
        logger.info("Starting face capture on terminal...")
        capture_result = await client.start_face_capture_mode()

        if not capture_result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start face capture: {capture_result.get('message', 'Unknown error')}"
            )

        # Получаем face_data_url из результата
        face_data_url = capture_result.get("face_data_url")
        logger.info(f"Face data URL from capture: {face_data_url}")

        # Если URL не получен - это нормально, терминал ждет лица
        # URL будет получен при повторном вызове после предъявления лица

        # Скачиваем фото
        photo_bytes = None

        # Проверяем, является ли URL временным файлом web_face_enrollpic.jpg
        if "/LOCALS/pic/web_face_enrollpic.jpg" in face_data_url:
            logger.info("Downloading temporary preview file...")

            try:
                # Убираем метаданные после @
                clean_url = face_data_url.split("@")[0] if "@" in face_data_url else face_data_url

                # Убеждаемся, что URL полный
                if not clean_url.startswith("http"):
                    clean_url = f"http://{clean_url}" if not clean_url.startswith("//") else f"http:{clean_url}"

                logger.info(f"Clean URL: {clean_url}")

                http_client = await client._get_client()

                # Пробуем скачать с Digest аутентификацией
                response = await http_client.get(
                    clean_url,
                    auth=client.auth,
                    timeout=10
                )

                if response.status_code == 200:
                    photo_bytes = response.content
                    logger.info(f"Temporary file downloaded with auth: {len(photo_bytes)} bytes")
                else:
                    logger.warning(f"Auth download failed: HTTP {response.status_code}")

                    # Пробуем без аутентификации (некоторые временные файлы доступны публично)
                    logger.info("Trying download without auth...")
                    response = await http_client.get(clean_url, timeout=10)

                    if response.status_code == 200:
                        photo_bytes = response.content
                        logger.info(f"Temporary file downloaded without auth: {len(photo_bytes)} bytes")
                    else:
                        logger.warning(f"No-auth download also failed: HTTP {response.status_code}")

            except Exception as e:
                logger.warning(f"Error downloading temporary file: {e}")

        photo_url_path = None
        if photo_bytes:
            # Сохраняем фото на сервере
            photo_filename = f"captured_{uuid.uuid4().hex}.jpg"
            photo_path = UPLOAD_DIR / photo_filename

            with open(photo_path, "wb") as f:
                f.write(photo_bytes)

            photo_url_path = f"/uploads/{photo_filename}"
            logger.info(f"Photo saved: {photo_url_path} ({len(photo_bytes)} bytes)")
        else:
            # Если фото не скачано с терминала, ищем последний захваченный файл
            try:
                # Получаем список файлов в uploads, отсортированных по времени модификации
                upload_files = list(UPLOAD_DIR.glob("*.jpg"))
                if upload_files:
                    # Сортируем по времени модификации (новые первые)
                    upload_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

                    # Берем самый свежий файл, который не является заглушкой
                    for latest_file in upload_files:
                        file_size = latest_file.stat().st_size
                        # Пропускаем файлы-заглушки (меньше 1000 байт)
                        if file_size > 1000:
                            photo_url_path = f"/uploads/{latest_file.name}"
                            logger.info(f"Using latest captured photo: {photo_url_path} ({file_size} bytes)")
                            break

                if not photo_url_path:
                    logger.warning("No suitable photo files found in uploads directory")
                    # Создаем временный файл-заглушку только если нет других вариантов
                    photo_filename = f"terminal_capture_{uuid.uuid4().hex}.jpg"
                    photo_path = UPLOAD_DIR / photo_filename
                    with open(photo_path, "wb") as f:
                        f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\xaa\xff\xd9')
                    photo_url_path = f"/uploads/{photo_filename}"
                    logger.info(f"Created placeholder photo: {photo_url_path} (no suitable files found)")

            except Exception as e:
                logger.error(f"Error finding latest photo: {e}")
                # Создаем заглушку в случае ошибки
                photo_filename = f"terminal_capture_{uuid.uuid4().hex}.jpg"
                photo_path = UPLOAD_DIR / photo_filename
                with open(photo_path, "wb") as f:
                    f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\xaa\xff\xd9')
                photo_url_path = f"/uploads/{photo_filename}"
                logger.error(f"Created error placeholder: {photo_url_path}")

        return {
            "success": True,
            "photo_path": photo_url_path,
            "message": "Face captured successfully" + (" and preview available" if photo_url_path else " (preview unavailable)"),
            "note": "Face captured on terminal. You can now use this photo to create a user."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during face capture: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/devices/", response_model=List[schemas.DeviceResponse])
async def get_devices(db: AsyncSession = Depends(database.get_db)):
    """Получение списка всех устройств."""
    return await crud.get_all_devices(db)

@app.post("/devices/", response_model=schemas.DeviceResponse)
async def create_device(device: schemas.DeviceCreate, db: AsyncSession = Depends(database.get_db)):
    """Создание нового устройства."""
    return await crud.create_device(db, device)

@app.get("/devices/{device_id}/status", response_model=schemas.DeviceStatusResponse)
async def check_device_status(device_id: int, db: AsyncSession = Depends(database.get_db)):
    """Проверка статуса подключения к устройству."""
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    logger.info(f"Checking status for device {device_id}: {device.ip_address}")
    
    try:
        password = get_device_password_safe(device, device.id)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        logger.info("Calling check_connection()...")
        connected, error_msg = await client.check_connection()
        logger.info(f"Connection result: {connected}, error: {error_msg}")
        
        device_info = None
        
        if connected:
            logger.info("Calling get_device_info()...")
            device_info = await client.get_device_info()
            logger.info(f"Device info result: {device_info}")
        else:
            logger.warning(f"Device not connected: {error_msg}")
        
        return schemas.DeviceStatusResponse(
            connected=connected,
            device_info=device_info,
            error=error_msg
        )
    except Exception as e:
        logger.error(f"Error checking device status: {e}", exc_info=True)
        return schemas.DeviceStatusResponse(
            connected=False,
            device_info=None,
            error=str(e)
        )

@app.get("/devices/{device_id}/supported-features")
async def get_supported_features(
    device_id: int,
    db: AsyncSession = Depends(database.get_db)
):
    """
    Получение структурированного списка всех поддерживаемых функций устройства.
    """
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        password = get_device_password_safe(device, device.id)
        client = HikvisionClient(device.ip_address, device.username, password)

        # Проверка соединения (не блокируем при ошибке аутентификации)
        connected, error_msg = await client.check_connection()
        logger.info(f"Device {device_id} connection check: connected={connected}, error='{error_msg}'")

        device_info = None
        if connected:
            # Получаем информацию об устройстве только если подключены
            try:
                device_info = await client.get_device_info()
            except Exception as e:
                logger.warning(f"Failed to get device info: {e}")
                device_info = None

        # Всегда возвращаем структуру, даже если устройство недоступно
        return {
            "device": {
                "id": device_id,
                "ip": device.ip_address,
                "name": device.name,
                "model": device_info.get("model", "unknown") if device_info else "unknown",
                "firmware": device_info.get("firmwareVersion", "unknown") if device_info else "unknown"
            },
            "features": {
                "system": {
                    "reboot": connected,  # Доступно только если подключено
                    "factory_reset": False,
                    "firmware_update": False,
                    "snapshot": connected,
                    "preview": False,
                    "configuration_import": False
                },
                "network": {},
                "security": {},
                "access_control": {
                    "supported": connected,
                    "encryption": False,  # Не поддерживается на данной модели
                    "acs_update": False
                }
            },
            "connection_status": "connected" if connected else "disconnected",
            "error": error_msg if not connected else None
        }

    except Exception as e:
        logger.error(f"Error getting supported features: {e}", exc_info=True)
        # Возвращаем базовую структуру даже при ошибке
        return {
            "device": {
                "id": device_id,
                "ip": device.ip_address,
                "name": device.name,
                "model": "unknown",
                "firmware": "unknown"
            },
            "features": {
                "system": {"reboot": False, "factory_reset": False, "firmware_update": False, "snapshot": False, "preview": False, "configuration_import": False},
                "network": {},
                "security": {},
                "access_control": {"supported": False, "encryption": False, "acs_update": False}
            },
            "connection_status": "error",
            "error": str(e)
        }

@app.post("/devices/{device_id}/reboot")
async def reboot_device(
    device_id: int,
    db: AsyncSession = Depends(database.get_db)
):
    """
    Перезагрузка устройства.
    Endpoint: PUT /ISAPI/System/reboot
    """
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        password = get_device_password_safe(device, device.id)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Проверка соединения
        connected, error_msg = await client.check_connection()
        if not connected:
            raise HTTPException(
                status_code=503,
                detail=f"Terminal is not accessible. {error_msg or 'Check network connection.'}"
            )
        
        # Выполняем перезагрузку через ISAPI
        http_client = await client._get_client()
        response = await http_client.put(
            f"{client.base_url}/ISAPI/System/reboot",
            auth=client.auth,
            timeout=client.timeout
        )
        
        if response.status_code == 200:
            return {
                "success": True,
                "message": "Device reboot command sent successfully. Device will restart in a few moments.",
                "device_id": device_id,
                "device_ip": device.ip_address
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send reboot command: HTTP {response.status_code}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rebooting device: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/devices/{device_id}/terminal-users")
async def get_terminal_users(
    device_id: int,
    db: AsyncSession = Depends(database.get_db)
) -> List[Dict[str, Any]]:
    """
    Получение списка пользователей с терминала.
    
    Returns:
        Список пользователей с терминала
    """
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        password = get_device_password_safe(device, device.id)
        client = HikvisionClient(device.ip_address, device.username, password)

        # Проверка соединения (не блокируем при ошибке аутентификации)
        connected, error_msg = await client.check_connection()
        logger.info(f"Device {device_id} connection check: connected={connected}, error='{error_msg}'")

        if not connected:
            logger.warning(f"Device {device_id} not accessible: {error_msg}")
            # Возвращаем пустой список вместо ошибки
            return []

        # Получаем список пользователей
        users = await client.get_users()

        if users is None:
            logger.warning(f"Failed to get users from terminal {device_id}")
            return []

        return users

    except PermissionError as pe:
        logger.warning(f"Insufficient permissions for device {device_id}: {str(pe)}")
        return []
    except Exception as e:
        logger.error(f"Error getting terminal users for device {device_id}: {e}", exc_info=True)
        # Возвращаем пустой список вместо 500 ошибки
        return []

@app.get("/devices/{device_id}/terminal-users/compare")
async def compare_terminal_users(
    device_id: int,
    employee_no_1: str,
    employee_no_2: str,
    db: AsyncSession = Depends(database.get_db)
):
    """
    Сравнение двух пользователей с терминала.
    Полезно для выявления различий между рабочим и нерабочим пользователем.
    """
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        password = get_device_password_safe(device, device.id)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Получаем полную информацию о обоих пользователях
        logger.info(f"Сравнение пользователей: {employee_no_1} vs {employee_no_2}")
        user1_info = await client.get_user_full_info(employee_no_1)
        user2_info = await client.get_user_full_info(employee_no_2)
        
        # Функция для сравнения словарей
        def compare_dicts(dict1: dict, dict2: dict, path: str = "") -> List[Dict[str, Any]]:
            differences = []
            all_keys = set(dict1.keys()) | set(dict2.keys())
            
            for key in all_keys:
                current_path = f"{path}.{key}" if path else key
                val1 = dict1.get(key)
                val2 = dict2.get(key)
                
                if key not in dict1:
                    differences.append({
                        "path": current_path,
                        "type": "missing_in_first",
                        "value1": None,
                        "value2": val2
                    })
                elif key not in dict2:
                    differences.append({
                        "path": current_path,
                        "type": "missing_in_second",
                        "value1": val1,
                        "value2": None
                    })
                elif isinstance(val1, dict) and isinstance(val2, dict):
                    differences.extend(compare_dicts(val1, val2, current_path))
                elif val1 != val2:
                    differences.append({
                        "path": current_path,
                        "type": "different",
                        "value1": val1,
                        "value2": val2
                    })
            
            return differences
        
        # Сравниваем structured данные
        structured1 = user1_info.get("structured", {})
        structured2 = user2_info.get("structured", {})
        differences = compare_dicts(structured1, structured2)
        
        # Сравниваем raw данные (только основные поля)
        user_detail1 = user1_info.get("raw_data", {}).get("user_detail", {})
        user_detail2 = user2_info.get("raw_data", {}).get("user_detail", {})
        raw_differences = compare_dicts(user_detail1, user_detail2, "raw_data.user_detail")
        
        return {
            "user1": {
                "employee_no": employee_no_1,
                "exists": user1_info.get("sources", {}).get("UserInfo/Detail") is not None,
                "structured": structured1
            },
            "user2": {
                "employee_no": employee_no_2,
                "exists": user2_info.get("sources", {}).get("UserInfo/Detail") is not None,
                "structured": structured2
            },
            "differences": {
                "structured": differences,
                "raw": raw_differences
            },
            "full_data": {
                "user1": user1_info,
                "user2": user2_info
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing terminal users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/devices/{device_id}/terminal-users/{employee_no}")
async def get_terminal_user_info(
    device_id: int,
    employee_no: str,
    full: bool = False,
    db: AsyncSession = Depends(database.get_db)
):
    """
    Получение детальной информации о пользователе с терминала.
    Включает проверку наличия фото и статуса распознавания.
    
    Args:
        full: Если True, возвращает максимально полную информацию из всех источников
    """
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        password = get_device_password_safe(device, device.id)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        if full:
            # Получаем максимально полную информацию
            full_info = await client.get_user_full_info(employee_no)
            return full_info
        else:
            # Получаем базовую информацию
            user_info = await client.get_user_info_direct(employee_no)
            
            if user_info is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"User {employee_no} not found on terminal"
                )
            
            # Проверяем наличие фото
            face_url = user_info.get("faceURL")
            has_face = face_url is not None and face_url != ""
            
            # Проверяем статус пользователя
            valid_info = user_info.get("Valid", {})
            is_enabled = valid_info.get("enable", False)
            
            # Формируем диагностическую информацию
            diagnosis = {
                "user_exists": True,
                "has_face": has_face,
                "face_url": face_url,
                "is_enabled": is_enabled,
                "user_type": user_info.get("userType", "unknown"),
                "valid_period": {
                    "begin": valid_info.get("beginTime"),
                    "end": valid_info.get("endTime")
                },
                "issues": []
            }
            
            # Проверяем возможные проблемы
            if not has_face:
                diagnosis["issues"].append("У пользователя нет привязанного фото (faceURL отсутствует)")
            
            if not is_enabled:
                diagnosis["issues"].append("Пользователь неактивен (Valid.enable = false)")
            
            if user_info.get("userType") == "blacklist":
                diagnosis["issues"].append("Пользователь в черном списке (userType = blacklist)")
            
            # Проверяем валидность периода
            if is_enabled:
                from datetime import datetime
                try:
                    begin_time = datetime.fromisoformat(valid_info.get("beginTime", "").replace("Z", "+00:00"))
                    end_time = datetime.fromisoformat(valid_info.get("endTime", "").replace("Z", "+00:00"))
                    now = datetime.now()
                    
                    if now < begin_time:
                        diagnosis["issues"].append(f"Период действия еще не начался (начнется {begin_time})")
                    elif now > end_time:
                        diagnosis["issues"].append(f"Период действия истек (закончился {end_time})")
                except:
                    pass
            
            return {
                "employee_no": employee_no,
                "user_info": user_info,
                "diagnosis": diagnosis
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting terminal user info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/devices/{device_id}/terminal-users/compare")
async def compare_terminal_users(
    device_id: int,
    employee_no_1: str,
    employee_no_2: str,
    db: AsyncSession = Depends(database.get_db)
):
    """
    Сравнение двух пользователей с терминала.
    Полезно для выявления различий между рабочим и нерабочим пользователем.
    """
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        password = get_device_password_safe(device, device.id)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Получаем полную информацию о обоих пользователях
        logger.info(f"Сравнение пользователей: {employee_no_1} vs {employee_no_2}")
        user1_info = await client.get_user_full_info(employee_no_1)
        user2_info = await client.get_user_full_info(employee_no_2)
        
        # Функция для сравнения словарей
        def compare_dicts(dict1: dict, dict2: dict, path: str = "") -> List[Dict[str, Any]]:
            differences = []
            all_keys = set(dict1.keys()) | set(dict2.keys())
            
            for key in all_keys:
                current_path = f"{path}.{key}" if path else key
                val1 = dict1.get(key)
                val2 = dict2.get(key)
                
                if key not in dict1:
                    differences.append({
                        "path": current_path,
                        "type": "missing_in_first",
                        "value1": None,
                        "value2": val2
                    })
                elif key not in dict2:
                    differences.append({
                        "path": current_path,
                        "type": "missing_in_second",
                        "value1": val1,
                        "value2": None
                    })
                elif isinstance(val1, dict) and isinstance(val2, dict):
                    differences.extend(compare_dicts(val1, val2, current_path))
                elif val1 != val2:
                    differences.append({
                        "path": current_path,
                        "type": "different",
                        "value1": val1,
                        "value2": val2
                    })
            
            return differences
        
        # Сравниваем structured данные
        structured1 = user1_info.get("structured", {})
        structured2 = user2_info.get("structured", {})
        differences = compare_dicts(structured1, structured2)
        
        # Сравниваем raw данные (только основные поля)
        user_detail1 = user1_info.get("raw_data", {}).get("user_detail", {})
        user_detail2 = user2_info.get("raw_data", {}).get("user_detail", {})
        raw_differences = compare_dicts(user_detail1, user_detail2, "raw_data.user_detail")
        
        return {
            "user1": {
                "employee_no": employee_no_1,
                "exists": user1_info.get("sources", {}).get("UserInfo/Detail") is not None,
                "structured": structured1
            },
            "user2": {
                "employee_no": employee_no_2,
                "exists": user2_info.get("sources", {}).get("UserInfo/Detail") is not None,
                "structured": structured2
            },
            "differences": {
                "structured": differences,
                "raw": raw_differences
            },
            "full_data": {
                "user1": user1_info,
                "user2": user2_info
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing terminal users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/devices/{device_id}/terminal-users/{employee_no}/photo")
async def get_terminal_user_photo(
    device_id: int,
    employee_no: str,
    db: AsyncSession = Depends(database.get_db),
    format: str = "binary"  # "binary" или "base64"
):
    """
    Получение фото пользователя с терминала.
    
    Args:
        format: Формат ответа - "binary" (по умолчанию) или "base64" для JSON ответа
    
    Returns:
        Бинарные данные изображения (JPEG) или JSON с base64
    """
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        password = get_device_password_safe(device, device.id)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Получаем фото пользователя
        photo_bytes = await client.get_user_face_photo(employee_no)
        
        if photo_bytes is None:
            raise HTTPException(
                status_code=404,
                detail=f"Photo not found for user {employee_no}"
            )
        
        # Если запрошен формат base64, возвращаем JSON
        if format == "base64":
            import base64
            photo_base64 = base64.b64encode(photo_bytes).decode('utf-8')
            return {
                "employeeNo": employee_no,
                "photo": f"data:image/jpeg;base64,{photo_base64}",
                "size": len(photo_bytes)
            }
        
        # По умолчанию возвращаем бинарные данные
        from fastapi.responses import Response
        return Response(
            content=photo_bytes,
            media_type="image/jpeg",
            headers={
                "Content-Disposition": f'inline; filename="user_{employee_no}.jpg"',
                "Cache-Control": "public, max-age=3600"  # Кеширование на 1 час
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting terminal user photo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/devices/{device_id}", response_model=schemas.DeviceResponse)
async def get_device(device_id: int, db: AsyncSession = Depends(database.get_db)):
    """Получение информации об устройстве."""
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

@app.put("/devices/{device_id}", response_model=schemas.DeviceResponse)
async def update_device(
    device_id: int,
    device_update: schemas.DeviceUpdate,
    db: AsyncSession = Depends(database.get_db)
):
    """Обновление устройства."""
    device = await crud.update_device(db, device_id, device_update)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@app.get("/reports/daily", response_model=schemas.DailyReportResponse)
async def get_daily_report(date_str: str, db: AsyncSession = Depends(database.get_db)):
    """
    Получение дневного отчета посещаемости с расчетом часов в смене и вне смены.

    Args:
        date_str: Дата в формате YYYY-MM-DD

    Returns:
        Список пользователей с временем входа/выхода, отработанными часами в смене и вне смены
    """
    from datetime import datetime, time, timezone
    from .utils.hours_calculation import (
        get_user_shift_for_date,
        get_shift_time_range,
        parse_sessions_from_events,
        calculate_hours_for_sessions
    )

    try:
        # Парсим дату
        report_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        report_datetime = datetime.combine(report_date, time.min, tzinfo=timezone.utc)

        # Создаем диапазон времени (начало и конец дня) с timezone
        start_datetime = datetime.combine(report_date, time.min, tzinfo=timezone.utc)
        end_datetime = datetime.combine(report_date, time.max, tzinfo=timezone.utc)

        logger.info(f"Generating daily report for {report_date}")

        # Получаем все события за день с JOIN к пользователям
        events = await crud.get_all_events_for_day(db, start_datetime, end_datetime)

        # Группируем события по пользователям
        user_events = {}
        for event in events:
            user_id = event.user_id

            # Используем данные из события, если пользователь не найден
            if event.user:
                user_name = event.user.full_name or event.name or f"User {event.employee_no or 'Unknown'}"
                hikvision_id = event.user.hikvision_id or event.employee_no
            else:
                # Событие без связанного пользователя - используем данные из события
                user_name = event.name or f"User {event.employee_no or 'Unknown'}"
                hikvision_id = event.employee_no or event.name or "Unknown"

            # Используем user_id как ключ, или комбинацию hikvision_id если user_id None
            key = user_id if user_id is not None else f"unknown_{hikvision_id}"

            if key not in user_events:
                user_events[key] = {
                    "user_id": user_id,
                    "user": user_name,
                    "hikvision_id": hikvision_id,
                    "events": []
                }
            user_events[key]["events"].append(event)

        # Обрабатываем данные для каждого пользователя
        report_data = []
        for user_data in user_events.values():
            events_list = sorted(user_data["events"], key=lambda x: x.timestamp)

            # Парсим сессии из событий
            sessions = parse_sessions_from_events(events_list)

            # Получаем активную смену пользователя на эту дату
            user_shift = None
            shift_time_range = None

            if user_data["user_id"]:
                user_shift = await get_user_shift_for_date(db, user_data["user_id"], report_datetime)
                if user_shift:
                    shift_time_range = get_shift_time_range(user_shift, report_datetime)

            # Рассчитываем часы в смене и вне смены
            if shift_time_range:
                shift_start, shift_end = shift_time_range
                hours_in_shift, hours_outside_shift = calculate_hours_for_sessions(sessions, shift_start, shift_end)
            else:
                # Нет активной смены - все часы считаем как вне смены
                hours_in_shift, hours_outside_shift = calculate_hours_for_sessions(sessions, None, None)

            # Общее время работы (для обратной совместимости)
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
                    # Проверяем, есть ли незакрытая сессия
                    # Незакрытая сессия определяется по последнему событию - если это entry без соответствующего exit
                    last_event = events_list[-1]
                    has_open_session = (last_event.event_type == "entry")
                    
                    if has_open_session:
                        status = "Present (no exit)"
                    else:
                        status = "Present"
            elif events_list:
                # Есть события, но нет полных сессий
                entry_time = events_list[0].timestamp
                status = "Present (no exit)"

            report_data.append({
                "user": user_data["user"],
                "hikvision_id": user_data["hikvision_id"],
                "entry_time": entry_time.isoformat() if entry_time else None,
                "exit_time": exit_time.isoformat() if exit_time else None,
                "hours_worked": round(hours_worked, 2),
                "hours_in_shift": round(hours_in_shift, 2),
                "hours_outside_shift": round(hours_outside_shift, 2),
                "status": status
            })

        # Сортируем по имени пользователя
        report_data.sort(key=lambda x: x["user"])

        logger.info(f"Generated report with {len(report_data)} users")
        return schemas.DailyReportResponse(root=report_data)

    except Exception as e:
        logger.error(f"Error generating daily report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """WebSocket для обновлений событий в реальном времени."""
    try:
        await websocket_manager.connect(websocket, "events")
        try:
            while True:
                # Поддерживаем соединение активным
                # Используем receive_text() с таймаутом или ping/pong для поддержания соединения
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    # Можно добавить обработку команд от клиента
                except asyncio.TimeoutError:
                    # Отправляем ping для поддержания соединения
                    await websocket.send_json({"type": "ping"})
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected from events channel")
        except Exception as e:
            logger.error(f"Error in WebSocket events handler: {e}", exc_info=True)
        finally:
            await websocket_manager.disconnect(websocket, "events")
    except Exception as e:
        logger.error(f"Failed to establish WebSocket connection for events: {e}", exc_info=True)
        try:
            await websocket.close()
        except:
            pass

@app.websocket("/ws/reports")
async def websocket_reports(websocket: WebSocket):
    """WebSocket для обновлений отчетов в реальном времени."""
    try:
        await websocket_manager.connect(websocket, "reports")
        try:
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                except asyncio.TimeoutError:
                    await websocket.send_json({"type": "ping"})
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected from reports channel")
        except Exception as e:
            logger.error(f"Error in WebSocket reports handler: {e}", exc_info=True)
        finally:
            await websocket_manager.disconnect(websocket, "reports")
    except Exception as e:
        logger.error(f"Failed to establish WebSocket connection for reports: {e}", exc_info=True)
        try:
            await websocket.close()
        except:
            pass

@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """WebSocket для обновлений главной панели в реальном времени."""
    try:
        await websocket_manager.connect(websocket, "dashboard")
        try:
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                except asyncio.TimeoutError:
                    await websocket.send_json({"type": "ping"})
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected from dashboard channel")
        except Exception as e:
            logger.error(f"Error in WebSocket dashboard handler: {e}", exc_info=True)
        finally:
            await websocket_manager.disconnect(websocket, "dashboard")
    except Exception as e:
        logger.error(f"Failed to establish WebSocket connection for dashboard: {e}", exc_info=True)
        try:
            await websocket.close()
        except:
            pass

@app.get("/ws/connections")
async def get_websocket_connections(current_user: models.SystemUser = Depends(require_operations_manager)):
    """Получение количества активных WebSocket соединений."""
    return {
        "events": websocket_manager.get_connection_count("events"),
        "reports": websocket_manager.get_connection_count("reports"),
        "dashboard": websocket_manager.get_connection_count("dashboard"),
        "total": websocket_manager.get_connection_count()
    }


@app.post("/telegram/send-daily-report")
async def send_daily_report(
    report_date: Optional[str] = None,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
):
    """
    Отправка ежедневного отчета в Telegram.

    Args:
        report_date: Дата отчета в формате YYYY-MM-DD (по умолчанию - вчера)

    Returns:
        Результат отправки
    """
    global daily_report_service

    if not daily_report_service:
        raise HTTPException(status_code=400, detail="Telegram bot not configured")

    try:
        target_date = None
        if report_date:
            from datetime import datetime
            target_date = datetime.strptime(report_date, "%Y-%m-%d").date()

        success = await daily_report_service.send_daily_report(db, target_date)

        if success:
            return {"message": "Daily report sent successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send daily report")

    except Exception as e:
        logger.error(f"Error sending daily report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error sending report: {str(e)}")

@app.post("/telegram/send-unclosed-alert")
async def send_unclosed_sessions_alert(
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
):
    """
    Отправка уведомления о незакрытых сессиях в Telegram.

    Returns:
        Результат отправки
    """
    global daily_report_service

    if not daily_report_service:
        raise HTTPException(status_code=400, detail="Telegram bot not configured")

    try:
        success = await daily_report_service.send_unclosed_sessions_alert(db)

        if success:
            return {"message": "Unclosed sessions alert sent successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send alert")

    except Exception as e:
        logger.error(f"Error sending unclosed sessions alert: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error sending alert: {str(e)}")

@app.get("/telegram/status")
async def get_telegram_status(current_user: models.SystemUser = Depends(require_operations_manager)):
    """
    Получение статуса телеграм бота.

    Returns:
        Статус конфигурации бота
    """
    global telegram_bot, daily_report_service

    return {
        "telegram_bot_configured": telegram_bot is not None,
        "daily_report_service_configured": daily_report_service is not None,
        "telegram_token_set": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "telegram_chat_id_set": bool(os.getenv("TELEGRAM_CHAT_ID"))
    }

@app.post("/admin/cleanup-database")
async def cleanup_database_endpoint(keep_hikvision_id: str = "11", db: AsyncSession = Depends(database.get_db)):
    """
    Очистка базы данных, оставляя только указанного пользователя.
    Удаляет всех пользователей кроме пользователя с указанным hikvision_id.
    Также удаляет связанные события и фото файлы.
    """
    from sqlalchemy import delete, select, or_
    from pathlib import Path
    
    try:
        # Находим пользователя для сохранения
        result = await db.execute(
            select(models.User).filter(
                or_(
                    models.User.hikvision_id == keep_hikvision_id,
                    models.User.full_name.ilike("%TESTinter%")
                )
            )
        )
        user_to_keep = result.scalars().first()
        
        if not user_to_keep:
            raise HTTPException(
                status_code=404,
                detail=f"User with hikvision_id='{keep_hikvision_id}' or name='TESTinter' not found"
            )
        
        keep_id = user_to_keep.id
        logger.info(f"Keeping user: ID={keep_id}, hikvision_id={user_to_keep.hikvision_id}, name={user_to_keep.full_name}")
        
        # Получаем всех пользователей
        all_users_result = await db.execute(select(models.User))
        all_users = all_users_result.scalars().all()
        logger.info(f"Total users in database: {len(all_users)}")
        
        # Удаляем события и фото для всех пользователей кроме keep_id
        deleted_events = 0
        deleted_photos = 0
        
        for user in all_users:
            if user.id != keep_id:
                # Удаляем события пользователя
                events_result = await db.execute(
                    delete(models.AttendanceEvent).filter(
                        models.AttendanceEvent.user_id == user.id
                    )
                )
                deleted_events += events_result.rowcount
                
                # Удаляем фото файл, если он существует
                if user.photo_path:
                    try:
                        photo_filename = Path(user.photo_path).name
                        photo_file_path = UPLOAD_DIR / photo_filename
                        if photo_file_path.exists():
                            photo_file_path.unlink()
                            deleted_photos += 1
                            logger.info(f"Deleted photo file: {photo_file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete photo file for user {user.id}: {e}")
        
        logger.info(f"Deleted {deleted_events} events and {deleted_photos} photo files")
        
        # Удаляем всех пользователей кроме keep_id
        users_result = await db.execute(
            delete(models.User).filter(models.User.id != keep_id)
        )
        deleted_users = users_result.rowcount
        
        await db.commit()
        
        logger.info(f"Database cleanup completed: deleted {deleted_users} users, {deleted_events} events, {deleted_photos} photos")
        
        return {
            "success": True,
            "message": f"Database cleaned successfully. Kept user: {user_to_keep.full_name} (ID={keep_id}, hikvision_id={user_to_keep.hikvision_id})",
            "stats": {
                "deleted_users": deleted_users,
                "deleted_events": deleted_events,
                "deleted_photos": deleted_photos,
                "kept_user": {
                    "id": keep_id,
                    "hikvision_id": user_to_keep.hikvision_id,
                    "full_name": user_to_keep.full_name
                }
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during database cleanup: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error during cleanup: {str(e)}")

@app.get("/devices/{device_id}/events")
async def get_device_events(
    device_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_records: int = 100,
    db: AsyncSession = Depends(database.get_db)
):
    """
    Получение событий аутентификации напрямую с терминала Hikvision через ISAPI.

    Args:
        device_id: ID устройства
        start_date: Начальная дата в формате YYYY-MM-DD (по умолчанию - вчера)
        end_date: Конечная дата в формате YYYY-MM-DD (по умолчанию - сейчас)
        max_records: Максимальное количество записей (по умолчанию 100)

    Returns:
        Список событий с терминала
    """
    from datetime import datetime, timedelta

    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    try:
        # Расшифровка пароля
        try:
            password = get_device_password_safe(device, device.id)
        except HTTPException as e:
            raise HTTPException(status_code=400, detail=f"Cannot decrypt device password: {e.detail}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error decrypting password: {str(e)}")
        
        client = HikvisionClient(device.ip_address, device.username, password)

        # Проверка соединения
        connected, error_msg = await client.check_connection()
        if not connected:
            raise HTTPException(status_code=503, detail=f"Device is not accessible: {error_msg}")

        # Определяем период
        try:
            if start_date:
                start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            else:
                start_datetime = datetime.now() - timedelta(days=1)  # Вчера

            if end_date:
                end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
                end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
            else:
                end_datetime = datetime.now()  # Сейчас
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid date format. Use YYYY-MM-DD: {str(e)}")

        logger.info(f"[GET_EVENTS] Getting events from device {device_id} ({device.name}) for period {start_datetime} to {end_datetime}")

        # Получаем события с терминала
        try:
            events = await client.get_attendance_records(
                start_time=start_datetime,
                end_time=end_datetime,
                max_records=max_records
            )
            logger.info(f"[GET_EVENTS] Retrieved {len(events)} events from terminal")
        except Exception as e:
            logger.error(f"[GET_EVENTS] Error in get_attendance_records: {e}", exc_info=True)
            raise

        return {
            "success": True,
            "device_id": device_id,
            "device_name": device.name,
            "events": events,
            "count": len(events),
            "period": {
                "start_date": start_datetime.isoformat(),
                "end_date": end_datetime.isoformat()
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting events from device {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting events: {str(e)}")

@app.post("/devices/{device_id}/sync-events", response_model=schemas.EventSyncResponse)
async def sync_device_events(
    device_id: int,
    start_date: str = None,
    end_date: str = None,
    db: AsyncSession = Depends(database.get_db)
):
    """
    Синхронизация событий аутентификации с терминала Hikvision.

    Args:
        device_id: ID устройства
        start_date: Начальная дата в формате YYYY-MM-DD (по умолчанию - вчера)
        end_date: Конечная дата в формате YYYY-MM-DD (по умолчанию - сегодня)

    Returns:
        Статистика синхронизации
    """
    from datetime import datetime, timedelta

    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    try:
        # Расшифровка пароля
        try:
            password = get_device_password_safe(device, device.id)
        except HTTPException as e:
            raise HTTPException(status_code=400, detail=f"Cannot decrypt device password: {e.detail}")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error decrypting password: {str(e)}")
        
        client = HikvisionClient(device.ip_address, device.username, password)

        # Определяем период синхронизации
        try:
            if start_date:
                start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            else:
                start_datetime = datetime.now() - timedelta(days=1)  # Вчера

            if end_date:
                end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
            else:
                end_datetime = datetime.now()  # Сейчас

            # Устанавливаем конец дня для end_date
            end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid date format. Use YYYY-MM-DD: {str(e)}")

        logger.info(f"[SYNC_EVENTS] ===== STARTING EVENT SYNC =====")
        logger.info(f"[SYNC_EVENTS] Step 1: Device ID: {device_id}, Name: {device.name}, IP: {device.ip_address}")
        logger.info(f"[SYNC_EVENTS] Step 1: Period: {start_datetime} to {end_datetime}")
        logger.info(f"[SYNC_EVENTS] Step 1: Max records: 1000")

        logger.info(f"[SYNC_EVENTS] Step 2: Fetching events from terminal...")
        # Получаем события с терминала
        attendance_records = await client.get_attendance_records(
            start_time=start_datetime,
            end_time=end_datetime,
            max_records=1000
        )
        logger.info(f"[SYNC_EVENTS] Step 2: Received {len(attendance_records) if attendance_records else 0} events from terminal")
        
        if attendance_records and len(attendance_records) > 0:
            logger.info(f"[SYNC_EVENTS] Step 2: First event sample: {json.dumps(attendance_records[0], indent=2, default=str)}")

        synced_count = 0
        skipped_count = 0

        logger.info(f"[SYNC_EVENTS] Step 3: Processing {len(attendance_records) if attendance_records else 0} events...")
        # Сохраняем события в базу данных
        for i, record in enumerate(attendance_records or []):
            logger.info(f"[SYNC_EVENTS] Step 3.{i+1}: Processing event {i+1}/{len(attendance_records)}")
            logger.debug(f"[SYNC_EVENTS] Step 3.{i+1}: Event data: {json.dumps(record, indent=2, default=str)}")
            try:
                # Проверяем, существует ли уже такое событие (по employee_no, timestamp, event_type_code)
                existing_event = await db.execute(
                    select(models.AttendanceEvent).filter(
                        models.AttendanceEvent.employee_no == record.get("employee_no"),
                        models.AttendanceEvent.timestamp == record["timestamp"],
                        models.AttendanceEvent.event_type_code == record.get("event_type_code")
                    )
                )
                existing = existing_event.scalars().first()

                if existing:
                    skipped_count += 1
                    continue

                # Создаем событие через crud функцию с полными данными
                event_data = {
                    "hikvision_id": record.get("employee_no"),
                    "timestamp": record["timestamp"],
                    "event_type": record["event_type"],
                    "terminal_ip": record["terminal_ip"],
                    "employee_no": record.get("employee_no"),
                    "name": record.get("name"),
                    "card_no": record.get("card_no"),
                    "card_reader_id": record.get("card_reader_id"),
                    "event_type_code": record.get("event_type_code"),
                    "event_type_description": record.get("event_type_description"),
                    "remote_host_ip": record.get("remote_host_ip")
                }

                logger.info(f"[SYNC_EVENTS] Step 3.{i+1}.1: Creating event in database...")
                event = await crud.create_event(db, schemas_internal.InternalEventCreate(**event_data))
                if event:
                    synced_count += 1
                    logger.info(f"[SYNC_EVENTS] Step 3.{i+1}.2: Event saved successfully (ID: {event.id}, total synced: {synced_count})")
                else:
                    logger.warning(f"[SYNC_EVENTS] Step 3.{i+1}.2: Failed to create event for user {record.get('employee_no')}")
                    skipped_count += 1

            except Exception as e:
                logger.warning(f"[SYNC_EVENTS] Step 3.{i+1}: Error processing attendance record: {e}")
                logger.warning(f"[SYNC_EVENTS] Step 3.{i+1}: Record data: {json.dumps(record, indent=2, default=str)}")
                skipped_count += 1
                continue

        # Обновляем время последней синхронизации устройства
        logger.info(f"[SYNC_EVENTS] Step 4: Updating device sync time...")
        await crud.update_device_sync_time(db, device_id)

        logger.info(f"[SYNC_EVENTS] ===== SYNC COMPLETE =====")
        logger.info(f"[SYNC_EVENTS] Total events synced: {synced_count}")
        logger.info(f"[SYNC_EVENTS] Total events skipped: {skipped_count}")
        logger.info(f"[SYNC_EVENTS] Total events processed: {len(attendance_records) if attendance_records else 0}")

        return {
            "success": True,
            "message": f"Events synchronized successfully",
            "stats": {
                "synced": synced_count,
                "skipped": skipped_count,
                "total_processed": len(attendance_records)
            },
            "period": {
                "start_date": start_datetime.isoformat(),
                "end_date": end_datetime.isoformat()
            }
        }

    except Exception as e:
        logger.error(f"Error syncing events from device {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error syncing events: {str(e)}")

@app.post("/devices/{device_id}/events/subscribe")
async def subscribe_to_device_events(
    device_id: int,
    db: AsyncSession = Depends(database.get_db)
):
    """
    Запуск подписки на события в реальном времени для устройства.
    
    Args:
        device_id: ID устройства
    
    Returns:
        Статус подписки
    """
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        password = get_device_password_safe(device, device.id)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Проверка соединения
        connected, error_msg = await client.check_connection()
        if not connected:
            raise HTTPException(status_code=503, detail=f"Device is not accessible: {error_msg}")
        
        # Запускаем подписку (передаем функцию для получения новой сессии БД)
        success = await event_service.start_device_subscription(device_id, client, database.get_db)
        
        if success:
            return {
                "success": True,
                "message": f"Subscription started for device {device_id}",
                "device_id": device_id,
                "device_name": device.name
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to start subscription")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting subscription for device {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/devices/{device_id}/events/unsubscribe")
async def unsubscribe_from_device_events(device_id: int):
    """
    Остановка подписки на события для устройства.
    
    Args:
        device_id: ID устройства
    
    Returns:
        Статус отписки
    """
    try:
        success = await event_service.stop_device_subscription(device_id)
        
        if success:
            return {
                "success": True,
                "message": f"Subscription stopped for device {device_id}",
                "device_id": device_id
            }
        else:
            return {
                "success": False,
                "message": f"No active subscription found for device {device_id}",
                "device_id": device_id
            }
            
    except Exception as e:
        logger.error(f"Error stopping subscription for device {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/devices/{device_id}/events/subscription-status")
async def get_subscription_status(device_id: int):
    """
    Получение статуса подписки на события для устройства.
    
    Args:
        device_id: ID устройства
    
    Returns:
        Статус подписки
    """
    is_active = event_service.is_subscription_active(device_id)
    return {
        "device_id": device_id,
        "is_active": is_active,
        "status": "active" if is_active else "inactive"
    }

@app.get("/devices/{device_id}/events/types")
async def get_event_types(device_id: int, db: AsyncSession = Depends(database.get_db)):
    """
    Получение типов событий для устройства.
    
    Args:
        device_id: ID устройства
    
    Returns:
        Список типов событий
    """
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        password = get_device_password_safe(device, device.id)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Проверка соединения
        connected, error_msg = await client.check_connection()
        if not connected:
            raise HTTPException(status_code=503, detail=f"Device is not accessible: {error_msg}")
        
        # Возвращаем список известных типов событий
        # В будущем можно получать через capabilities API
        event_types = [
            {"code": "1_1", "description": "Door Open", "major": 1, "sub": 1},
            {"code": "1_2", "description": "Door Closed", "major": 1, "sub": 2},
            {"code": "2_1", "description": "Authenticated via Face", "major": 2, "sub": 1},
            {"code": "2_2", "description": "Authenticated via Card", "major": 2, "sub": 2},
            {"code": "2_7", "description": "Person Not Assigned", "major": 2, "sub": 7},
            {"code": "5_1", "description": "Remote: Login", "major": 5, "sub": 1},
            {"code": "5_2", "description": "Local: Login", "major": 5, "sub": 2},
        ]
        
        return {
            "success": True,
            "device_id": device_id,
            "event_types": event_types
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting event types for device {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/devices/{device_id}/webhook/status")
async def get_webhook_status(device_id: int, db: AsyncSession = Depends(database.get_db)):
    """
    Получение текущего статуса настройки HTTP Listening (Webhook) на терминале.
    
    Args:
        device_id: ID устройства
    
    Returns:
        Статус настройки webhook
    """
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        password = get_device_password_safe(device, device.id)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Проверка соединения
        connected, error_msg = await client.check_connection()
        if not connected:
            raise HTTPException(status_code=503, detail=f"Device is not accessible: {error_msg}")
        
        # Получаем настройки HTTP hosts
        result = await client.get_http_hosts()
        
        return {
            "success": result.get("success", False),
            "device_id": device_id,
            "device_name": device.name,
            "device_ip": device.ip_address,
            "http_hosts": result.get("data"),
            "requires_manual_setup": result.get("requires_manual_setup", False),
            "error": result.get("error")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting webhook status for device {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/devices/{device_id}/webhook/configure")
async def configure_webhook(
    device_id: int,
    server_ip: Optional[str] = None,
    server_port: int = 80,
    url_path: str = "/events/webhook",
    protocol: str = "http",
    db: AsyncSession = Depends(database.get_db)
):
    """
    Настройка HTTP Listening (Webhook) на терминале для отправки событий на сервер.
    
    Args:
        device_id: ID устройства
        server_ip: IP адрес сервера (если не указан, используется SERVER_IP из env или определяется автоматически)
        server_port: Порт сервера (по умолчанию 80)
        url_path: Путь на сервере (по умолчанию /events/webhook)
        protocol: Протокол (http или https, по умолчанию http)
    
    Returns:
        Результат настройки webhook
    """
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        password = get_device_password_safe(device, device.id)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Проверка соединения
        connected, error_msg = await client.check_connection()
        if not connected:
            raise HTTPException(status_code=503, detail=f"Device is not accessible: {error_msg}")
        
        # Определяем IP сервера
        if not server_ip:
            # Пробуем получить из переменных окружения
            server_ip = os.getenv("SERVER_IP")
            if not server_ip:
                # Если не указан, используем IP устройства (предполагаем, что сервер в той же сети)
                # Или можно использовать VPN IP
                terminal_vpn_ip = os.getenv("TERMINAL_IN_IP", "").rsplit(".", 1)[0] + ".1" if os.getenv("TERMINAL_IN_IP") else None
                if terminal_vpn_ip:
                    server_ip = terminal_vpn_ip
                else:
                    # Последний вариант - используем IP из запроса (если доступен)
                    raise HTTPException(
                        status_code=400,
                        detail="server_ip is required. Please provide server_ip parameter or set SERVER_IP in environment variables."
                    )
        
        logger.info(f"[WEBHOOK_CONFIG] Configuring webhook for device {device_id} ({device.name})")
        logger.info(f"[WEBHOOK_CONFIG] Server: {server_ip}:{server_port}{url_path} (protocol: {protocol})")
        
        # Настраиваем HTTP host
        result = await client.configure_http_host(
            server_ip=server_ip,
            server_port=server_port,
            url_path=url_path,
            protocol=protocol
        )
        
        return {
            "success": result.get("success", False),
            "device_id": device_id,
            "device_name": device.name,
            "message": result.get("message") or result.get("error"),
            "configuration": {
                "server_ip": server_ip,
                "server_port": server_port,
                "url_path": url_path,
                "protocol": protocol,
                "full_url": f"{protocol}://{server_ip}:{server_port}{url_path}"
            },
            "requires_manual_setup": result.get("requires_manual_setup", False),
            "manual_setup_instructions": result.get("manual_setup_instructions"),
            "error": result.get("error")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error configuring webhook for device {device_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/events/webhook")
async def receive_webhook_event(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(database.get_db)
):
    """
    Webhook endpoint для приема событий от терминала Hikvision через HTTP Listening.
    
    Терминал настроен:
    - Event Alarm IP: 192.168.1.64
    - URL: /events/webhook
    - Port: 80
    - Protocol: http
    
    События приходят в формате MIME multipart с JSON данными.
    """
    try:
        if WEBHOOK_API_KEY:
            if x_api_key:
                if x_api_key != WEBHOOK_API_KEY:
                    logger.warning(f"[WEBHOOK] Invalid API key from {request.client.host if request.client else 'unknown'}")
                    raise HTTPException(status_code=401, detail="Invalid API key")
        
        terminal_ip = request.client.host if request.client else "unknown"
        
        event_data = None
        try:
            event_data = await parse_multipart_event(request)
        except Exception as e:
            logger.error(f"[WEBHOOK] Error in parse_multipart_event: {e}", exc_info=True)
            event_data = None
        
        if not event_data:
            try:
                event_data = await parse_json_event(request)
            except Exception as e:
                logger.error(f"[WEBHOOK] Error in parse_json_event: {e}", exc_info=True)
                event_data = None
        
        if not event_data:
            content_type = request.headers.get('content-type', 'unknown')
            logger.warning(f"[WEBHOOK] Could not parse event. Content-Type: {content_type}")
            return {
                "status": "received", 
                "message": "Event format not recognized"
            }

        parsed_event = None
        try:
            temp_client = HikvisionClient("dummy", "dummy", "dummy")
            parsed_event = temp_client._parse_access_event(event_data)
        except Exception as parse_error:
            logger.error(f"[WEBHOOK] Error parsing event: {parse_error}", exc_info=True)
            return {
                "status": "received",
                "message": f"Error parsing event: {str(parse_error)}"
            }
        
        if not parsed_event:
            logger.warning(f"[WEBHOOK] Could not parse event data")
            return {
                "status": "received",
                "message": "Event parsed but no data extracted"
            }
        
        try:
            parsed_event["terminal_ip"] = terminal_ip
        except Exception as set_ip_error:
            logger.error(f"[WEBHOOK] Error setting terminal_ip: {set_ip_error}", exc_info=True)
            return {
                "status": "received",
                "message": f"Error setting terminal_ip: {str(set_ip_error)}"
            }
        from datetime import datetime, timezone
        timestamp = parsed_event.get("timestamp")
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                timestamp = timestamp.astimezone(timezone.utc)
            except Exception as ts_error:
                logger.warning(f"[WEBHOOK] Error parsing timestamp: {ts_error}")
                timestamp = datetime.now(timezone.utc)
        elif isinstance(timestamp, datetime):
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            else:
                timestamp = timestamp.astimezone(timezone.utc)
        elif not timestamp:
            timestamp = datetime.now(timezone.utc)

        try:
            internal_event = schemas_internal.InternalEventCreate(
                hikvision_id=parsed_event.get("employee_no"),
                event_type=parsed_event.get("event_type", "unknown"),
                terminal_ip=terminal_ip,
                timestamp=timestamp,
                employee_no=parsed_event.get("employee_no"),
                name=parsed_event.get("name"),
                card_no=parsed_event.get("card_no"),
                card_reader_id=parsed_event.get("card_reader_id"),
                event_type_code=parsed_event.get("event_type_code"),
                event_type_description=parsed_event.get("event_type_description"),
                remote_host_ip=parsed_event.get("remote_host_ip")
            )
        except Exception as create_error:
            logger.error(f"[WEBHOOK] Error creating event object: {create_error}", exc_info=True)
            return {
                "status": "received",
                "message": f"Error creating event object: {str(create_error)}"
            }

        try:
            db_event = await crud.create_event(db, internal_event)
            logger.info(f"[WEBHOOK] Event saved: ID={db_event.id}, employee={db_event.employee_no}")

            event_notification = {
                "id": db_event.id,
                "user_id": db_event.user_id,
                "employee_no": db_event.employee_no,
                "name": db_event.name,
                "event_type": db_event.event_type,
                "timestamp": db_event.timestamp.isoformat(),
                "terminal_ip": db_event.terminal_ip
            }
            await websocket_manager.notify_event_update(event_notification)
        except Exception as save_error:
            logger.error(f"[WEBHOOK] Error saving event: {save_error}", exc_info=True)
            return {
                "status": "received",
                "message": f"Error saving event: {str(save_error)}"
            }
        
        return {
            "status": "success",
            "message": "Event received and saved",
            "event_id": db_event.id,
            "employee_no": parsed_event.get("employee_no"),
            "event_type": parsed_event.get("event_type_description"),
            "debug": {
                "parsed_event": parsed_event
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[WEBHOOK] ERROR: Error processing webhook event: {e}", exc_info=True)
        # Возвращаем 200, чтобы терминал не повторял запрос при ошибке
        return {
            "status": "error", 
            "message": str(e),
            "error_type": type(e).__name__
        }


@app.on_event("shutdown")
async def shutdown_event():
    await event_service.stop_all_subscriptions()
    global daily_report_task
    if daily_report_task and not daily_report_task.done():
        daily_report_task.cancel()
        try:
            await daily_report_task
        except asyncio.CancelledError:
            pass
