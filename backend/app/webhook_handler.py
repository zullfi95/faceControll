import json
import logging
from typing import Dict, Any, Optional
from fastapi import Request
import os

logger = logging.getLogger(__name__)

WEBHOOK_API_KEY = os.getenv("WEBHOOK_API_KEY", "")


async def parse_multipart_event(request: Request) -> Optional[Dict[str, Any]]:
    """Парсинг MIME multipart события от терминала Hikvision."""
    try:
        content_type = request.headers.get("content-type", "")
        
        if not content_type or "multipart/form-data" not in content_type:
            logger.warning(f"[PARSE_MULTIPART] Unexpected content-type: '{content_type}'")
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
                    except Exception as read_error:
                        logger.warning(f"[PARSE_MULTIPART] Failed to read file field '{key}': {read_error}")
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
                
        except Exception as form_error:
            logger.warning(f"[PARSE_MULTIPART] Failed to parse as form: {form_error}")
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
    except Exception as e:
        logger.warning(f"[PARSE_JSON] Failed to parse JSON event: {e}")
        return None

