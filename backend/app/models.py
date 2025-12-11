from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

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
    is_active = Column(Boolean, default=True)
    photo_path = Column(String, nullable=True)  # Путь к сохраненному фото
    synced_to_device = Column(Boolean, default=False)  # Синхронизирован ли с устройством
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    events = relationship("AttendanceEvent", back_populates="user")

class AttendanceEvent(Base):
    __tablename__ = "attendance_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    event_type = Column(String)  # "entry" (вход) или "exit" (выход)
    terminal_ip = Column(String)  # IP адрес терминала, с которого пришло событие

    # Связь с пользователем (lazy loading для оптимизации)
    user = relationship("User", back_populates="events", lazy="joined")

