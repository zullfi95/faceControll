from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from .enums import UserRole

class Device(Base):
    """Модель устройства Hikvision."""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Название устройства (например, "Терминал Вход")
    ip_address = Column(String, nullable=False, unique=True)
    username = Column(String, nullable=False)
    password_encrypted = Column(Text, nullable=False)  # Зашифрованный пароль
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_sync = Column(DateTime(timezone=True), nullable=True)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    hikvision_id = Column(String, unique=True, index=True)  # ID внутри терминала (например, "1001")
    full_name = Column(String)
    department = Column(String, nullable=True)
    role = Column(String, nullable=True, default=UserRole.CLEANER.value)  # Роль пользователя
    is_active = Column(Boolean, default=True)
    photo_path = Column(String, nullable=True)  # Путь к сохраненному фото
    synced_to_device = Column(Boolean, default=False)  # Синхронизирован ли с устройством
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    events = relationship("AttendanceEvent", back_populates="user")
    shift_assignments = relationship("UserShiftAssignment", back_populates="user", cascade="all, delete-orphan")

class AttendanceEvent(Base):
    __tablename__ = "attendance_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)  # Может быть NULL для событий без пользователя

    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    event_type = Column(String)  # "entry" (вход) или "exit" (выход) - базовый тип для совместимости
    terminal_ip = Column(String)  # IP адрес терминала, с которого пришло событие
    
    # Расширенные поля из ISAPI событий
    employee_no = Column(String, index=True, nullable=True)  # ID сотрудника из терминала
    name = Column(String, nullable=True)  # Имя сотрудника
    card_no = Column(String, nullable=True)  # Номер карты
    card_reader_id = Column(String, nullable=True)  # ID считывателя карт
    event_type_code = Column(String, nullable=True)  # Код типа события (majorEventType + subEventType)
    event_type_description = Column(String, nullable=True)  # Текстовое описание типа события
    remote_host_ip = Column(String, nullable=True)  # IP адрес удаленного хоста

    # Связь с пользователем (lazy loading для оптимизации)
    user = relationship("User", back_populates="events", lazy="joined")


class WorkShift(Base):
    """Модель рабочей смены с настройкой по дням недели."""
    __tablename__ = "work_shifts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Название смены (например, "Утренняя смена", "Ночная смена")
    description = Column(String, nullable=True)  # Описание смены
    
    # Настройки по дням недели (0=Понедельник, 6=Воскресенье)
    # JSON структура: {"0": {"start": "09:00", "end": "18:00", "enabled": true}, ...}
    schedule = Column(JSON, nullable=False)  # Расписание по дням недели
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user_assignments = relationship("UserShiftAssignment", back_populates="shift", cascade="all, delete-orphan")


class UserShiftAssignment(Base):
    """Модель привязки пользователя к рабочей смене."""
    __tablename__ = "user_shift_assignments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    shift_id = Column(Integer, ForeignKey("work_shifts.id"), nullable=False, index=True)
    
    # Дата начала действия привязки
    start_date = Column(DateTime(timezone=True), nullable=True)
    # Дата окончания действия привязки (NULL = бессрочно)
    end_date = Column(DateTime(timezone=True), nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="shift_assignments")
    shift = relationship("WorkShift", back_populates="user_assignments")


class SystemUser(Base):
    """Модель пользователя системы (для аутентификации в веб-интерфейсе)."""
    __tablename__ = "system_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, nullable=False, default=UserRole.CLEANER.value)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

