from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# Нужен для типизации вызовов внутри кода (не для API)
class InternalEventCreate(BaseModel):
    hikvision_id: Optional[str] = None  # Может быть None для событий без пользователя
    event_type: str
    terminal_ip: str
    timestamp: datetime
    
    # Расширенные поля из ISAPI событий
    employee_no: Optional[str] = None
    name: Optional[str] = None
    card_no: Optional[str] = None
    card_reader_id: Optional[str] = None
    event_type_code: Optional[str] = None
    event_type_description: Optional[str] = None
    remote_host_ip: Optional[str] = None

