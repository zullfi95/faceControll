from pydantic import BaseModel, RootModel, Field, field_validator
from datetime import datetime
from typing import Optional, List, Dict

# --- User Schemas ---
class UserBase(BaseModel):
    hikvision_id: str
    full_name: str
    department: Optional[str] = None

class UserCreate(UserBase):
    @field_validator('hikvision_id')
    @classmethod
    def validate_hikvision_id(cls, v):
        if not v:
            raise ValueError('hikvision_id cannot be empty')
        if len(v) > 32:
            raise ValueError('hikvision_id cannot be longer than 32 characters')
        if not all(ord(c) < 128 for c in v):
            raise ValueError('hikvision_id can only contain ASCII characters (no Cyrillic or special symbols)')
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('hikvision_id can only contain letters, numbers, underscores, and hyphens')
        return v

class UserUpdate(BaseModel):
    hikvision_id: Optional[str] = None
    full_name: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    photo_path: Optional[str] = None
    synced_to_device: bool = False
    created_at: datetime

    class Config:
        from_attributes = True

# --- Device Schemas ---
class DeviceBase(BaseModel):
    name: str
    ip_address: str
    username: str

class DeviceCreate(DeviceBase):
    password: str

class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    ip_address: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class DeviceResponse(DeviceBase):
    id: int
    is_active: bool
    created_at: datetime
    last_sync: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- Device Management Schemas ---
class SyncUserToDevice(BaseModel):
    user_id: int

class DeviceStatusResponse(BaseModel):
    connected: bool
    device_info: Optional[Dict[str, str]] = None
    error: Optional[str] = None

class StartFaceEnrollmentRequest(BaseModel):
    """Запрос на запуск процесса регистрации лица на терминале."""
    hikvision_id: str
    full_name: str

class FaceEnrollmentResponse(BaseModel):
    """Ответ с инструкциями по регистрации лица."""
    success: bool
    user_added: bool
    message: str
    instructions: Optional[List[str]] = None

# --- Remote Enrollment Schemas ---
class RemoteEnrollmentRequest(BaseModel):
    """Запрос на запуск удаленной регистрации на терминале."""
    hikvision_id: str
    full_name: str
    timeout: int = 60

class RemoteEnrollmentStatusResponse(BaseModel):
    """Ответ статуса удаленной регистрации."""
    registered: bool
    hikvision_id: str
    face_id: Optional[str] = None

class CompleteEnrollmentRequest(BaseModel):
    """Запрос на завершение регистрации и создание пользователя."""
    hikvision_id: str
    full_name: str
    department: Optional[str] = None

# --- Hikvision Raw Event Schemas ---
class AccessControllerEvent(BaseModel):
    deviceName: Optional[str] = None
    majorEventType: int
    subEventType: int
    employeeNoString: Optional[str] = None
    name: Optional[str] = None
    currentVerifyMode: Optional[str] = None

class HikvisionEventPayload(BaseModel):
    ipAddress: str
    dateTime: datetime
    AccessControllerEvent: AccessControllerEvent

# --- Internal Event Schemas ---
class EventResponse(BaseModel):
    id: int
    user_id: int
    timestamp: datetime
    event_type: str

    class Config:
        from_attributes = True

# --- Reports Schemas ---
class DailyReportEntry(BaseModel):
    """Запись в дневном отчете посещаемости."""
    user: str  # Имя пользователя
    hikvision_id: str  # ID в системе Hikvision
    entry_time: Optional[str] = None  # Время входа (ISO format)
    exit_time: Optional[str] = None  # Время выхода (ISO format)
    hours_worked: float  # Отработанные часы
    status: str  # "Present", "Absent", "Present (no exit)" и т.д.

class DailyReportResponse(RootModel):
    """Ответ endpoint /reports/daily."""
    root: List[DailyReportEntry]

class EventSyncResponse(BaseModel):
    """Ответ endpoint синхронизации событий."""
    success: bool
    message: str
    stats: Dict[str, int]
    period: Dict[str, str]