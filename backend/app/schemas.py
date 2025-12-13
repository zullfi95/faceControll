from pydantic import BaseModel, RootModel, Field, field_validator
from datetime import datetime
from typing import Optional, List, Dict
from .enums import UserRole

# --- User Schemas ---
class UserBase(BaseModel):
    hikvision_id: str
    full_name: str
    department: Optional[str] = None
    role: Optional[str] = UserRole.CLEANER.value  # Роль пользователя (по умолчанию Cleaner)

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
    role: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    photo_path: Optional[str] = None
    synced_to_device: bool = False
    role: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# --- Role Schemas ---
class RoleInfo(BaseModel):
    """Информация о роли."""
    value: str
    display_name: str

class RolesListResponse(BaseModel):
    """Список всех доступных ролей."""
    roles: List[RoleInfo]

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
    user_id: Optional[int] = None
    timestamp: datetime
    event_type: str
    terminal_ip: Optional[str] = None
    
    # Расширенные поля из ISAPI событий
    employee_no: Optional[str] = None
    name: Optional[str] = None
    card_no: Optional[str] = None
    card_reader_id: Optional[str] = None
    event_type_code: Optional[str] = None
    event_type_description: Optional[str] = None
    remote_host_ip: Optional[str] = None

    class Config:
        from_attributes = True

class EventTypeResponse(BaseModel):
    """Ответ с информацией о типе события."""
    major_event_type: int
    sub_event_type: int
    code: str  # Комбинация majorEventType + subEventType
    description: str  # Текстовое описание

# --- Reports Schemas ---
class DailyReportEntry(BaseModel):
    """Запись в дневном отчете посещаемости."""
    user: str  # Имя пользователя
    hikvision_id: str  # ID в системе Hikvision
    entry_time: Optional[str] = None  # Время входа (ISO format)
    exit_time: Optional[str] = None  # Время выхода (ISO format)
    hours_worked: float  # Отработанные часы (сумма часов в смене и вне смены)
    hours_in_shift: float  # Часы, отработанные в смене
    hours_outside_shift: float  # Часы, отработанные вне смены
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

# --- Authentication Schemas ---
class Token(BaseModel):
    """Схема токена."""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """Данные токена."""
    username: Optional[str] = None

class UserLogin(BaseModel):
    """Схема для входа."""
    username: str
    password: str

class SystemUserBase(BaseModel):
    """Базовая схема пользователя системы."""
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str = "cleaner"
    is_active: bool = True

class SystemUserCreate(SystemUserBase):
    """Схема для создания пользователя системы."""
    password: str

class SystemUserUpdate(BaseModel):
    """Схема для обновления пользователя системы."""
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class SystemUserResponse(SystemUserBase):
    """Схема ответа с данными пользователя системы."""
    id: int
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True

class CurrentUserResponse(BaseModel):
    """Схема текущего пользователя."""
    id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    is_active: bool

    class Config:
        from_attributes = True

# --- Work Shift Schemas ---
class DaySchedule(BaseModel):
    """Расписание на один день недели."""
    start: str  # Время начала в формате "HH:MM" (например, "09:00")
    end: str  # Время окончания в формате "HH:MM" (например, "18:00")
    enabled: bool = True  # Включен ли этот день

class WorkShiftBase(BaseModel):
    """Базовая схема рабочей смены."""
    name: str
    description: Optional[str] = None
    schedule: Dict[str, DaySchedule]  # Ключ - день недели (0-6), значение - расписание дня
    is_active: bool = True

class WorkShiftCreate(WorkShiftBase):
    """Схема для создания рабочей смены."""
    pass

class WorkShiftUpdate(BaseModel):
    """Схема для обновления рабочей смены."""
    name: Optional[str] = None
    description: Optional[str] = None
    schedule: Optional[Dict[str, DaySchedule]] = None
    is_active: Optional[bool] = None

class WorkShiftResponse(WorkShiftBase):
    """Схема ответа с данными рабочей смены."""
    id: int
    created_at: datetime
    updated_at: datetime
    user_count: Optional[int] = None  # Количество привязанных пользователей

    class Config:
        from_attributes = True
        # Позволяем работать с JSON полями
        json_encoders = {
            dict: lambda v: v
        }

# --- User Shift Assignment Schemas ---
class UserShiftAssignmentBase(BaseModel):
    """Базовая схема привязки пользователя к смене."""
    user_id: int
    shift_id: int
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: bool = True

class UserShiftAssignmentCreate(UserShiftAssignmentBase):
    """Схема для создания привязки."""
    pass

class UserShiftAssignmentUpdate(BaseModel):
    """Схема для обновления привязки."""
    shift_id: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: Optional[bool] = None

class UserShiftAssignmentResponse(UserShiftAssignmentBase):
    """Схема ответа с данными привязки."""
    id: int
    created_at: datetime
    updated_at: datetime
    user_name: Optional[str] = None
    shift_name: Optional[str] = None

    class Config:
        from_attributes = True