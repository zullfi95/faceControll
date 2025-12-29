from pydantic import BaseModel, RootModel, Field, field_validator, EmailStr
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum
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

class UserStatisticsResponse(BaseModel):
    """Статистика пользователя."""
    user_id: int
    user_name: str
    hikvision_id: str
    total_events: int
    total_entry_events: int
    total_exit_events: int
    first_event_date: Optional[datetime] = None
    last_event_date: Optional[datetime] = None
    events_last_30_days: int
    events_last_7_days: int
    events_today: int

# --- Role Schemas ---
class RoleInfo(BaseModel):
    """Информация о роли."""
    value: str
    display_name: str

class RolesListResponse(BaseModel):
    """Список всех доступных ролей."""
    roles: List[RoleInfo]

# --- Device Schemas ---
class DeviceType(str, Enum):
    """Типы терминалов."""
    ENTRY = "entry"  # Вход
    EXIT = "exit"    # Выход
    BOTH = "both"    # Оба (вход и выход)
    OTHER = "other"  # Другое

class DeviceBase(BaseModel):
    name: str
    ip_address: str
    username: str
    device_type: Optional[DeviceType] = DeviceType.OTHER
    location: Optional[str] = None
    priority: Optional[int] = 0

class DeviceCreate(DeviceBase):
    password: str

class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    ip_address: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    device_type: Optional[DeviceType] = None
    location: Optional[str] = None
    priority: Optional[int] = None

class DeviceResponse(DeviceBase):
    id: int
    is_active: bool
    device_type: DeviceType
    location: Optional[str] = None
    priority: int
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

# --- Device Grouping Schemas ---
class DeviceGroupResponse(BaseModel):
    """Группировка устройств по типам."""
    entry: List[DeviceResponse]
    exit: List[DeviceResponse]
    both: List[DeviceResponse]
    other: List[DeviceResponse]

class DeviceStatusInfo(BaseModel):
    """Статус устройства с информацией о подключении."""
    device_id: int
    name: str
    device_type: DeviceType
    location: Optional[str] = None
    is_active: bool
    connection_status: str  # connected, disconnected, error
    subscription_active: bool
    last_event_at: Optional[datetime] = None
    error_message: Optional[str] = None

# --- User Device Sync Schemas ---
class UserDeviceSyncCreate(BaseModel):
    """Создание связи пользователь-устройство."""
    user_id: int
    device_id: int

class UserDeviceSyncUpdate(BaseModel):
    """Обновление статуса синхронизации."""
    sync_status: str
    last_sync_at: Optional[datetime] = None
    error_message: Optional[str] = None

class UserDeviceSyncResponse(BaseModel):
    """Ответ с информацией о синхронизации."""
    id: int
    user_id: int
    device_id: int
    device_name: str
    device_type: DeviceType
    sync_status: str
    last_sync_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SyncToDevicesRequest(BaseModel):
    """Запрос на синхронизацию пользователя с несколькими устройствами."""
    device_ids: List[int]
    force: bool = False  # Пересинхронизировать даже если уже синхронизирован

class SyncToDevicesResult(BaseModel):
    """Результат синхронизации с одним устройством."""
    device_id: int
    device_name: str
    status: str  # synced, failed, skipped
    message: str
    error: Optional[str] = None

class SyncToDevicesResponse(BaseModel):
    """Ответ на запрос синхронизации с несколькими устройствами."""
    success: bool
    results: List[SyncToDevicesResult]
    total_devices: int
    synced_count: int
    failed_count: int

class UserDeviceSyncStatusResponse(BaseModel):
    """Статус синхронизации пользователя со всеми устройствами."""
    user_id: int
    user_name: str
    hikvision_id: str
    synced_devices: List[UserDeviceSyncResponse]
    total_synced: int
    total_devices: int

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

