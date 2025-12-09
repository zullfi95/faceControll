from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File, Body
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict
from datetime import datetime
import os
import uuid
import logging
from pathlib import Path

from . import crud, models, schemas, database
from .hikvision_client import HikvisionClient
from .utils.crypto import decrypt_password

app = FastAPI(title="Face Access Control System")

# Настройка логирования
logger = logging.getLogger(__name__)

# Загрузка API ключа из переменных окружения
WEBHOOK_API_KEY = os.getenv("WEBHOOK_API_KEY", "")

# Директория для загружаемых фото
UPLOAD_DIR = Path("/app/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Монтирование статики для доступа к фото
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

@app.on_event("startup")
async def startup():
    async with database.engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

# --- Users API ---
@app.post("/users/", response_model=schemas.UserResponse)
async def create_user(user: schemas.UserCreate, db: AsyncSession = Depends(database.get_db)):
    db_user = await crud.get_user_by_hik_id(db, hik_id=user.hikvision_id)
    if db_user:
        raise HTTPException(status_code=400, detail="User already registered")
    return await crud.create_user(db=db, user=user)

@app.get("/users/", response_model=List[schemas.UserResponse])
async def read_users(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(database.get_db)):
    users = await crud.get_users(db, skip=skip, limit=limit)
    return users

@app.delete("/users/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(database.get_db)):
    """Удаление пользователя из базы данных."""
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

@app.delete("/users/")
async def delete_all_users(db: AsyncSession = Depends(database.get_db)):
    """Удаление всех пользователей из базы данных (очистка)."""
    # Получаем всех пользователей для удаления их фото
    users = await crud.get_users(db, skip=0, limit=10000)
    
    # Удаляем файлы фото
    deleted_photos = 0
    for user in users:
        if user.photo_path:
            photo_filename = Path(user.photo_path).name
            photo_file_path = UPLOAD_DIR / photo_filename
            try:
                if photo_file_path.exists():
                    photo_file_path.unlink()
                    deleted_photos += 1
            except Exception as e:
                logger.warning(f"Failed to delete photo file {photo_file_path}: {e}")
    
    # Удаляем всех пользователей из БД
    deleted_count = await crud.delete_all_users(db)
    
    logger.info(f"Deleted {deleted_count} users and {deleted_photos} photo files")
    
    return {
        "message": f"All users deleted successfully",
        "users_deleted": deleted_count,
        "photos_deleted": deleted_photos
    }

# --- Hikvision Webhook Handler ---
@app.post("/events/webhook")
async def hikvision_webhook(
    payload: schemas.HikvisionEventPayload, 
    db: AsyncSession = Depends(database.get_db),
    x_api_key: Optional[str] = Header(None)
):
    """
    Принимает реальные события от устройств Hikvision.
    Фильтрует только события успешного прохода (major=5, sub=75).
    Требует API ключ в заголовке X-API-Key для безопасности.
    """
    # Проверка API ключа
    if WEBHOOK_API_KEY and x_api_key != WEBHOOK_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    event_data = payload.AccessControllerEvent
    
    # Проверяем, что это событие аутентификации лица (код 75 - Face authentication passed)
    # Коды могут отличаться в зависимости от прошивки, но 75 - стандарт для FaceID
    # majorEventType 5 - это "Event"
    
    if event_data.majorEventType != 5:
        return {"status": "ignored", "reason": "Not an event"}

    # subEventType 75 = Face authentication passed
    # subEventType 1 = Card passed
    # subEventType 25 = Fingerprint passed
    # Мы будем ловить все успешные проходы
    
    # Список кодов успешного доступа (можно расширять)
    SUCCESS_CODES = [1, 25, 75] 
    
    if event_data.subEventType not in SUCCESS_CODES:
         return {"status": "ignored", "reason": f"SubEventType {event_data.subEventType} is not access granted"}

    if not event_data.employeeNoString:
        return {"status": "ignored", "reason": "No employee ID"}

    # Определяем Тип (Вход/Выход) по IP терминала
    # Эту логику лучше вынести в конфиг, но пока захардкодим для наглядности
    # Вам нужно будет задать эти IP статикой в настройках терминалов
    
    TERMINAL_IN_IP = os.getenv("TERMINAL_IN_IP", "192.168.1.64")
    
    # Если событие пришло с IP Входа -> 'entry', иначе -> 'exit'
    event_type = "entry" if payload.ipAddress == TERMINAL_IN_IP else "exit"

    # Импортируем внутреннюю схему для создания события
    from .schemas_internal import InternalEventCreate
    
    # Создаем внутренний объект события
    internal_event = InternalEventCreate(
        hikvision_id=event_data.employeeNoString,
        event_type=event_type,
        terminal_ip=payload.ipAddress,
        timestamp=payload.dateTime
    )
    
    # Сохраняем в БД через crud
    db_event = await crud.create_event(db, internal_event)
    
    if not db_event:
        return {"status": "error", "msg": "User unknown or event creation failed"}
    
    return {"status": "ok", "saved": True, "event_id": db_event.id}

# --- Reports API ---
@app.get("/reports/daily")
async def daily_report(date_str: str = None, db: AsyncSession = Depends(database.get_db)):
    if not date_str:
        target_date = datetime.now().date()
    else:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Date format must be YYYY-MM-DD")
    
    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = datetime.combine(target_date, datetime.max.time())

    # Оптимизация: получаем всех пользователей и все события за день одним запросом
    users = await crud.get_users(db)
    all_events = await crud.get_all_events_for_day(db, start_of_day, end_of_day)
    
    # Группируем события по пользователям
    events_by_user = {}
    for event in all_events:
        if event.user_id not in events_by_user:
            events_by_user[event.user_id] = []
        events_by_user[event.user_id].append(event)
    
    # Создаем словарь пользователей для быстрого доступа
    users_dict = {user.id: user for user in users}
    
    report = []
    for user in users:
        events = events_by_user.get(user.id, [])
        
        if not events:
            report.append({
                "user": user.full_name,
                "status": "Absent",
                "hours_worked": 0
            })
            continue

        first_event = events[0]
        last_event = events[-1]
        
        if len(events) == 1:
             report.append({
                "user": user.full_name,
                "status": "Incomplete",
                "entry_time": first_event.timestamp,
                "exit_time": None,
                "hours_worked": 0
            })
             continue

        work_duration = last_event.timestamp - first_event.timestamp
        total_hours = work_duration.total_seconds() / 3600

        report.append({
            "user": user.full_name,
            "status": "Present",
            "entry_time": first_event.timestamp,
            "exit_time": last_event.timestamp,
            "hours_worked": round(total_hours, 2)
        })

    return report

# --- Device Management API ---
@app.post("/devices/", response_model=schemas.DeviceResponse)
async def create_device(device: schemas.DeviceCreate, db: AsyncSession = Depends(database.get_db)):
    """Создание нового устройства."""
    return await crud.create_device(db, device)

@app.get("/devices/", response_model=List[schemas.DeviceResponse])
async def get_devices(db: AsyncSession = Depends(database.get_db)):
    """Получение списка всех устройств."""
    return await crud.get_all_devices(db)

@app.get("/devices/{device_id}", response_model=schemas.DeviceResponse)
async def get_device(device_id: int, db: AsyncSession = Depends(database.get_db)):
    """Получение информации об устройстве."""
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

@app.put("/devices/{device_id}", response_model=schemas.DeviceResponse)
async def update_device(device_id: int, device_update: schemas.DeviceUpdate, db: AsyncSession = Depends(database.get_db)):
    """Обновление устройства."""
    device = await crud.update_device(db, device_id, device_update)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

@app.get("/devices/{device_id}/status", response_model=schemas.DeviceStatusResponse)
async def check_device_status(device_id: int, db: AsyncSession = Depends(database.get_db)):
    """Проверка статуса подключения к устройству."""
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    logger.info(f"Checking status for device {device_id}: {device.ip_address}")
    
    try:
        password = decrypt_password(device.password_encrypted)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        logger.info("Calling check_connection()...")
        connected = await client.check_connection()
        logger.info(f"Connection result: {connected}")
        
        device_info = None
        
        if connected:
            logger.info("Calling get_device_info()...")
            device_info = await client.get_device_info()
            logger.info(f"Device info result: {device_info}")
        else:
            logger.warning("Device not connected, skipping device_info")
        
        return schemas.DeviceStatusResponse(
            connected=connected,
            device_info=device_info,
            error=None if connected else "Connection failed"
        )
    except Exception as e:
        logger.error(f"Error checking device status: {e}", exc_info=True)
        return schemas.DeviceStatusResponse(
            connected=False,
            device_info=None,
            error=str(e)
        )

@app.get("/devices/{device_id}/capabilities")
async def get_device_capabilities(
    device_id: int, 
    format: str = "json",
    db: AsyncSession = Depends(database.get_db)
):
    """
    Получение списка поддерживаемых функций устройства.
    Endpoint: GET /ISAPI/System/capabilities
    
    Args:
        device_id: ID устройства в БД
        format: Формат ответа - "json" или "xml" (по умолчанию "json")
    """
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        password = decrypt_password(device.password_encrypted)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Проверка соединения
        connected = await client.check_connection()
        if not connected:
            raise HTTPException(
                status_code=503,
                detail="Terminal is not accessible. Check network connection."
            )
        
        # Получаем capabilities
        capabilities = await client.get_system_capabilities(format=format)
        
        if capabilities is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to get capabilities from terminal"
            )
        
        return {
            "device": {
                "id": device_id,
                "ip": device.ip_address,
                "name": device.name
            },
            "format": format,
            "capabilities": capabilities
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting capabilities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/devices/{device_id}/remote-control")
async def get_remote_control_info(
    device_id: int,
    db: AsyncSession = Depends(database.get_db)
):
    """
    Получение информации о Remote Control и его capabilities.
    Проверяет поддержку удаленной регистрации на терминале.
    """
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        password = decrypt_password(device.password_encrypted)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Проверка соединения
        connected = await client.check_connection()
        if not connected:
            raise HTTPException(
                status_code=503,
                detail="Terminal is not accessible. Check network connection."
            )
        
        # Получаем информацию о Remote Control
        remote_info = await client.check_remote_control_settings()
        
        # Получаем информацию об устройстве для контекста
        device_info = await client.get_device_info()
        
        return {
            "device": {
                "id": device_id,
                "ip": device.ip_address,
                "name": device.name,
                "model": device_info.get("model", "unknown") if device_info else "unknown",
                "firmware": device_info.get("firmwareVersion", "unknown") if device_info else "unknown"
            },
            "remote_control": remote_info,
            "summary": {
                "capabilities_available": remote_info.get("capabilities_available", False) if remote_info else False,
                "settings_available": remote_info.get("settings_available", False) if remote_info else False,
                "register_endpoint_accessible": remote_info.get("register_endpoint_accessible", False) if remote_info else False,
                "remote_registration_supported": (
                    remote_info and (
                        remote_info.get("capabilities_available") or 
                        remote_info.get("register_endpoint_accessible")
                    )
                ) if remote_info else False
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting remote control info: {e}", exc_info=True)
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
        password = decrypt_password(device.password_encrypted)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Проверка соединения
        connected = await client.check_connection()
        if not connected:
            raise HTTPException(
                status_code=503,
                detail="Terminal is not accessible. Check network connection."
            )
        
        # Получаем сводку поддерживаемых функций
        features = await client.get_supported_features_summary()
        
        # Получаем информацию об устройстве
        device_info = await client.get_device_info()
        
        return {
            "device": {
                "id": device_id,
                "ip": device.ip_address,
                "name": device.name,
                "model": device_info.get("model", "unknown") if device_info else "unknown",
                "firmware": device_info.get("firmwareVersion", "unknown") if device_info else "unknown"
            },
            "features": features
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting supported features: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/devices/{device_id}/start-face-capture")
async def start_face_capture_mode(
    device_id: int,
    request: Dict = Body(...),
    db: AsyncSession = Depends(database.get_db)
):
    """
    Запуск режима захвата лица на терминале (появляется кружок для лица).
    Пробует различные возможные endpoints для запуска режима захвата.
    
    Args:
        device_id: ID устройства в БД
        request: Body с employee_no или hikvision_id
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Получаем employee_no из request
    employee_no = request.get("employee_no") or request.get("hikvision_id")
    if not employee_no:
        raise HTTPException(status_code=400, detail="employee_no or hikvision_id is required in request body")
    
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        password = decrypt_password(device.password_encrypted)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Проверка соединения
        connected = await client.check_connection()
        if not connected:
            raise HTTPException(
                status_code=503,
                detail="Terminal is not accessible. Check network connection."
            )
        # Параметры из запроса
        user_name = request.get("full_name") or employee_no
        user_department = request.get("department") or ""

        # Гарантируем FDLib
        ensure_fdlib = await client.ensure_fdlib_exists()
        if not ensure_fdlib.get("success"):
            raise HTTPException(status_code=502, detail=f"Failed to ensure FDLib: {ensure_fdlib.get('error')}")

        # Проверяем/создаем пользователя без фото, чтобы терминал ожидал лицо именно для него
        terminal_users = await client.get_users()
        user_exists = terminal_users and any(user.get("employeeNo") == employee_no for user in terminal_users)
        if not user_exists:
            created = await client.create_user_basic(employee_no, user_name, user_department or None)
            if not created.get("success"):
                raise HTTPException(status_code=502, detail=f"Failed to create user before capture: {created.get('error')}")

        # Запускаем режим захвата на терминале
        logger.info(f"Starting face capture mode for employee {employee_no}")
        capture_result = await client.start_face_capture_mode(employee_no, user_name)

        if not capture_result or not capture_result.get("success"):
            msg = capture_result.get("message") if capture_result else "unknown error"
            raw = capture_result.get("raw_response") if capture_result else ""
            raise HTTPException(
                status_code=502,
                detail=f"Face capture mode not started: {msg}. Raw: {raw[:300]}"
            )

        face_data_url = capture_result.get("face_data_url")
        if not face_data_url:
            # Пробуем подождать и проверить, появилось ли лицо у пользователя
            import asyncio
            for _ in range(3):
                await asyncio.sleep(1)
                face_info = await client.check_face_info(employee_no)
                if face_info and face_info.get("has_face") and face_info.get("face_url"):
                    face_data_url = face_info["face_url"]
                    break

        if not face_data_url:
            raw = capture_result.get("raw_response", "")
            raise HTTPException(
                status_code=502,
                detail=f"Face capture mode started but no face_data_url returned. Raw: {raw[:300]}"
            )

        # Скачиваем фото с терминала и загружаем в FDLib (чтобы лицо сохранилось)
        import httpx
        from httpx import DigestAuth
        async with httpx.AsyncClient() as http_client:
            clean_url = face_data_url.split('@')[0] if '@' in face_data_url else face_data_url
            photo_response = await http_client.get(
                clean_url,
                auth=DigestAuth(device.username, password),
                timeout=30
            )

        if photo_response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to download captured photo: HTTP {photo_response.status_code}"
            )

        photo_bytes = photo_response.content
        upload_result = await client.add_face_to_user_json(employee_no, photo_bytes, user_name)

        if not upload_result.get("success"):
            raise HTTPException(
                status_code=502,
                detail=f"Failed to upload face to FDLib: {upload_result.get('error')}"
            )

        return {
            "success": True,
            "message": f"Face captured and saved on terminal for employee {employee_no}",
            "employee_no": employee_no,
            "face_data_url": face_data_url,
            "face_uploaded": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting face capture mode: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/devices/{device_id}/user-face-data")
async def get_user_face_data(
    device_id: int,
    employee_no: str,
    db: AsyncSession = Depends(database.get_db)
):
    """
    Получение фото лица пользователя с терминала по employee_no.
    Endpoint: GET /ISAPI/AccessControl/UserFace/faceData
    """
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        password = decrypt_password(device.password_encrypted)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Проверка соединения
        connected = await client.check_connection()
        if not connected:
            raise HTTPException(
                status_code=503,
                detail="Terminal is not accessible. Check network connection."
            )
        
        # Получаем фото лица
        photo_bytes = await client.get_user_face_data(employee_no)
        
        if not photo_bytes:
            raise HTTPException(
                status_code=404,
                detail=f"No face data found for employee {employee_no}"
            )
        
        from fastapi.responses import Response
        return Response(content=photo_bytes, media_type="image/jpeg")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user face data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

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
        password = decrypt_password(device.password_encrypted)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Проверка соединения
        connected = await client.check_connection()
        if not connected:
            raise HTTPException(
                status_code=503,
                detail="Terminal is not accessible. Check network connection."
            )
        
        # Проверяем, поддерживается ли перезагрузка
        capabilities = await client.get_system_capabilities()
        if capabilities:
            parsed = capabilities.get("parsed", {})
            if parsed.get("isSupportReboot", "false") != "true":
                raise HTTPException(
                    status_code=501,
                    detail="Device does not support reboot operation"
                )
        
        # Выполняем перезагрузку
        success = await client.reboot_device()
        
        if success:
            return {
                "success": True,
                "message": "Device reboot command sent successfully. Device will restart in a few moments.",
                "device_id": device_id,
                "device_ip": device.ip_address
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to send reboot command to device"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rebooting device: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/users/{user_id}/upload-photo")
async def upload_user_photo(
    user_id: int, 
    file: UploadFile = File(...),
    db: AsyncSession = Depends(database.get_db)
):
    """Загрузка фото пользователя."""
    # Проверка существования пользователя
    user = await crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Проверка типа файла
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Сохранение файла
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
    
    # Проверка наличия фото
    if not user.photo_path:
        raise HTTPException(status_code=400, detail="User has no photo. Upload photo first.")
    
    try:
        # Расшифровка пароля устройства
        password = decrypt_password(device.password_encrypted)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Чтение фото с валидацией пути (защита от path traversal)
        filename = Path(user.photo_path).name  # Безопасное извлечение имени файла
        if not filename or filename != Path(user.photo_path).name:
            raise HTTPException(status_code=400, detail="Invalid photo path")
        photo_file_path = UPLOAD_DIR / filename
        # Дополнительная проверка, что путь находится в UPLOAD_DIR
        try:
            photo_file_path.resolve().relative_to(UPLOAD_DIR.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid photo path - path traversal detected")
        if not photo_file_path.exists():
            raise HTTPException(status_code=404, detail="Photo file not found")
        
        with open(photo_file_path, "rb") as f:
            photo_bytes = f.read()
        
        # Проверяем, существует ли пользователь на терминале
        terminal_users = await client.get_users()
        user_exists = False
        if terminal_users:
            user_exists = any(u.get("employeeNo") == user.hikvision_id for u in terminal_users)
        
        # Синхронизация с устройством
        if user_exists:
            # Пользователь уже существует на терминале
            # ВАЖНО: Фото можно загрузить только при создании пользователя, не к существующему
            logger.info(f"User {user.hikvision_id} already exists on terminal")
            
            # Проверяем, есть ли фото на терминале
            face_info = await client.check_face_info(user.hikvision_id)
            photo_already_on_terminal = face_info is not None
            
            if photo_already_on_terminal:
                logger.info(f" Photo already exists on terminal for user {user.hikvision_id}")
            else:
                logger.warning(f" Photo not found on terminal for user {user.hikvision_id}")
                logger.warning(f" NOTE: Cannot add photo to existing user - photo can only be uploaded during user creation")
            
            # Отмечаем как синхронизированного (пользователь существует на терминале)
            await crud.mark_user_synced(db, user_id, True)
            await crud.update_device_sync_time(db, device.id)
            
            return {
                "message": "User synchronized successfully (user already existed on terminal)",
                "face_uploaded": photo_already_on_terminal,
                "photo_already_on_terminal": photo_already_on_terminal,
                "note": "User exists on terminal. Photo can only be uploaded during user creation, not to existing users."
            }
        else:
            # Пользователь не существует - создаем с фото через multipart (как в веб-интерфейсе)
            logger.info(f"User {user.hikvision_id} does not exist on terminal, creating with face via multipart")
            
            result = await client.add_user_with_face(
                employee_no=user.hikvision_id,
                name=user.full_name,
                photo_bytes=photo_bytes,
                department=user.department if user.department else None
            )
            
            logger.info(f"Result from add_user_with_face: {result}")
            
            # Проверяем, что result не None перед обращением к его элементам
            if result is not None and result.get("success"):
                # Отмечаем пользователя как синхронизированного
                await crud.mark_user_synced(db, user_id, True)
                await crud.update_device_sync_time(db, device.id)
                
                logger.info(f" User {user.hikvision_id} synchronized successfully with face")
                
                return {
                    "message": "User synchronized successfully",
                    "result": result
                }
            elif result and result.get("user_added") and "already exists" in result.get("error", "").lower():
                # Пользователь уже существует на терминале - проверяем наличие фото
                logger.warning(f"User {user.hikvision_id} already exists on terminal, checking for photo...")
                face_info = await client.check_face_info(user.hikvision_id)
                photo_exists = face_info is not None
                
                await crud.mark_user_synced(db, user_id, True)
                await crud.update_device_sync_time(db, device.id)
                
                return {
                    "message": "User already exists on terminal",
                    "face_uploaded": photo_exists,
                    "photo_already_on_terminal": photo_exists,
                    "note": "User exists on terminal. Photo can only be uploaded during user creation."
                }
            else:
                # Если создание не удалось, возвращаем ошибку
                error_msg = result.get('error', 'Unknown error') if result else 'add_user_with_face returned None'
                raise HTTPException(status_code=500, detail=f"Sync failed: {error_msg}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during sync: {str(e)}")

@app.delete("/users/{user_id}/remove-from-device")
async def remove_user_from_device(user_id: int, db: AsyncSession = Depends(database.get_db)):
    """Удаление пользователя с устройства."""
    user = await crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    device = await crud.get_active_device(db)
    if not device:
        raise HTTPException(status_code=404, detail="No active device found")
    
    try:
        password = decrypt_password(device.password_encrypted)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        success = await client.delete_user(user.hikvision_id)
        
        if success:
            await crud.mark_user_synced(db, user_id, False)
            return {"message": "User removed from device successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to remove user from device")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during removal: {str(e)}")

@app.get("/devices/terminal-users")
async def get_terminal_users(db: AsyncSession = Depends(database.get_db)):
    """
    Получение списка пользователей с терминала.
    Endpoint: POST /ISAPI/AccessControl/UserInfo/Search
    
    Возвращает пользователей, которые есть на терминале, но нет в БД.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    device = await crud.get_active_device(db)
    if not device:
        raise HTTPException(status_code=404, detail="No active device found")
    
    try:
        password = decrypt_password(device.password_encrypted)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Получаем всех пользователей с терминала
        terminal_users = await client.get_users()
        
        if terminal_users is None:
            raise HTTPException(status_code=500, detail="Failed to get users from terminal")
        
        # Получаем пользователей из БД
        db_users = await crud.get_users(db)
        db_user_ids = {user.hikvision_id for user in db_users}
        
        # Фильтруем новых пользователей
        new_users = []
        for user in terminal_users:
            emp_no = user.get("employeeNo", "")
            if emp_no and emp_no not in db_user_ids:
                new_users.append({
                    "employeeNo": emp_no,
                    "name": user.get("name", ""),
                    "has_face": int(user.get("numOfFace", 0)) > 0
                })
        
        logger.info(f"Found {len(new_users)} new users on terminal")
        
        return {
            "total_on_terminal": len(terminal_users),
            "new_users": new_users,
            "terminal_ip": device.ip_address
        }
            
    except Exception as e:
        logger.error(f"Error getting terminal users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/devices/capture-snapshot")
async def capture_snapshot_from_terminal(db: AsyncSession = Depends(database.get_db)):
    """
    Захват snapshot с камеры терминала.
    Endpoint: GET /ISAPI/Streaming/channels/101/picture (канал 101 для терминалов!)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    device = await crud.get_active_device(db)
    if not device:
        raise HTTPException(status_code=404, detail="No active device found")
    
    try:
        password = decrypt_password(device.password_encrypted)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Используем канал 101 для терминалов контроля доступа
        photo_bytes = await client.capture_snapshot(channel_id=101)
        
        if not photo_bytes:
            raise HTTPException(status_code=500, detail="Failed to capture snapshot")
        
        # Сохраняем временный файл
        temp_filename = f"snapshot_{uuid.uuid4().hex}.jpg"
        temp_path = UPLOAD_DIR / temp_filename
        
        try:
            with open(temp_path, "wb") as f:
                f.write(photo_bytes)
        except (IOError, OSError) as file_error:
            logger.error(f"Failed to save snapshot file {temp_path}: {file_error}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to save snapshot: {file_error}")
        
        return {
            "message": "Snapshot captured successfully",
            "photo_url": f"/uploads/{temp_filename}",
            "temp_filename": temp_filename
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# --- Debug Endpoints ---
# Эти endpoints доступны только в режиме разработки (DEBUG=True)
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"

@app.get("/devices/{device_id}/access-control-capabilities")
async def get_access_control_capabilities(device_id: int, db: AsyncSession = Depends(database.get_db)):
    """
    Получить capabilities Access Control для проверки поддерживаемых функций.
    Доступно только в режиме разработки (DEBUG=true).
    """
    if not DEBUG_MODE:
        raise HTTPException(status_code=404, detail="Not found")
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        password = decrypt_password(device.password_encrypted)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Check connection first
        connected = await client.check_connection()
        if not connected:
            raise HTTPException(
                status_code=503,
                detail="Terminal is not accessible."
            )
        
        # Get capabilities
        import httpx
        from httpx import DigestAuth
        
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(
                f"http://{device.ip_address}/ISAPI/AccessControl/capabilities?format=json",
                auth=DigestAuth(device.username, password),
                timeout=10
            )
            
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "json" in content_type:
                    capabilities_data = response.json()
                else:
                    # XML response - parse it
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(response.content)
                    # Convert to dict-like structure for display
                    capabilities_data = {"xml": response.text[:5000]}  # First 5000 chars
                
                return {
                    "device": {
                        "model": device.name,
                        "ip": device.ip_address
                    },
                    "content_type": content_type,
                    "capabilities": capabilities_data
                }
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to get capabilities: {response.text[:200]}"
                )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting capabilities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/devices/{device_id}/isapi-endpoints")
async def discover_isapi_endpoints(device_id: int, db: AsyncSession = Depends(database.get_db)):
    """
    Обнаружение всех доступных ISAPI endpoints на терминале.
    Помогает понять, какие функции поддерживаются устройством.
    Доступно только в режиме разработки (DEBUG=true).
    """
    if not DEBUG_MODE:
        raise HTTPException(status_code=404, detail="Not found")
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        password = decrypt_password(device.password_encrypted)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Check connection first
        connected = await client.check_connection()
        if not connected:
            raise HTTPException(
                status_code=503,
                detail="Terminal is not accessible. Check network connection."
            )
        
        # Get device info
        device_info = await client.get_device_info()
        
        # Discover endpoints
        endpoints_info = await client.discover_isapi_endpoints()
        
        return {
            "device": {
                "model": device_info.get("model", "unknown") if device_info else "unknown",
                "firmware": device_info.get("firmwareVersion", "unknown") if device_info else "unknown",
                "ip": device.ip_address
            },
            "endpoints": endpoints_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error discovering ISAPI endpoints: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/devices/{device_id}/fdlib/list")
async def get_fdlib_list(device_id: int, db: AsyncSession = Depends(database.get_db)):
    """
    Получение списка лиц из FDLib.
    GET /ISAPI/Intelligent/FDLib?format=json
    """
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        password = decrypt_password(device.password_encrypted)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Check connection first
        connected = await client.check_connection()
        if not connected:
            raise HTTPException(
                status_code=503,
                detail="Terminal is not accessible. Check network connection."
            )
        
        # Get FDLib list
        fdlib_list = await client.get_fdlib_list()
        
        # Форматируем ответ для удобства
        result = {
            "device_id": device_id,
            "device_ip": device.ip_address,
            "success": fdlib_list is not None and "error" not in fdlib_list,
            "fdlib_list": fdlib_list
        }
        
        # Добавляем статистику, если есть данные
        if fdlib_list and "total_faces" in fdlib_list:
            result["summary"] = {
                "total_faces": fdlib_list.get("total_faces", 0),
                "status": fdlib_list.get("statusString", "Unknown")
            }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting FDLib list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/devices/{device_id}/remote-control-settings")
async def get_remote_control_settings(device_id: int, db: AsyncSession = Depends(database.get_db)):
    """
    Проверка настроек Remote Control на терминале.
    Показывает, какие endpoints доступны и поддерживается ли Remote Registration.
    Доступно только в режиме разработки (DEBUG=true).
    """
    if not DEBUG_MODE:
        raise HTTPException(status_code=404, detail="Not found")
    device = await crud.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        password = decrypt_password(device.password_encrypted)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Check connection first
        connected = await client.check_connection()
        if not connected:
            raise HTTPException(
                status_code=503,
                detail="Terminal is not accessible. Check network connection."
            )
        
        # Get device info
        device_info = await client.get_device_info()
        
        # Check Remote Control settings
        remote_settings = await client.check_remote_control_settings()
        
        return {
            "device": {
                "model": device_info.get("model", "unknown") if device_info else "unknown",
                "firmware": device_info.get("firmwareVersion", "unknown") if device_info else "unknown",
                "ip": device.ip_address
            },
            "remote_control": remote_settings,
            "conclusion": "Remote Registration is supported" if remote_settings and (
                remote_settings.get("capabilities_available") or 
                remote_settings.get("register_endpoint_accessible")
            ) else "Remote Registration may not be supported or not configured"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking remote control settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/devices/test-remote-registration")
async def test_remote_registration(
    request: schemas.RemoteEnrollmentRequest,
    db: AsyncSession = Depends(database.get_db)
):
    """
    Детальный тест Remote Registration с различными вариантами запросов.
    Проверяет все возможные комбинации методов, форматов и заголовков.
    Доступно только в режиме разработки (DEBUG=true).
    """
    if not DEBUG_MODE:
        raise HTTPException(status_code=404, detail="Not found")
    import logging
    import httpx
    from httpx import DigestAuth
    import xml.etree.ElementTree as ET
    import json
    
    logger = logging.getLogger(__name__)
    
    device = await crud.get_active_device(db)
    if not device:
        raise HTTPException(status_code=404, detail="No active device found")
    
    try:
        password = decrypt_password(device.password_encrypted)
        results = []
        base_url = f"http://{device.ip_address}/ISAPI/AccessControl/RemoteControl/register"
        
        # Получаем информацию об устройстве
        hikvision_client = HikvisionClient(device.ip_address, device.username, password)
        device_info = await hikvision_client.get_device_info()
        
        # Test 1: PUT with JSON (стандартный способ)
        request_body_json = {
            "RemoteRegister": {
                "registerType": "face",
                "registerValidDuration": request.timeout,
                "employeeNo": request.hikvision_id
            }
        }
        
        logger.info(f"Testing Remote Registration on {device.ip_address}")
        
        async with httpx.AsyncClient() as client:
            # Test 1a: PUT with JSON, Content-Type: application/json
            try:
                response = await client.put(
                    base_url,
                    auth=DigestAuth(device.username, password),
                    json=request_body_json,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
                results.append({
                    "test": "PUT + JSON + Content-Type: application/json",
                    "status_code": response.status_code,
                    "response_body": response.text[:500],
                    "error_info": HikvisionClient.parse_error_xml(response.content) if response.status_code != 200 else None
                })
            except Exception as e:
                results.append({
                    "test": "PUT + JSON + Content-Type: application/json",
                    "error": str(e)
                })
            
            # Test 1b: PUT with JSON, без явного Content-Type
            try:
                response = await client.put(
                    base_url,
                    auth=DigestAuth(device.username, password),
                    json=request_body_json,
                    timeout=10
                )
                
                results.append({
                    "test": "PUT + JSON (auto Content-Type)",
                    "status_code": response.status_code,
                    "response_body": response.text[:500],
                    "error_info": HikvisionClient.parse_error_xml(response.content) if response.status_code != 200 else None
                })
            except Exception as e:
                results.append({
                    "test": "PUT + JSON (auto Content-Type)",
                    "error": str(e)
                })
            
            # Test 2: POST with JSON
            try:
                response = await client.post(
                    base_url,
                    auth=DigestAuth(device.username, password),
                    json=request_body_json,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
                results.append({
                    "test": "POST + JSON",
                    "status_code": response.status_code,
                    "response_body": response.text[:500],
                    "error_info": HikvisionClient.parse_error_xml(response.content) if response.status_code != 200 else None
                })
            except Exception as e:
                results.append({
                    "test": "POST + JSON",
                    "error": str(e)
                })
            
            # Test 3: PUT with XML
            request_body_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<RemoteRegister>
    <registerType>face</registerType>
    <registerValidDuration>{request.timeout}</registerValidDuration>
    <employeeNo>{request.hikvision_id}</employeeNo>
</RemoteRegister>"""
            
            try:
                response = await client.put(
                    base_url,
                    auth=DigestAuth(device.username, password),
                    content=request_body_xml,
                    headers={"Content-Type": "application/xml"},
                    timeout=10
                )
                
                results.append({
                    "test": "PUT + XML",
                    "status_code": response.status_code,
                    "response_body": response.text[:500],
                    "error_info": HikvisionClient.parse_error_xml(response.content) if response.status_code != 200 else None
                })
            except Exception as e:
                results.append({
                    "test": "PUT + XML",
                    "error": str(e)
                })
        
        # Определяем результат
        success_tests = [r for r in results if r.get("status_code") in [200, 201]]
        conclusion = " Remote Registration SUPPORTED" if success_tests else " Remote Registration NOT supported"
        
        return {
            "device": {
                "model": device_info.get("model", "unknown") if device_info else "unknown",
                "firmware": device_info.get("firmwareVersion", "unknown") if device_info else "unknown",
                "ip": device.ip_address
            },
            "tests": results,
            "conclusion": conclusion,
            "note": "If all tests return 400/notSupport, the firmware version (V4.38.0) may not support this feature. Consider updating firmware to a newer version."
        }
            
    except Exception as e:
        logger.error(f"Error testing remote registration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# --- Remote Enrollment Endpoints ---
@app.post("/devices/start-remote-enrollment")
async def start_remote_enrollment(
    request: schemas.RemoteEnrollmentRequest,
    db: AsyncSession = Depends(database.get_db)
):
    """
    Запуск режима удаленной регистрации на терминале.
    Терминал перейдет в режим ожидания регистрации лица на указанное время.
    """
    import logging
    logger = logging.getLogger(__name__)

    device = await crud.get_active_device(db)
    if not device:
        raise HTTPException(status_code=404, detail="No active device found")

    try:
        password = decrypt_password(device.password_encrypted)
        client = HikvisionClient(device.ip_address, device.username, password)

        # First, check if terminal is connected
        logger.info("Checking terminal connection...")
        connected = await client.check_connection()
        if not connected:
            raise HTTPException(
                status_code=503,
                detail="Terminal is not accessible. Check network connection and terminal status."
            )

        # Try to start remote registration
        success = await client.start_remote_registration(
            request.hikvision_id,
            request.timeout
        )

        if not success:
            # Get device info for better error reporting
            device_info = await client.get_device_info()
            firmware_version = device_info.get('firmwareVersion', 'unknown') if device_info else 'unknown'
            model = device_info.get('model', 'unknown') if device_info else 'unknown'

            logger.error(f"Failed to start remote registration on {model} (FW: {firmware_version})")

            # Check if it's a "not support" error
            raise HTTPException(
                status_code=501,
                detail=f"Remote Registration не поддерживается на терминале {model} (прошивка {firmware_version}). "
                       f"Эта функция может быть недоступна на данной модели или требует обновления прошивки. "
                       f"Используйте альтернативный способ регистрации через интерфейс."
            )

        return {
            "success": True,
            "message": f"Remote registration started for employee {request.hikvision_id}",
            "timeout": request.timeout
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting remote enrollment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/devices/check-enrollment-status/{hikvision_id}")
async def check_enrollment_status(
    hikvision_id: str,
    db: AsyncSession = Depends(database.get_db)
):
    """
    Проверка статуса регистрации лица на терминале.
    Возвращает информацию о том, зарегистрировано ли лицо и FaceID.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    device = await crud.get_active_device(db)
    if not device:
        raise HTTPException(status_code=404, detail="No active device found")
    
    try:
        password = decrypt_password(device.password_encrypted)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        face_info = await client.check_face_info(hikvision_id)
        
        if face_info:
            face_id = face_info.get("faceLibID")
            return {
                "registered": True,
                "hikvision_id": hikvision_id,
                "face_id": face_id
            }
        else:
            return {
                "registered": False,
                "hikvision_id": hikvision_id,
                "face_id": None
            }
        
    except Exception as e:
        logger.error(f"Error checking enrollment status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/devices/complete-remote-enrollment", response_model=schemas.UserResponse)
async def complete_remote_enrollment(
    request: schemas.CompleteEnrollmentRequest,
    db: AsyncSession = Depends(database.get_db)
):
    """
    Завершение удаленной регистрации: получение фото с терминала и создание пользователя.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    device = await crud.get_active_device(db)
    if not device:
        raise HTTPException(status_code=404, detail="No active device found")
    
    try:
        password = decrypt_password(device.password_encrypted)
        client = HikvisionClient(device.ip_address, device.username, password)
        
        # Шаг 1: Получить FaceID
        face_info = await client.check_face_info(request.hikvision_id)
        if not face_info:
            raise HTTPException(
                status_code=404,
                detail=f"No face registered for employee {request.hikvision_id}"
            )
        
        face_id = face_info.get("faceLibID")
        if not face_id:
            raise HTTPException(
                status_code=500,
                detail="Face info found but FaceID is missing"
            )
        
        # Шаг 2: Загрузить фото по FaceID
        photo_bytes = await client.get_face_data_by_id(face_id)
        if not photo_bytes:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve face photo for FaceID {face_id}"
            )
        
        # Шаг 3: Сохранить фото
        photo_filename = f"{request.hikvision_id}_remote.jpg"
        photo_path = UPLOAD_DIR / photo_filename
        
        with open(photo_path, "wb") as f:
            f.write(photo_bytes)
        
        logger.info(f"Saved face photo to {photo_path}")
        
        # Шаг 4: Создать пользователя в БД
        user_create = schemas.UserCreate(
            hikvision_id=request.hikvision_id,
            full_name=request.full_name,
            department=request.department
        )
        
        db_user = await crud.create_user(db, user_create)
        
        # Шаг 5: Привязать фото к пользователю
        db_user.photo_path = f"/uploads/{photo_filename}"
        db_user.synced_to_device = True
        await db.commit()
        await db.refresh(db_user)
        
        logger.info(f" User {request.hikvision_id} created successfully via remote enrollment")
        
        return db_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing remote enrollment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")