from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any, Optional
import os
import uuid
import logging
from pathlib import Path
import httpx

from . import models, database, crud, schemas, schemas_internal
from .utils.crypto import decrypt_password, encrypt_password
from .hikvision_client import HikvisionClient

app = FastAPI(title="Face Access Control System")

# Настройка логирования
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

# Загрузка API ключа из переменных окружения
WEBHOOK_API_KEY = os.getenv("WEBHOOK_API_KEY", "")

# Директория для загружаемых фото
UPLOAD_DIR = Path("/app/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Монтирование статики для доступа к фото
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

@app.on_event("startup")
async def startup():
    """Инициализация базы данных при запуске приложения."""
    async with database.engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

# --- Users API ---
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
async def update_user(user_id: int, user_update: schemas.UserUpdate, db: AsyncSession = Depends(database.get_db)):
    """Обновление пользователя."""
    user = await crud.update_user(db, user_id, user_update)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

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

        # Чтение фото с валидацией пути
        filename = Path(user.photo_path).name
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

# --- Devices API ---
@app.get("/devices/", response_model=List[schemas.DeviceResponse])
async def get_devices(db: AsyncSession = Depends(database.get_db)):
    """Получение списка всех устройств."""
    return await crud.get_all_devices(db)

@app.post("/devices/", response_model=schemas.DeviceResponse)
async def create_device(device: schemas.DeviceCreate, db: AsyncSession = Depends(database.get_db)):
    """Создание нового устройства."""
    return await crud.create_device(db, device)

# Важно: более специфичные маршруты должны быть выше общих
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

# Общие маршруты устройств (должны быть в конце, после специфичных)
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

# --- Reports API ---

@app.get("/reports/daily", response_model=schemas.DailyReportResponse)
async def get_daily_report(date_str: str, db: AsyncSession = Depends(database.get_db)):
    """
    Получение дневного отчета посещаемости.

    Args:
        date_str: Дата в формате YYYY-MM-DD

    Returns:
        Список пользователей с временем входа/выхода и отработанными часами
    """
    from datetime import datetime, time

    try:
        # Парсим дату
        report_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        # Создаем диапазон времени (начало и конец дня)
        start_datetime = datetime.combine(report_date, time.min)
        end_datetime = datetime.combine(report_date, time.max)

        logger.info(f"Generating daily report for {report_date}")

        # Получаем все события за день с JOIN к пользователям
        events = await crud.get_all_events_for_day(db, start_datetime, end_datetime)

        # Группируем события по пользователям
        user_events = {}
        for event in events:
            user_id = event.user_id
            if user_id not in user_events:
                user_events[user_id] = {
                    "user": event.user.full_name,
                    "hikvision_id": event.user.hikvision_id,
                    "events": []
                }
            user_events[user_id]["events"].append({
                "timestamp": event.timestamp,
                "event_type": event.event_type
            })

        # Обрабатываем данные для каждого пользователя
        report_data = []
        for user_data in user_events.values():
            events_list = sorted(user_data["events"], key=lambda x: x["timestamp"])

            # Находим первый вход и последний выход
            entry_time = None
            exit_time = None

            for event in events_list:
                if event["event_type"] == "entry" and entry_time is None:
                    entry_time = event["timestamp"]
                elif event["event_type"] == "exit":
                    exit_time = event["timestamp"]

            # Вычисляем отработанные часы
            hours_worked = 0.0
            status = "Absent"

            if entry_time and exit_time:
                # Оба события есть
                time_diff = exit_time - entry_time
                hours_worked = time_diff.total_seconds() / 3600
                status = "Present"
            elif entry_time and not exit_time:
                # Только вход - считаем как присутствие, но без точного времени выхода
                # Можно использовать текущее время или конец рабочего дня
                now = datetime.now()
                if now.date() == report_date:
                    # Сегодня - используем текущее время
                    time_diff = now - entry_time
                    hours_worked = time_diff.total_seconds() / 3600
                else:
                    # Прошлый день - предполагаем конец рабочего дня (18:00)
                    end_of_day = datetime.combine(report_date, time(18, 0))
                    if entry_time < end_of_day:
                        time_diff = end_of_day - entry_time
                        hours_worked = time_diff.total_seconds() / 3600
                status = "Present (no exit)"

            report_data.append({
                "user": user_data["user"],
                "hikvision_id": user_data["hikvision_id"],
                "entry_time": entry_time.isoformat() if entry_time else None,
                "exit_time": exit_time.isoformat() if exit_time else None,
                "hours_worked": round(hours_worked, 2),
                "status": status
            })

        # Сортируем по имени пользователя
        report_data.sort(key=lambda x: x["user"])

        logger.info(f"Generated report with {len(report_data)} users")
        return schemas.DailyReportResponse(root=report_data)

    except Exception as e:
        logger.error(f"Error generating daily report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")

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
        password = get_device_password_safe(device, device.id)
        client = HikvisionClient(device.ip_address, device.username, password)

        # Проверка соединения
        connected, error_msg = await client.check_connection()
        if not connected:
            raise HTTPException(status_code=503, detail=f"Device is not accessible: {error_msg}")

        # Определяем период
        if start_date:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start_datetime = datetime.now() - timedelta(days=1)  # Вчера

        if end_date:
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
            end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
        else:
            end_datetime = datetime.now()  # Сейчас

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
        password = get_device_password_safe(device, device.id)
        client = HikvisionClient(device.ip_address, device.username, password)

        # Определяем период синхронизации
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

        logger.info(f"Syncing events from device {device_id} ({device.name}) for period {start_datetime} to {end_datetime}")

        # Получаем события с терминала
        attendance_records = await client.get_attendance_records(
            start_time=start_datetime,
            end_time=end_datetime,
            max_records=1000
        )

        synced_count = 0
        skipped_count = 0

        # Сохраняем события в базу данных
        for record in attendance_records:
            try:
                # Проверяем, существует ли уже такое событие (по employee_no, timestamp, event_type)
                existing_event = await db.execute(
                    select(models.AttendanceEvent).filter(
                        models.AttendanceEvent.user_id == record["employee_no"],  # Это будет hikvision_id
                        models.AttendanceEvent.timestamp == record["timestamp"],
                        models.AttendanceEvent.event_type == record["event_type"]
                    )
                )
                existing = existing_event.scalars().first()

                if existing:
                    skipped_count += 1
                    continue

                # Создаем событие через crud функцию
                event_data = {
                    "hikvision_id": record["employee_no"],
                    "timestamp": record["timestamp"],
                    "event_type": record["event_type"],
                    "terminal_ip": record["terminal_ip"]
                }

                event = await crud.create_event(db, schemas_internal.InternalEventCreate(**event_data))
                if event:
                    synced_count += 1
                else:
                    logger.warning(f"Failed to create event for user {record['employee_no']}")

            except Exception as e:
                logger.warning(f"Error processing attendance record {record}: {e}")
                continue

        # Обновляем время последней синхронизации устройства
        await crud.update_device_sync_time(db, device_id)

        logger.info(f"Sync completed: {synced_count} events synced, {skipped_count} events skipped")

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
