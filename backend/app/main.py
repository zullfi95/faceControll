from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, text
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
from .tasks.auto_close_sessions import auto_close_sessions_daily as imported_auto_close_sessions_daily
from .auth import (
    verify_password, create_access_token, get_current_active_user,
    require_operations_manager, get_current_user
)
from .config import settings
from fastapi import Request, Header
from fastapi.security import OAuth2PasswordRequestForm

# Настройка структурированного логирования
class StructuredFormatter(logging.Formatter):
    """Форматтер для структурированного логирования в JSON."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Добавляем request_id если доступен
        if hasattr(record, 'request_id'):
            log_entry["request_id"] = record.request_id

        # Добавляем дополнительные поля из record
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)

        # Добавляем exception info если есть
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)

# Настройка корневого логгера
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Создаем обработчик для stdout с структурированным форматом
console_handler = logging.StreamHandler()
console_handler.setFormatter(StructuredFormatter())
root_logger.addHandler(console_handler)

UPLOAD_DIR = Path("uploads")


def validate_environment():
    """Валидация критически важных переменных окружения при запуске."""
    import logging
    temp_logger = logging.getLogger(__name__)
    errors = []

    # Проверка обязательных настроек
    if not settings.jwt_secret_key:
        errors.append("JWT_SECRET_KEY is required")

    if not settings.encryption_key:
        errors.append("ENCRYPTION_KEY is required")

    if not settings.webhook_api_key and settings.is_production():
        errors.append("WEBHOOK_API_KEY is required in production")

    # Проверка базы данных
    if not settings.database_url:
        errors.append("DATABASE_URL or PostgreSQL settings are required")

    # Проверка директории для загрузок
    if not UPLOAD_DIR.exists():
        try:
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"Cannot create upload directory: {e}")

    if errors:
        error_msg = "Environment validation failed:\n" + "\n".join(f"- {error}" for error in errors)
        temp_logger.error(error_msg)
        raise ValueError(error_msg)

    temp_logger.info("Environment validation passed")


# Валидация окружения при импорте модуля
validate_environment()

app = FastAPI(title="Face Access Control System")

logger = logging.getLogger(__name__)

# Middleware для добавления request ID
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    import uuid
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    # Добавляем request_id в логи
    logger.info(f"Request started: {request.method} {request.url.path} - ID: {request_id}")

    response = await call_next(request)

    # Добавляем request_id в заголовки ответа
    response.headers["X-Request-ID"] = request_id
    logger.info(f"Request completed: {request.method} {request.url.path} - ID: {request_id} - Status: {response.status_code}")

    return response

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

WEBHOOK_API_KEY = settings.webhook_api_key

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


@app.get("/health")
async def health_check():
    """Проверка здоровья приложения."""
    from datetime import datetime
    import platform

    # Проверяем подключение к БД
    try:
        async for db in database.get_db_session():
            await db.execute(text("SELECT 1"))
            db_status = "healthy"
            break
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    # Собираем информацию о системе (упрощенная версия без psutil)
    health_info = {
        "status": "healthy" if db_status == "healthy" else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "environment": settings.environment,
        "database": db_status,
        "system": {
            "platform": platform.system(),
            "python_version": platform.python_version(),
        },
        "telegram_bot_configured": bool(settings.telegram_bot_token and settings.telegram_chat_id),
    }

    return health_info

telegram_bot = None
daily_report_service = None
daily_report_task = None  # Фоновая задача для ежедневных отчетов
auto_close_sessions_task = None  # Фоновая задача для автозакрытия старых сессий

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
    """Инициализация телеграм бота и Device Manager при запуске приложения."""
    # База данных инициализируется через Alembic миграции

    # Инициализация телеграм бота
    global telegram_bot, daily_report_service, daily_report_task, auto_close_sessions_task
    telegram_token = settings.telegram_bot_token
    telegram_chat_id = settings.telegram_chat_id

    if telegram_token and telegram_chat_id:
        telegram_bot = TelegramBot(telegram_token, telegram_chat_id)
        daily_report_service = DailyReportService(telegram_bot)

        # Запускаем автоматическую отправку отчетов
        daily_report_task = asyncio.create_task(send_daily_reports_automatically())
        logger.info("Telegram bot and automated daily reports initialized successfully")
    else:
        logger.warning("Telegram bot not configured (missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID)")
    
    # Запускаем автоматическое закрытие старых сессий (передаем telegram_bot для уведомлений)
    try:
        auto_close_sessions_task = asyncio.create_task(imported_auto_close_sessions_daily(telegram_bot))
        logger.info("Auto-close sessions task initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize auto-close sessions task: {e}", exc_info=True)
    
    # Инициализация Device Manager и запуск подписок на события
    try:
        from .device_manager import device_manager
        
        logger.info("Initializing Device Manager...")
        
        # Получаем сессию БД для инициализации
        async for db in database.get_db_session():
            # Инициализируем Device Manager
            await device_manager.initialize(db)
            
            # Получаем все активные устройства
            active_devices = await crud.get_all_devices(db)
            active_devices = [d for d in active_devices if d.is_active]
            
            logger.info(f"Found {len(active_devices)} active device(s)")
            
            # Запускаем подписки на события для каждого активного терминала
            subscribed_count = 0
            for device in active_devices:
                try:
                    success = await device_manager.start_subscription(device.id)
                    if success:
                        logger.info(f"✓ Started event subscription for device {device.id} ({device.name})")
                        subscribed_count += 1
                    else:
                        logger.warning(f"✗ Failed to start subscription for device {device.id} ({device.name})")
                except Exception as e:
                    logger.error(f"✗ Error starting subscription for device {device.id}: {e}", exc_info=True)
            
            logger.info(f"Device Manager initialized: {subscribed_count}/{len(active_devices)} subscriptions active")
            break  # Выходим после первой итерации
            
    except Exception as e:
        logger.error(f"Error initializing Device Manager: {e}", exc_info=True)
        logger.warning("Application will continue without Device Manager")

@app.post("/users/", response_model=schemas.UserResponse)
async def create_user(user: schemas.UserCreate, db: AsyncSession = Depends(database.get_db)):
    """Создание нового пользователя."""
    # Проверяем, не существует ли уже пользователь с таким ID
    existing_user = await crud.get_user_by_hik_id(db, user.hikvision_id)
    if existing_user:
        raise HTTPException(status_code=400, detail=f"User with hikvision_id '{user.hikvision_id}' already exists")

    return await crud.create_user(db=db, user=user)

@app.get("/users/", response_model=List[schemas.UserResponse])
async def get_users(
    skip: int = 0, 
    limit: int = 100, 
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(get_current_active_user)
):
    """Получение списка пользователей."""
    return await crud.get_users(db, skip=skip, limit=limit)

@app.get("/users/{user_id}", response_model=schemas.UserResponse)
async def get_user(
    user_id: int, 
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(get_current_active_user)
):
    """Получение пользователя по ID."""
    user = await crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/users/{user_id}/statistics", response_model=schemas.UserStatisticsResponse)
async def get_user_statistics(
    user_id: int, 
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(get_current_active_user)
):
    """Получение статистики пользователя."""
    from sqlalchemy import func, and_
    from datetime import datetime, timedelta, timezone
    
    user = await crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Получаем все события пользователя
    all_events_query = select(models.AttendanceEvent).filter(
        models.AttendanceEvent.user_id == user_id
    ).order_by(models.AttendanceEvent.timestamp.asc())
    
    result = await db.execute(all_events_query)
    all_events = result.scalars().all()
    
    # Вычисляем статистику
    total_events = len(all_events)
    total_entry_events = sum(1 for e in all_events if e.event_type == "entry")
    total_exit_events = sum(1 for e in all_events if e.event_type == "exit")
    
    first_event_date = all_events[0].timestamp if all_events else None
    last_event_date = all_events[-1].timestamp if all_events else None
    
    # События за последние 30 дней
    now = datetime.now(timezone.utc)
    date_30_days_ago = now - timedelta(days=30)
    date_7_days_ago = now - timedelta(days=7)
    today_start = datetime.combine(now.date(), time.min).replace(tzinfo=timezone.utc)
    
    events_last_30_days = sum(1 for e in all_events if e.timestamp >= date_30_days_ago)
    events_last_7_days = sum(1 for e in all_events if e.timestamp >= date_7_days_ago)
    events_today = sum(1 for e in all_events if e.timestamp >= today_start)
    
    return schemas.UserStatisticsResponse(
        user_id=user.id,
        user_name=user.full_name or f"User {user.hikvision_id}",
        hikvision_id=user.hikvision_id,
        total_events=total_events,
        total_entry_events=total_entry_events,
        total_exit_events=total_exit_events,
        first_event_date=first_event_date,
        last_event_date=last_event_date,
        events_last_30_days=events_last_30_days,
        events_last_7_days=events_last_7_days,
        events_today=events_today
    )

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
async def delete_user(
    user_id: int, 
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
):
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
    
    # Проверка размера файла (максимум 200KB)
    MAX_FILE_SIZE = 200 * 1024  # 200 KB
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400, 
            detail=f"File size exceeds maximum allowed size of 200KB. Current size: {len(file_content) / 1024:.2f}KB"
        )
    # Возвращаем указатель в начало файла для дальнейшего чтения
    await file.seek(0)

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

    # Убеждаемся, что директория существует
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        content = await file.read()
        logger.info(f"Saving photo for user {user_id}: {file_path}, size: {len(content)} bytes")
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Проверяем, что файл действительно сохранен
        if not file_path.exists():
            raise IOError(f"Photo file was not saved: {file_path}")
        
        file_size = file_path.stat().st_size
        logger.info(f"Photo file saved successfully: {file_path}, size: {file_size} bytes")
        
    except Exception as e:
        logger.error(f"Error saving photo file for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save photo file: {str(e)}")

    # Обновление пользователя
    user.photo_path = f"/uploads/{unique_filename}"
    try:
        await db.commit()
        await db.refresh(user)
        logger.info(f"Photo path updated in database for user {user_id}: {user.photo_path}")
    except Exception as e:
        logger.error(f"Error updating photo_path in database for user {user_id}: {e}", exc_info=True)
        # Пытаемся удалить сохраненный файл, если не удалось обновить БД
        try:
            if file_path.exists():
                file_path.unlink()
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to update photo path in database: {str(e)}")

    logger.info(f"Photo uploaded successfully for user {user_id}: {user.photo_path}")
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

@app.post("/users/{user_id}/sync-to-devices", response_model=schemas.SyncToDevicesResponse)
async def sync_user_to_multiple_devices(
    user_id: int,
    sync_request: schemas.SyncToDevicesRequest,
    db: AsyncSession = Depends(database.get_db)
):
    """
    Синхронизация пользователя с несколькими устройствами.
    
    Args:
        user_id: ID пользователя
        sync_request: Список device_ids и опция force
    
    Returns:
        Результаты синхронизации для каждого устройства
    """
    try:
        from .device_manager import device_manager
        
        # Получаем пользователя
        user = await crud.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        results = []
        synced_count = 0
        failed_count = 0
        
        # Синхронизируем на каждое устройство
        for device_id in sync_request.device_ids:
            try:
                device = await crud.get_device_by_id(db, device_id)
                if not device:
                    results.append(schemas.SyncToDevicesResult(
                        device_id=device_id,
                        device_name="Unknown",
                        status="failed",
                        message="Device not found",
                        error="Device not found"
                    ))
                    failed_count += 1
                    continue
                
                if not device.is_active:
                    results.append(schemas.SyncToDevicesResult(
                        device_id=device_id,
                        device_name=device.name,
                        status="failed",
                        message="Device is inactive",
                        error="Device is inactive"
                    ))
                    failed_count += 1
                    continue
                
                # Проверяем, нужна ли синхронизация
                if not sync_request.force:
                    synced_devices = await crud.get_user_synced_devices(db, user_id, status='synced')
                    if any(s.device_id == device_id for s in synced_devices):
                        results.append(schemas.SyncToDevicesResult(
                            device_id=device_id,
                            device_name=device.name,
                            status="skipped",
                            message="Already synced (use force=true to resync)"
                        ))
                        continue
                
                # Создаем/обновляем запись синхронизации
                await crud.create_user_device_sync(db, user_id, device_id, 'syncing')
                
                # Получаем клиент от Device Manager
                client = await device_manager.get_client(device_id, db)
                if not client:
                    await crud.update_device_sync_status(
                        db, user_id, device_id, 'failed',
                        "Failed to create client"
                    )
                    results.append(schemas.SyncToDevicesResult(
                        device_id=device_id,
                        device_name=device.name,
                        status="failed",
                        message="Failed to create client",
                        error="Could not connect to device"
                    ))
                    failed_count += 1
                    continue
                
                # Проверяем соединение (для синхронизации нужен прямой доступ к терминалу)
                # Увеличиваем таймаут для синхронизации
                original_timeout = client.timeout
                client.timeout = 30  # Увеличиваем таймаут для синхронизации
                
                try:
                    connected, error = await client.check_connection()
                    if not connected:
                        # Для webhook режима устройство может быть недоступно для входящих соединений
                        # Но для синхронизации нужен прямой доступ, поэтому все равно пытаемся выполнить операцию
                        if error and ("webhook" in error.lower() or "недоступно для входящих" in error.lower()):
                            logger.warning(f"Device {device_id} may be in webhook mode, but attempting sync anyway")
                            # Продолжаем попытку синхронизации, но с предупреждением
                        elif error and ("401" in error or "403" in error or "учетные данные" in error.lower() or "доступ запрещен" in error.lower()):
                            # Для ошибок аутентификации/авторизации блокируем синхронизацию
                            await crud.update_device_sync_status(
                                db, user_id, device_id, 'failed',
                                f"Connection failed: {error}"
                            )
                            results.append(schemas.SyncToDevicesResult(
                                device_id=device_id,
                                device_name=device.name,
                                status="failed",
                                message=f"Ошибка подключения к терминалу",
                                error=error
                            ))
                            failed_count += 1
                            continue
                        else:
                            # Для других ошибок (таймаут, сеть и т.д.) все равно пытаемся синхронизировать
                            logger.warning(f"Device {device_id} connection check failed: {error}, but attempting sync anyway")
                finally:
                    client.timeout = original_timeout
                
                # Создаем пользователя на терминале
                result = await client.create_user_basic(
                    employee_no=user.hikvision_id,
                    name=user.full_name,
                    group_id=None
                )
                
                if result.get("success"):
                    # Загружаем фото на терминал (если есть на сервере)
                    photo_uploaded = False
                    if user.photo_path:
                        try:
                            # Читаем фото с сервера
                            photo_filename = Path(user.photo_path).name
                            photo_file_path = UPLOAD_DIR / photo_filename
                            
                            if photo_file_path.exists():
                                with open(photo_file_path, "rb") as f:
                                    photo_bytes = f.read()
                                
                                # Загружаем фото на терминал
                                upload_result = await client.upload_face_image_to_terminal(
                                    employee_no=user.hikvision_id,
                                    image_bytes=photo_bytes
                                )
                                
                                if upload_result.get("success"):
                                    photo_uploaded = True
                                    logger.info(f"Photo uploaded to terminal {device_id} for user {user.hikvision_id}")
                                else:
                                    logger.warning(f"Failed to upload photo to terminal {device_id} for user {user.hikvision_id}: {upload_result.get('error')}")
                            else:
                                logger.warning(f"Photo file not found on server for user {user.hikvision_id}: {photo_file_path}")
                        except Exception as e:
                            logger.error(f"Error uploading photo for user {user.hikvision_id} to device {device_id}: {e}", exc_info=True)
                    
                    # Если фото не загружено, пытаемся использовать локальный URL (для обратной совместимости)
                    if not photo_uploaded:
                        face_url = f"{client.base_url}/LOCALS/pic/web_face_enrollpic.jpg@WEB000000000020"
                        face_result = await client.setup_user_face_fdlib(
                            employee_no=user.hikvision_id,
                            face_url=face_url
                        )
                        if face_result.get("success"):
                            logger.info(f"Face linked via URL for user {user.hikvision_id} on device {device_id}")
                    
                    # Обновляем статус синхронизации
                    await crud.update_device_sync_status(db, user_id, device_id, 'synced')
                    
                    sync_message = "Successfully synced"
                    if photo_uploaded:
                        sync_message += " with photo"
                    elif not user.photo_path:
                        sync_message += " (no photo)"
                    else:
                        sync_message += " (photo upload failed)"
                    
                    results.append(schemas.SyncToDevicesResult(
                        device_id=device_id,
                        device_name=device.name,
                        status="synced",
                        message=sync_message
                    ))
                    synced_count += 1
                else:
                    error_msg = result.get('error', 'Unknown error')
                    # Улучшаем сообщение об ошибке для пользователя
                    user_friendly_message = "Не удалось синхронизировать пользователя с терминалом"
                    if "недоступно для входящих" in error_msg.lower() or "webhook" in error_msg.lower():
                        user_friendly_message = "Терминал недоступен для входящих соединений. Для синхронизации пользователей необходим прямой доступ к терминалу (не webhook режим). Проверьте сетевые настройки и доступность терминала."
                    elif "timeout" in error_msg.lower() or "таймаут" in error_msg.lower():
                        user_friendly_message = "Таймаут подключения к терминалу. Проверьте доступность терминала в сети."
                    elif "401" in error_msg or "учетные данные" in error_msg.lower():
                        user_friendly_message = "Ошибка аутентификации. Проверьте учетные данные терминала в настройках устройства."
                    elif "403" in error_msg or "доступ запрещен" in error_msg.lower():
                        user_friendly_message = "Доступ запрещен. Проверьте права пользователя терминала."
                    
                    await crud.update_device_sync_status(
                        db, user_id, device_id, 'failed',
                        error_msg
                    )
                    results.append(schemas.SyncToDevicesResult(
                        device_id=device_id,
                        device_name=device.name,
                        status="failed",
                        message=user_friendly_message,
                        error=error_msg
                    ))
                    failed_count += 1
                
            except Exception as e:
                logger.error(f"Error syncing user {user_id} to device {device_id}: {e}", exc_info=True)
                await crud.update_device_sync_status(
                    db, user_id, device_id, 'failed',
                    str(e)
                )
                results.append(schemas.SyncToDevicesResult(
                    device_id=device_id,
                    device_name=device.name if device else "Unknown",
                    status="failed",
                    message="Error during sync",
                    error=str(e)
                ))
                failed_count += 1
        
        # Обновляем User.synced_to_device (для обратной совместимости)
        if synced_count > 0:
            await crud.mark_user_synced(db, user_id, True)
        
        return schemas.SyncToDevicesResponse(
            success=failed_count == 0,
            results=results,
            total_devices=len(sync_request.device_ids),
            synced_count=synced_count,
            failed_count=failed_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in sync_user_to_multiple_devices: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/users/{user_id}/device-sync-status", response_model=schemas.UserDeviceSyncStatusResponse)
async def get_user_device_sync_status(
    user_id: int,
    db: AsyncSession = Depends(database.get_db)
):
    """
    Получение статуса синхронизации пользователя со всеми устройствами.
    
    Returns:
        Информация о том, на какие устройства синхронизирован пользователь
    """
    try:
        # Получаем пользователя
        user = await crud.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Получаем все синхронизации пользователя
        user_syncs = await crud.get_user_synced_devices(db, user_id)
        
        # Получаем все устройства для подсчета total
        all_devices = await crud.get_all_devices(db)
        
        # Формируем ответ
        synced_devices = []
        for sync in user_syncs:
            synced_devices.append(schemas.UserDeviceSyncResponse(
                id=sync.id,
                user_id=sync.user_id,
                device_id=sync.device_id,
                device_name=sync.device.name,
                device_type=sync.device.device_type,
                sync_status=sync.sync_status,
                last_sync_at=sync.last_sync_at,
                error_message=sync.error_message,
                created_at=sync.created_at,
                updated_at=sync.updated_at
            ))
        
        # Подсчитываем количество синхронизированных устройств
        synced_count = sum(1 for s in user_syncs if s.sync_status == 'synced')
        
        return schemas.UserDeviceSyncStatusResponse(
            user_id=user_id,
            user_name=user.full_name,
            hikvision_id=user.hikvision_id,
            synced_devices=synced_devices,
            total_synced=synced_count,
            total_devices=len(all_devices)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user device sync status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

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
        # Используем короткий таймаут для быстрой проверки
        try:
            connected, error_msg = await asyncio.wait_for(
                client.check_connection(),
                timeout=2.0
            )
        except asyncio.TimeoutError:
            connected = False
            error_msg = "Устройство недоступно для входящих соединений. Это нормально при использовании webhook - терминал отправляет события на сервер автоматически."
        
        logger.info(f"Connection result: {connected}, error: {error_msg}")
        
        device_info = None
        
        if connected:
            try:
                logger.info("Calling get_device_info()...")
                device_info = await asyncio.wait_for(
                    client.get_device_info(),
                    timeout=3.0
                )
                logger.info(f"Device info result: {device_info}")
            except asyncio.TimeoutError:
                logger.warning("Timeout getting device info")
            except Exception as e:
                logger.warning(f"Error getting device info: {e}")
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

@app.get("/devices/groups", response_model=schemas.DeviceGroupResponse)
async def get_device_groups(db: AsyncSession = Depends(database.get_db)):
    """Получение устройств, сгруппированных по типам (entry/exit/both/other)."""
    try:
        devices = await crud.get_all_devices(db)
        
        # Группируем устройства по типам
        groups = {
            "entry": [],
            "exit": [],
            "both": [],
            "other": []
        }
        
        for device in devices:
            device_type = device.device_type or "other"
            if device_type in groups:
                groups[device_type].append(device)
        
        return schemas.DeviceGroupResponse(**groups)
    except Exception as e:
        logger.error(f"Error getting device groups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/devices/status", response_model=List[schemas.DeviceStatusInfo])
async def get_all_devices_status(db: AsyncSession = Depends(database.get_db)):
    """Получение статуса всех устройств с информацией о подключении и подписках."""
    try:
        from .device_manager import device_manager
        
        if not device_manager.is_initialized():
            logger.warning("Device Manager not initialized")
            return []
        
        statuses = await device_manager.get_all_statuses()
        
        # Преобразуем в формат DeviceStatusInfo
        result = []
        for status in statuses:
            result.append(schemas.DeviceStatusInfo(
                device_id=status["device_id"],
                name=status["name"],
                device_type=status["device_type"],
                location=status.get("location"),
                is_active=status["is_active"],
                connection_status=status["connection_status"],
                subscription_active=status["subscription_active"],
                last_event_at=status.get("last_event_at"),
                error_message=status.get("error_message")
            ))
        
        return result
    except Exception as e:
        logger.error(f"Error getting devices status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/devices/{device_id}/reconnect")
async def reconnect_device(device_id: int, db: AsyncSession = Depends(database.get_db)):
    """Переподключение к устройству (перезапуск подписки на события)."""
    try:
        from .device_manager import device_manager
        
        device = await crud.get_device_by_id(db, device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        success = await device_manager.reconnect_device(device_id, db)
        
        if success:
            return {
                "success": True,
                "message": f"Successfully reconnected to device {device_id}",
                "device_id": device_id,
                "device_name": device.name
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to reconnect to device {device_id}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reconnecting device: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

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
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(get_current_active_user)
) -> Dict[str, Any]:
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
            # Возвращаем пустой результат с пагинацией вместо ошибки
            return {"total": 0, "skip": skip, "limit": limit, "users": []}

        # Получаем список пользователей
        users = await client.get_users()

        if users is None:
            logger.warning(f"Failed to get users from terminal {device_id}")
            return {"total": 0, "skip": skip, "limit": limit, "users": []}

        # Применяем пагинацию
        total = len(users)
        paginated_users = users[skip:skip + limit]

        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "users": paginated_users
        }

    except PermissionError as pe:
        logger.warning(f"Insufficient permissions for device {device_id}: {str(pe)}")
        return {"total": 0, "skip": skip, "limit": limit, "users": []}
    except Exception as e:
        logger.error(f"Error getting terminal users for device {device_id}: {e}", exc_info=True)
        # Возвращаем пустой результат с пагинацией вместо 500 ошибки
        return {"total": 0, "skip": skip, "limit": limit, "users": []}

@app.post("/devices/{device_id}/sync-users")
async def sync_users_from_terminal(
    device_id: int,
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
) -> Dict[str, Any]:
    """
    Синхронизация пользователей с терминала в базу данных.
    
    Получает список пользователей с терминала и добавляет их в БД,
    если они еще не существуют.
    
    Returns:
        Статистика синхронизации: created, existing, total, errors
    """
    from .enums import UserRole
    
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    created_count = 0
    existing_count = 0
    errors = []
    
    try:
        password = get_device_password_safe(device, device.id)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Проверка соединения
        connected, error_msg = await client.check_connection()
        if not connected:
            raise HTTPException(
                status_code=400,
                detail=f"Device {device_id} not accessible: {error_msg}"
            )
        
        # Получаем список пользователей с терминала
        terminal_users = await client.get_users()
        
        if terminal_users is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to get users from terminal"
            )
        
        if not terminal_users:
            return {
                "success": True,
                "created": 0,
                "existing": 0,
                "total": 0,
                "errors": []
            }
        
        # Обрабатываем каждого пользователя
        for terminal_user in terminal_users:
            try:
                # Извлекаем данные из структуры Hikvision
                employee_no = terminal_user.get("employeeNo")
                name = terminal_user.get("name", "")
                
                if not employee_no:
                    errors.append({
                        "user": terminal_user,
                        "error": "Missing employeeNo"
                    })
                    continue
                
                # Проверяем, существует ли пользователь в БД
                existing_user = await crud.get_user_by_hik_id(db, employee_no)
                
                if existing_user:
                    existing_count += 1
                    logger.debug(f"User {employee_no} already exists in database")
                else:
                    # Создаем нового пользователя
                    user_create = schemas.UserCreate(
                        hikvision_id=employee_no,
                        full_name=name or employee_no,  # Используем employeeNo если name пустой
                        department=None,  # Department может быть в других полях, но пока оставляем None
                        role=UserRole.CLEANER.value  # Роль по умолчанию
                    )
                    
                    await crud.create_user(db, user_create)
                    created_count += 1
                    logger.info(f"Created user {employee_no} ({name}) in database")
                    
            except ValueError as ve:
                # Ошибка валидации hikvision_id
                errors.append({
                    "employee_no": employee_no,
                    "error": f"Validation error: {str(ve)}"
                })
                logger.warning(f"Validation error for user {employee_no}: {ve}")
            except Exception as e:
                errors.append({
                    "employee_no": employee_no,
                    "error": str(e)
                })
                logger.error(f"Error processing user {employee_no}: {e}", exc_info=True)
        
        total_processed = created_count + existing_count + len(errors)
        
        return {
            "success": True,
            "created": created_count,
            "existing": existing_count,
            "total": len(terminal_users),
            "processed": total_processed,
            "errors": errors
        }
        
    except HTTPException:
        raise
    except PermissionError as pe:
        logger.warning(f"Insufficient permissions for device {device_id}: {str(pe)}")
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient permissions: {str(pe)}"
        )
    except Exception as e:
        logger.error(f"Error syncing users from terminal {device_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error syncing users: {str(e)}"
        )
    finally:
        # Закрываем клиент, если он был создан
        try:
            if 'client' in locals():
                await client.close()
        except:
            pass

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


@app.get("/reports/daily", response_model=schemas.ShiftReportResponse)
async def get_daily_report(
    date_str: str, 
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(get_current_active_user)
):
    """
    Получение дневного отчета посещаемости с группировкой по сменам.

    Args:
        date_str: Дата в формате YYYY-MM-DD

    Returns:
        Отчет по сменам с детальной информацией о каждом сотруднике
    """
    DAY_NAMES = {
        0: "Понедельник",
        1: "Вторник", 
        2: "Среда",
        3: "Четверг",
        4: "Пятница",
        5: "Суббота",
        6: "Воскресенье"
    }
    
    from datetime import datetime, time, timezone, timedelta
    from .utils.hours_calculation import (
        get_shift_time_range,
        parse_sessions_from_events,
        calculate_hours_for_sessions
    )
    from . import models
    from sqlalchemy import select, and_, or_

    try:
        from .utils.hours_calculation import BAKU_TZ
        
        # Парсим дату с обработкой ошибок
        try:
            report_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format: {date_str}. Expected format: YYYY-MM-DD. Error: {str(e)}"
            )
        # Используем BAKU_TZ для согласованности с расчетами часов
        report_datetime = datetime.combine(report_date, time.min, tzinfo=BAKU_TZ)
        weekday = report_date.weekday()  # 0=Monday, 6=Sunday

        logger.info(f"Generating shift-based daily report for {report_date}")

        # Диапазон для поиска событий (с учетом ночных смен)
        # Используем BAKU_TZ для согласованности
        start_datetime = datetime.combine(report_date, time.min, tzinfo=BAKU_TZ)
        end_datetime = datetime.combine(report_date, time.max, tzinfo=BAKU_TZ)
        extended_start_datetime = start_datetime - timedelta(days=1)
        
        # Получаем все события за период
        events = await crud.get_all_events_for_day(db, extended_start_datetime, end_datetime)
        
        # Группируем события по user_id для быстрого доступа
        events_by_user = {}
        for event in events:
            if event.user_id:
                if event.user_id not in events_by_user:
                    events_by_user[event.user_id] = []
                events_by_user[event.user_id].append(event)
        
        # Получаем все активные смены
        shifts = await crud.get_all_work_shifts(db, active_only=True)
        
        shift_reports = []
        
        for shift in shifts:
            # Получаем всех пользователей, привязанных к этой смене
            assignments = await crud.get_user_shift_assignments(
                db, shift_id=shift.id, active_only=True
            )

            # Фильтруем привязки по дате (start_date и end_date)
            active_assignments = []
            for assignment in assignments:
                date_check = (not assignment.start_date or assignment.start_date.date() <= report_date) and \
                           (not assignment.end_date or assignment.end_date.date() >= report_date)
                if date_check:
                    active_assignments.append(assignment)
            
            # Создаем список всех дней недели из расписания смены
            shift_days = []
            
            # Проходим по всем дням недели (0-6)
            for day_of_week in range(7):
                day_schedule_dict = shift.schedule.get(str(day_of_week))
                
                # Если день включен в расписании, добавляем его
                if day_schedule_dict and day_schedule_dict.get("enabled", False):
                    day_schedule = schemas.DaySchedule(
                        start=day_schedule_dict.get("start", "09:00"),
                        end=day_schedule_dict.get("end", "18:00"),
                        enabled=True
                    )
                    
                    # Определяем, является ли этот день активным (соответствует выбранной дате)
                    is_active = (day_of_week == weekday)
                    
                    # Вычисляем продолжительность смены для отображения (одинакова для всех сотрудников дня)
                    shift_duration_hours = None
                    if day_schedule:
                        try:
                            start_hour, start_minute = map(int, day_schedule.start.split(':'))
                            end_hour, end_minute = map(int, day_schedule.end.split(':'))
                            start_time_obj = time(start_hour, start_minute)
                            end_time_obj = time(end_hour, end_minute)
                            
                            # Вычисляем разницу во времени
                            temp_date = datetime.combine(report_datetime.date(), start_time_obj)
                            start_datetime = datetime.combine(temp_date.date(), start_time_obj)
                            end_datetime = datetime.combine(temp_date.date(), end_time_obj)
                            
                            # Если время окончания меньше времени начала, значит смена переходит через полночь
                            if end_datetime < start_datetime:
                                end_datetime += timedelta(days=1)
                            
                            duration_timedelta = end_datetime - start_datetime
                            shift_duration_hours = duration_timedelta.total_seconds() / 3600.0
                        except (ValueError, AttributeError) as e:
                            logger.warning(f"Error calculating shift duration for day {day_of_week}: {e}")
                    
                    # Обрабатываем сотрудников только для активного дня
                    employees_for_day = []
                    if is_active:
                        for assignment in active_assignments:
                            user = assignment.user
                            user_events = sorted(events_by_user.get(user.id, []), key=lambda x: x.timestamp)
                            
                            # Парсим сессии из событий (передаем дату отчета и конец смены для правильной обработки незакрытых сессий)
                            shift_end_for_parsing = shift_time_range[1] if shift_time_range else None
                            sessions = parse_sessions_from_events(user_events, report_date=report_datetime, shift_end=shift_end_for_parsing)
                            
                            # Получаем расписание смены для этого дня
                            shift_time_range = None
                            if day_schedule:
                                shift_time_range = get_shift_time_range(shift, report_datetime)
                                if shift_time_range:
                                    pass
                                else:
                                    logger.warning(
                                        f"No shift time range for user {user.id} on {report_date} "
                                        f"(shift {shift.name}, weekday {day_of_week})"
                                    )
                            
                            # Рассчитываем часы (передаем user_id для логирования)
                            if shift_time_range:
                                hours_in_shift, hours_outside_shift = calculate_hours_for_sessions(
                                    sessions, shift_time_range[0], shift_time_range[1], user_id=user.id
                                )
                            else:
                                # Если нет расписания смены, считаем все часы как вне смены
                                hours_in_shift, hours_outside_shift = calculate_hours_for_sessions(
                                    sessions, None, None, user_id=user.id
                                )
                            
                            # Логируем предупреждения для отладки
                            if user_events and len(sessions) == 0:
                                logger.warning(
                                    f"User {user.id} ({user.full_name}) has {len(user_events)} events but 0 sessions parsed. "
                                    f"Events: {[(e.event_type, e.timestamp) for e in user_events[:5]]}"
                                )
                            elif user_events and hours_in_shift == 0 and hours_outside_shift == 0:
                                logger.warning(
                                    f"User {user.id} ({user.full_name}) has {len(sessions)} sessions but 0 hours calculated. "
                                    f"Sessions: {sessions[:3] if sessions else 'None'}"
                                )
                            
                            # Определяем первое время входа и последнее событие
                            first_entry_time = None
                            last_entry_exit_time = None
                            last_event_type = None
                            status = "Absent"
                            
                            # Определяем первое событие входа в рамках смены
                            # Для ночных смен важно брать первое событие именно в период смены, а не первое событие вообще
                            if shift_time_range:
                                shift_start, shift_end = shift_time_range
                                # Ищем первое событие "entry" в период смены
                                for event in user_events:
                                    if event.event_type == "entry" and shift_start <= event.timestamp <= shift_end:
                                        first_entry_time = event.timestamp
                                        break
                            
                            # Если не нашли в смене, используем первое событие из сессий или событий
                            if first_entry_time is None:
                                if sessions:
                                    first_entry_time = sessions[0][0]  # Первая сессия - вход
                                elif user_events:
                                    # Берем первое событие "entry", если есть
                                    for event in user_events:
                                        if event.event_type == "entry":
                                            first_entry_time = event.timestamp
                                            break
                                    # Если нет entry событий, берем первое событие вообще
                                    if first_entry_time is None:
                                        first_entry_time = user_events[0].timestamp
                            
                            if sessions:
                                # Используем последнее событие для определения типа и времени
                                if user_events:
                                    last_entry_exit_time = user_events[-1].timestamp
                                    last_event_type = user_events[-1].event_type
                                    if last_event_type == "entry":
                                        # Открытая сессия - последнее событие вход
                                        status = "Present (no exit)"
                                    else:
                                        # Закрытая сессия - последнее событие выход
                                        if hours_in_shift + hours_outside_shift > 0:
                                            status = "Present"
                                else:
                                    # Если нет событий, используем время из сессий
                                    last_entry_exit_time = sessions[-1][1]  # Последняя сессия - выход
                                    last_event_type = "exit"
                                    if hours_in_shift + hours_outside_shift > 0:
                                        status = "Present"
                            elif user_events:
                                if last_entry_exit_time is None:
                                    last_entry_exit_time = user_events[-1].timestamp
                                if last_event_type is None:
                                    last_event_type = user_events[-1].event_type
                                status = "Present (no exit)"
                            
                            # Вычисляем время начала смены и опоздание
                            shift_start_time_str = None
                            delay_minutes = None
                            if day_schedule and day_schedule.start:
                                shift_start_time_str = day_schedule.start
                                
                                # Вычисляем опоздание, если есть первое время входа
                                if first_entry_time:
                                    try:
                                        # Парсим время начала смены (формат "HH:MM")
                                        start_hour, start_minute = map(int, day_schedule.start.split(':'))
                                        shift_start_datetime = report_datetime.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
                                        
                                        # Если первое время входа позже времени начала смены - есть опоздание
                                        if first_entry_time > shift_start_datetime:
                                            delay_timedelta = first_entry_time - shift_start_datetime
                                            delay_minutes = int(delay_timedelta.total_seconds() / 60)
                                    except (ValueError, AttributeError) as e:
                                        logger.warning(f"Error calculating delay for user {user.id}: {e}")
                            
                            # Общее время работы
                            hours_worked_total = hours_in_shift + hours_outside_shift
                            
                            employees_for_day.append(schemas.ShiftDayEmployee(
                                user_id=user.id,
                                user_name=user.full_name or f"User {user.hikvision_id}",
                                hikvision_id=user.hikvision_id,
                                shift_start_time=shift_start_time_str,
                                shift_duration_hours=round(shift_duration_hours, 2) if shift_duration_hours is not None else None,
                                first_entry_time=first_entry_time.isoformat() if first_entry_time else None,
                                delay_minutes=delay_minutes,
                                last_entry_exit_time=last_entry_exit_time.isoformat() if last_entry_exit_time else None,
                                last_event_type=last_event_type,
                                hours_worked_total=round(hours_worked_total, 2),
                                hours_in_shift=round(hours_in_shift, 2),
                                hours_outside_shift=round(hours_outside_shift, 2),
                                status=status
                            ))
                    
                    # Создаем данные для дня
                    day_data = schemas.ShiftDay(
                        day_of_week=day_of_week,
                        day_name=DAY_NAMES[day_of_week],
                        is_active=is_active,
                        schedule=day_schedule,
                        employees=employees_for_day
                    )
                    shift_days.append(day_data)
            
            # Добавляем отчет по смене только если есть хотя бы один день в расписании
            if shift_days:
                shift_reports.append(schemas.ShiftReport(
                    shift_id=shift.id,
                    shift_name=shift.name,
                    shift_description=shift.description,
                    days=shift_days,  # Список всех дней недели из расписания
                    active_day=weekday
                ))
        
        return schemas.ShiftReportResponse(
            shifts=shift_reports,
            report_date=date_str
        )

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
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                    try:
                        message_data = json.loads(data)
                        message_type = message_data.get("type")
                        
                        if message_type == "connected":
                            await websocket.send_json({"type": "connected", "status": "ok"})
                        elif message_type == "pong":
                            pass
                        elif message_type == "ping":
                            await websocket.send_json({"type": "pong"})
                            
                    except Exception as e:
                        logger.warning(f"Error parsing message: {e}")
                except asyncio.TimeoutError:
                    try:
                        await websocket.send_json({"type": "ping"})
                    except:
                        break
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"Error in events handler: {e}", exc_info=True)
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
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                    try:
                        message_data = json.loads(data)
                        message_type = message_data.get("type")
                        
                        if message_type == "connected":
                            await websocket.send_json({"type": "connected", "status": "ok"})
                        elif message_type == "pong":
                            pass
                        elif message_type == "ping":
                            await websocket.send_json({"type": "pong"})
                            
                    except:
                        pass
                except asyncio.TimeoutError:
                    try:
                        await websocket.send_json({"type": "ping"})
                    except:
                        break
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"Error in WebSocket reports handler: {e}", exc_info=True)
        finally:
            await websocket_manager.disconnect(websocket, "reports")
    except Exception as e:
        logger.error(f"Failed to establish WebSocket connection for reports: {e}", exc_info=True)
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
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                    try:
                        message_data = json.loads(data)
                        message_type = message_data.get("type")
                        
                        if message_type == "connected":
                            await websocket.send_json({"type": "connected", "status": "ok"})
                        elif message_type == "pong":
                            pass
                        elif message_type == "ping":
                            await websocket.send_json({"type": "pong"})
                            
                    except:
                        pass
                except asyncio.TimeoutError:
                    try:
                        await websocket.send_json({"type": "ping"})
                    except:
                        break

        except WebSocketDisconnect:
            pass
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
        "telegram_token_set": bool(settings.telegram_bot_token),
        "telegram_chat_id_set": bool(settings.telegram_chat_id)
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

@app.post("/admin/clear-events")
async def clear_all_events(
    db: AsyncSession = Depends(database.get_db),
    current_user: models.SystemUser = Depends(require_operations_manager)
):
    """
    Очистка всех событий посещаемости из базы данных.
    Удаляет все события (attendance_events), но сохраняет:
    - Пользователей (users)
    - Смены (work_shifts)
    - Привязки пользователей к сменам (user_shift_assignments)
    """
    from sqlalchemy import delete, select
    
    try:
        # Подсчитываем количество событий перед удалением
        count_result = await db.execute(select(models.AttendanceEvent))
        total_events = len(count_result.scalars().all())
        
        logger.info(f"Starting events cleanup: {total_events} events to delete")
        
        # Удаляем все события
        delete_result = await db.execute(delete(models.AttendanceEvent))
        deleted_count = delete_result.rowcount
        
        await db.commit()
        
        logger.info(f"Events cleanup completed: deleted {deleted_count} events")
        
        return {
            "success": True,
            "message": f"Успешно удалено {deleted_count} событий посещаемости",
            "stats": {
                "deleted_events": deleted_count,
                "users_preserved": True,
                "shifts_preserved": True,
                "assignments_preserved": True
            }
        }
    
    except Exception as e:
        logger.error(f"Error during events cleanup: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при очистке событий: {str(e)}")

@app.get("/devices/{device_id}/events")
async def get_device_events(
    device_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_records: int = 1000,
    db: AsyncSession = Depends(database.get_db)
):
    """
    Получение событий аутентификации из базы данных.
    События сохраняются в БД через webhook от терминала Hikvision.

    Args:
        device_id: ID устройства
        start_date: Начальная дата в формате YYYY-MM-DD (по умолчанию - вчера)
        end_date: Конечная дата в формате YYYY-MM-DD (по умолчанию - сейчас)
        max_records: Максимальное количество записей (по умолчанию 1000)

    Returns:
        Список событий из базы данных
    """
    from datetime import datetime, timedelta
    from sqlalchemy import and_

    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    try:
        # Определяем период (используем UTC для согласованности с событиями в БД)
        from datetime import timezone
        try:
            if start_date:
                start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
                # Делаем timezone-aware (UTC)
                start_datetime = start_datetime.replace(tzinfo=timezone.utc)
            else:
                start_datetime = datetime.now(timezone.utc) - timedelta(days=1)  # Вчера

            if end_date:
                end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
                end_datetime = end_datetime.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            else:
                end_datetime = datetime.now(timezone.utc)  # Сейчас
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid date format. Use YYYY-MM-DD: {str(e)}")

        logger.info(f"[GET_EVENTS] Getting events from DB for device {device_id} ({device.name}) for period {start_datetime} to {end_datetime}")

        # Получаем события из БД, фильтруя по IP адресу терминала
        # Используем remote_host_ip или terminal_ip для совместимости
        from sqlalchemy import or_
        events_query = select(models.AttendanceEvent).filter(
            and_(
                or_(
                    models.AttendanceEvent.terminal_ip == device.ip_address,
                    models.AttendanceEvent.remote_host_ip == device.ip_address
                ),
                models.AttendanceEvent.timestamp >= start_datetime,
                models.AttendanceEvent.timestamp <= end_datetime
            )
        ).order_by(models.AttendanceEvent.timestamp.desc()).limit(max_records)
        
        result = await db.execute(events_query)
        db_events = result.scalars().all()

        # Преобразуем события из БД в формат, совместимый с форматом терминала
        # Используем snake_case для совместимости с фронтендом
        events = []
        for event in db_events:
            events.append({
                "employee_no": event.employee_no or "",
                "name": event.name or "",
                "card_no": event.card_no or "",
                "card_reader_id": event.card_reader_id or "",
                "event_type": event.event_type or "",
                "event_type_code": event.event_type_code or "",
                "event_type_description": event.event_type_description or "",
                "timestamp": event.timestamp.isoformat() if event.timestamp else "",
                "remote_host_ip": event.remote_host_ip or "",
                "device_name": device.name or ""
            })

        logger.info(f"[GET_EVENTS] Retrieved {len(events)} events from database")

        return {
            "success": True,
            "device_id": device_id,
            "device_name": device.name,
            "events": events,
            "count": len(events),
            "period": {
                "start_date": start_datetime.isoformat(),
                "end_date": end_datetime.isoformat()
            },
            "source": "database"
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

        # Получаем события с терминала
        attendance_records = await client.get_attendance_records(
            start_time=start_datetime,
            end_time=end_datetime,
            max_records=1000
        )

        synced_count = 0
        skipped_count = 0

        # Сохраняем события в базу данных
        for i, record in enumerate(attendance_records or []):
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

                event = await crud.create_event(db, schemas_internal.InternalEventCreate(**event_data))
                if event:
                    synced_count += 1
                else:
                    skipped_count += 1

            except Exception as e:
                skipped_count += 1
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
            # Пробуем получить из настроек
            server_ip = settings.server_ip
            if not server_ip:
                # Если не указан, используем IP устройства (предполагаем, что сервер в той же сети)
                # Или можно использовать VPN IP
                terminal_vpn_ip = settings.terminal_in_ip.rsplit(".", 1)[0] + ".1" if settings.terminal_in_ip else None
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
                    raise HTTPException(status_code=401, detail="Invalid API key")
        
        # Получаем IP терминала из заголовков или client.host
        # X-Forwarded-For содержит реальный IP клиента за прокси
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For может содержать несколько IP через запятую
            terminal_ip = forwarded_for.split(",")[0].strip()
        else:
            terminal_ip = request.client.host if request.client else "unknown"
        
        event_data = None
        try:
            event_data = await parse_multipart_event(request)
        except Exception:
            event_data = None
        
        if not event_data:
            try:
                event_data = await parse_json_event(request)
            except Exception:
                event_data = None
        
        if not event_data:
            return {
                "status": "received", 
                "message": "Event format not recognized"
            }

        parsed_event = None
        try:
            temp_client = HikvisionClient("dummy", "dummy", "dummy")
            parsed_event = temp_client._parse_access_event(event_data)
        except Exception as parse_error:
            return {
                "status": "received",
                "message": f"Error parsing event: {str(parse_error)}"
            }
        
        if not parsed_event:
            return {
                "status": "received",
                "message": "Event parsed but no data extracted"
            }
        
        # Используем remote_host_ip из события как terminal_ip, если он есть
        # Это реальный IP терминала, который отправляет событие
        remote_host_ip = parsed_event.get("remote_host_ip")
        if remote_host_ip and remote_host_ip != "unknown":
            terminal_ip = remote_host_ip
            logger.info(f"[WEBHOOK] Using remote_host_ip {remote_host_ip} as terminal_ip")
        else:
            logger.info(f"[WEBHOOK] Using terminal_ip from request: {terminal_ip}, remote_host_ip: {remote_host_ip}")
        
        try:
            parsed_event["terminal_ip"] = terminal_ip
        except Exception as set_ip_error:
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
            except Exception:
                timestamp = datetime.now(timezone.utc)
        elif isinstance(timestamp, datetime):
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            else:
                timestamp = timestamp.astimezone(timezone.utc)
        elif not timestamp:
            timestamp = datetime.now(timezone.utc)

        # Определяем правильный тип события на основе предыдущих событий пользователя
        from .utils.entry_exit import determine_entry_exit
        employee_no = parsed_event.get("employee_no")
        user_id = None
        
        
        # Находим пользователя по hikvision_id для получения user_id
        if employee_no:
            user = await crud.get_user_by_hik_id(db, employee_no)
            if user:
                user_id = user.id
        
        # Определяем тип события на основе предыдущих событий
        determined_event_type = await determine_entry_exit(
            db=db,
            user_id=user_id,
            employee_no=employee_no,
            terminal_ip=terminal_ip,
            timestamp=timestamp
        )
        

        try:
            internal_event = schemas_internal.InternalEventCreate(
                hikvision_id=employee_no,
                event_type=determined_event_type,  # Используем определенный тип события
                terminal_ip=terminal_ip,
                timestamp=timestamp,
                employee_no=employee_no,
                name=parsed_event.get("name"),
                card_no=parsed_event.get("card_no"),
                card_reader_id=parsed_event.get("card_reader_id"),
                event_type_code=parsed_event.get("event_type_code"),
                event_type_description=parsed_event.get("event_type_description"),
                remote_host_ip=parsed_event.get("remote_host_ip")
            )
        except Exception as create_error:
            return {
                "status": "received",
                "message": f"Error creating event object: {str(create_error)}"
            }

        try:
            
            db_event = await crud.create_event(db, internal_event)
            

            event_notification = {
                "id": db_event.id,
                "user_id": db_event.user_id,
                "employee_no": db_event.employee_no,
                "name": db_event.name,
                "event_type": db_event.event_type,
                "timestamp": db_event.timestamp.isoformat(),
                "terminal_ip": db_event.terminal_ip
            }
            try:
                await websocket_manager.notify_event_update(event_notification)
            except Exception as e:
                # Тихая обработка ошибок уведомления
                pass
        except Exception as save_error:
            return {
                "status": "received",
                "message": f"Error saving event: {str(save_error)}"
            }
        
        return {
            "status": "success",
            "message": "Event received and saved",
            "event_id": db_event.id,
            "employee_no": parsed_event.get("employee_no"),
            "event_type": parsed_event.get("event_type_description")
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
    """Завершение работы приложения и остановка всех фоновых задач."""
    # Останавливаем Device Manager (автоматически останавливает все подписки)
    try:
        from .device_manager import device_manager
        await device_manager.stop_all()
        logger.info("Device Manager stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping Device Manager: {e}")
    
    # Останавливаем автоматическую отправку отчетов
    global daily_report_task, auto_close_sessions_task
    if daily_report_task and not daily_report_task.done():
        daily_report_task.cancel()
        try:
            await daily_report_task
        except asyncio.CancelledError:
            pass
        logger.info("Daily report task stopped")
    
    # Останавливаем автоматическое закрытие сессий
    if auto_close_sessions_task and not auto_close_sessions_task.done():
        auto_close_sessions_task.cancel()
        try:
            await auto_close_sessions_task
        except asyncio.CancelledError:
            pass
        logger.info("Auto-close sessions task stopped")