# --- Shift-based Reports Schemas ---
class ShiftDayEmployee(BaseModel):
    """Данные сотрудника для дня смены."""
    user_id: int
    user_name: str
    hikvision_id: str
    shift_start_time: Optional[str] = None  # Время начала смены в формате "HH:MM"
    shift_duration_hours: Optional[float] = None  # Продолжительность смены в часах (разница между start и end)
    first_entry_time: Optional[str] = None  # Время первого входа за смену (ISO format)
    delay_minutes: Optional[int] = None  # Опоздание в минутах (если есть)
    last_entry_exit_time: Optional[str] = None  # Время последнего входа/выхода (ISO format)
    last_event_type: Optional[str] = None  # "entry" или "exit"
    hours_worked_total: Optional[float] = None  # Общее время работы (часы в день)
    hours_in_shift: float  # Время за смену
    hours_outside_shift: float  # Время вне смены
    status: str  # "Present", "Absent", "Present (no exit)"

class DaySchedule(BaseModel):
    """Расписание на один день недели."""
    start: str  # Время начала в формате "HH:MM" (например, "09:00")
    end: str  # Время окончания в формате "HH:MM" (например, "18:00")
    enabled: bool = True  # Включен ли этот день

class ShiftDay(BaseModel):
    """Данные для одного дня недели смены."""
    day_of_week: int  # 0-6 (0=Monday, 6=Sunday)
    day_name: str  # Название дня недели
    is_active: bool  # Активен ли этот день (для выбранной даты)
    schedule: Optional[DaySchedule] = None  # Расписание на этот день
    employees: List[ShiftDayEmployee]  # Список сотрудников для этого дня

class ShiftReport(BaseModel):
    """Отчет по одной смене."""
    shift_id: int
    shift_name: str
    shift_description: Optional[str] = None
    days: List[ShiftDay]  # Список дней недели (обычно только активный день)
    active_day: int  # Активный день недели для выбранной даты (0-6)

class ShiftReportResponse(BaseModel):
    """Ответ endpoint /reports/daily с группировкой по сменам."""
    shifts: List[ShiftReport]
    report_date: str  # Дата отчета (YYYY-MM-DD)

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
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: str = UserRole.CLEANER.value
    is_active: bool = True

class SystemUserCreate(SystemUserBase):
    """Схема для создания пользователя системы."""
    password: str

class SystemUserUpdate(BaseModel):
    """Схема для обновления пользователя системы."""
    email: Optional[EmailStr] = None
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
    
    @field_validator('start_date', 'end_date', mode='before')
    @classmethod
    def parse_date_string(cls, v):
        """Конвертирует строку даты в datetime, если необходимо."""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            # Пробуем разные форматы
            try:
                # Формат "YYYY-MM-DD"
                if len(v) == 10 and v.count('-') == 2:
                    return datetime.strptime(v, "%Y-%m-%d")
                # Формат ISO с T
                if 'T' in v or 't' in v or '_' in v:
                    return datetime.fromisoformat(v.replace('Z', '+00:00'))
                # Пробуем стандартный парсинг
                return datetime.fromisoformat(v)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid date format: {v}. Expected YYYY-MM-DD or ISO datetime format.")
        return v

class UserShiftAssignmentCreate(UserShiftAssignmentBase):
    """Схема для создания привязки."""
    pass

class UserShiftAssignmentUpdate(BaseModel):
    """Схема для обновления привязки."""
    shift_id: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: Optional[bool] = None
    
    @field_validator('start_date', 'end_date', mode='before')
    @classmethod
    def parse_date_string(cls, v):
        """Конвертирует строку даты в datetime, если необходимо."""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            # Пробуем разные форматы
            try:
                # Формат "YYYY-MM-DD"
                if len(v) == 10 and v.count('-') == 2:
                    return datetime.strptime(v, "%Y-%m-%d")
                # Формат ISO с T
                if 'T' in v or 't' in v or '_' in v:
                    return datetime.fromisoformat(v.replace('Z', '+00:00'))
                # Пробуем стандартный парсинг
                return datetime.fromisoformat(v)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid date format: {v}. Expected YYYY-MM-DD or ISO datetime format.")
        return v

class UserShiftAssignmentResponse(UserShiftAssignmentBase):
    """Схема ответа с данными привязки."""
    id: int
    created_at: datetime
    updated_at: datetime
    user_name: Optional[str] = None
    shift_name: Optional[str] = None

    class Config:
        from_attributes = True