import json
import logging
from typing import Dict, Any, Optional
from fastapi import Request
from .config import settings

logger = logging.getLogger(__name__)

WEBHOOK_API_KEY = settings.webhook_api_key


async def parse_multipart_event(request: Request) -> Optional[Dict[str, Any]]:
    """Парсинг MIME multipart события от терминала Hikvision."""
    try:
        content_type = request.headers.get("content-type", "")
        
        if not content_type or "multipart/form-data" not in content_type:
            return None
        
        # Пробуем использовать request.form() для multipart данных
        event_data_from_form = None
        try:
            form = await request.form()
            
            # Ищем поле с JSON данными
            for key, value in form.items():
                field_content = None
                if isinstance(value, str):
                    field_content = value
                elif hasattr(value, 'read'):  # UploadFile
                    try:
                        field_content = await value.read()
                        if isinstance(field_content, bytes):
                            field_content = field_content.decode('utf-8', errors='ignore')
                    except Exception:
                        continue
                else:
                    continue

                if field_content:
                    try:
                        event_data = json.loads(field_content)
                        
                        # Проверяем тип события
                        event_type = event_data.get("eventType", "")
                        if event_type == "heartBeat":
                            return None

                        # Возвращаем данные
                        if "AccessControllerEvent" in event_data:
                            event_data_from_form = event_data
                            break
                        else:
                            event_data_from_form = {"AccessControllerEvent": event_data}
                            break
                    except json.JSONDecodeError:
                        continue
            
            if event_data_from_form:
                return event_data_from_form
                
        except Exception:
            if event_data_from_form:
                return event_data_from_form
            return None

        return None
        
    except Exception as e:
        logger.error(f"[PARSE_MULTIPART] Error parsing multipart event: {e}", exc_info=True)
        return None


async def parse_json_event(request: Request) -> Optional[Dict[str, Any]]:
    """Парсинг JSON события."""
    try:
        body = await request.json()
        
        if "AccessControllerEvent" in body:
            return body
        elif isinstance(body, dict) and any(key in body for key in ["majorEventType", "employeeNoString"]):
            return {"AccessControllerEvent": body}
        
        return None
    except Exception:
        return None

