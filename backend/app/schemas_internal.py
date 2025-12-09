from pydantic import BaseModel
from datetime import datetime

# Нужен для типизации вызовов внутри кода (не для API)
class InternalEventCreate(BaseModel):
    hikvision_id: str
    event_type: str
    terminal_ip: str
    timestamp: datetime

