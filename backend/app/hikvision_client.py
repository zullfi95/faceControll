from typing import Dict, Any, Optional, List, Tuple
import asyncio
import httpx
import uuid
import xml.etree.ElementTree as ET
import json
from datetime import datetime, timedelta, timezone

class HikvisionClient:
    def __init__(self, ip: str, username: str, password: str, use_https: bool = True):
        protocol = "https" if use_https else "http"
        self.base_url = f"{protocol}://{ip}"
        self.username = username
        self.password = password
        self.auth = httpx.DigestAuth(username, password)
        self.timeout = 30
        self._client = None
        self._token = None

    async def _get_client(self):
        if self._client is None:
            if self._token:
                self._client = httpx.AsyncClient(
                    timeout=self.timeout,
                    verify=False
                )
            else:
                self._client = httpx.AsyncClient(
                    auth=self.auth,
                    timeout=self.timeout,
                    verify=False
                )
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def check_connection(self) -> Tuple[bool, Optional[str]]:
        try:
            client = await self._get_client()
            url = f"{self.base_url}/ISAPI/System/deviceInfo"
            if self._token:
                url += f"?token={self._token}"
            response = await client.get(url, timeout=5)
            
            if response.status_code == 200:
                if not self._token:
                    try:
                        await self._get_security_token()
                    except Exception:
                        pass
                return True, None
            elif response.status_code == 401:
                return False, f"Неверные учетные данные (HTTP 401). Проверьте username и password."
            elif response.status_code == 403:
                return False, f"Доступ запрещен (HTTP 403). Пользователь '{self.username}' не имеет необходимых прав."
            elif response.status_code == 404:
                return False, f"Endpoint не найден (HTTP 404). Возможно, устройство не поддерживает ISAPI или использует другую версию протокола."
            else:
                return False, f"Устройство вернуло код ошибки HTTP {response.status_code}"
                
        except httpx.ConnectTimeout:
            error_msg = f"Устройство {self.base_url} недоступно для входящих соединений. Это нормально при использовании webhook - терминал отправляет события на сервер автоматически."
            return False, error_msg
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            error_str = str(e)
            if "SSL" in error_str or "certificate" in error_str.lower():
                error_msg = f"Ошибка SSL-сертификата: {error_str}. Используется самоподписанный сертификат устройства."
                return False, error_msg
            # Для таймаутов и ошибок подключения показываем понятное сообщение для webhook режима
            if "timeout" in error_str.lower() or "connection" in error_str.lower() or "failed" in error_str.lower():
                error_msg = f"Устройство {self.base_url} недоступно для входящих соединений. Это нормально при использовании webhook - терминал отправляет события на сервер автоматически."
            else:
                error_msg = f"Не удалось подключиться к {self.base_url}. Возможные причины:\n- Устройство выключено или недоступно в сети\n- Неверный IP-адрес\n- Проблемы с сетевым подключением\n- Блокировка файрволом\n\nДетали: {error_str}"
            return False, error_msg
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP ошибка {e.response.status_code}: {e.response.text[:200]}"
            return False, error_msg
        except Exception as e:
            error_type = type(e).__name__
            error_msg = f"Неожиданная ошибка подключения ({error_type}): {str(e)}"
            return False, error_msg
    
    async def get_device_info(self) -> Optional[Dict[str, Any]]:
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/ISAPI/System/deviceInfo",
                auth=self.auth,
                timeout=self.timeout
            )
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                device_info = self._xml_to_dict(root)
                result = {
                    "model": device_info.get("deviceName", "unknown"),
                    "serialNumber": device_info.get("serialNumber", "unknown"),
                    "firmwareVersion": device_info.get("firmwareVersion", "unknown"),
                    "deviceID": device_info.get("deviceID", "unknown"),
                }
                return result
            return None
        except Exception:
            return None
    
    def _xml_to_dict(self, element):
        result = {}
        for child in element:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if len(child) == 0:
                result[tag] = child.text
            else:
                result[tag] = self._xml_to_dict(child)
        return result
    
    async def get_user_info_direct(self, employee_no: str) -> Optional[Dict[str, Any]]:
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/ISAPI/AccessControl/UserInfo/Detail?format=json&employeeNo={employee_no}",
                auth=self.auth,
                timeout=self.timeout
            )
            if response.status_code != 200:
                return None
            data = response.json()
            user_info = data.get("UserInfo", {})
            return user_info
        except Exception:
            return None
    
    async def get_user_face_photo(self, employee_no: str) -> Optional[bytes]:
        try:
            user_info = await self.get_user_info_direct(employee_no)
            if not user_info:
                return None
            face_url = user_info.get("faceURL")
            if not face_url:
                return None
            face_url = self._normalize_face_url(face_url)
            client = await self._get_client()
            photo_response = await client.get(
                f"{self.base_url}{face_url}",
                auth=self.auth,
                timeout=self.timeout
            )
            if photo_response.status_code == 200:
                return photo_response.content
            return None
        except Exception:
            return None
    
    def _normalize_face_url(self, face_url: str) -> str:
        if not face_url:
            return ""
        if "@" in face_url:
            face_url = face_url.split("@")[0]
        face_url = face_url.replace("https://", "").replace("http://", "")
        if "/" in face_url:
            parts = face_url.split("/", 1)
            if len(parts) == 2:
                face_url = "/" + parts[1]
        if not face_url.startswith("/"):
            face_url = "/" + face_url
        return face_url
    
    async def get_users(self, max_results: int = 1000) -> Optional[List[Dict[str, Any]]]:
        try:
            client = await self._get_client()
            search_id = str(uuid.uuid4()).replace('-', '')
            payload = {
                "UserInfoSearchCond": {
                    "searchID": search_id,
                    "maxResults": max_results,
                    "searchResultPosition": 0
                }
            }
            response = await client.post(
                f"{self.base_url}/ISAPI/AccessControl/UserInfo/Search?format=json",
                auth=self.auth,
                json=payload,
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                user_info_search = data.get("UserInfoSearch", {})
                users = user_info_search.get("UserInfo", [])
                if not isinstance(users, list):
                    users = [users] if users else []
                return users
            elif response.status_code in [401, 403]:
                raise PermissionError(f"User '{self.username}' lacks permission to access UserInfo/Search (HTTP {response.status_code})")
            return None
        except PermissionError:
            raise
        except Exception:
            return None

    async def create_user_basic(
        self,
        employee_no: str,
        name: str,
        group_id: Optional[int] = None
    ) -> Dict[str, Any]:
        try:
            await self.check_connection()
            http_client = await self._get_client()
            begin_time = datetime.now().strftime("%Y-%m-%dT00:00:00")
            end_time = (datetime.now() + timedelta(days=3650)).strftime("%Y-%m-%dT23:59:59")
            user_data = {
                "UserInfo": {
                    "employeeNo": employee_no,
                    "name": name,
                    "userType": "normal",
                    "Valid": {
                        "enable": True,
                        "beginTime": begin_time,
                        "endTime": end_time,
                        "timeType": "local"
                    },
                    "gender": "unknown",
                    "doorRight": "1",
                    "RightPlan": [
                        {
                            "doorNo": 1,
                            "planTemplateNo": "1"
                        }
                    ]
                }
            }
            if group_id is not None:
                user_data["UserInfo"]["groupId"] = group_id
            else:
                user_data["UserInfo"]["groupId"] = 1
            url = f"{self.base_url}/ISAPI/AccessControl/UserInfo/Record?format=json"
            if self._token:
                url += f"&token={self._token}"
            response = await http_client.post(url, json=user_data, timeout=self.timeout)
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": f"User {employee_no} created successfully"
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "message": f"Failed to create user: HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Error creating user: {str(e)}"
            }

    async def upload_face_image_to_terminal(
        self,
        employee_no: str,
        image_bytes: bytes
    ) -> Dict[str, Any]:
        """
        Загрузка фото лица на терминал через ISAPI FaceDataRecord.
        
        Args:
            employee_no: ID сотрудника
            image_bytes: Байты изображения
        
        Returns:
            Dict с результатом загрузки
        """
        try:
            connected, error_msg = await self.check_connection()
            if not connected:
                return {
                    "success": False,
                    "error": f"Terminal is not accessible. {error_msg or 'Check network connection.'}"
                }
            
            http_client = await self._get_client()
            boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
            
            # Формируем multipart/form-data с изображением
            face_data = {
                "faceLibType": "blackFD",
                "FDID": "1",
                "FPID": employee_no
            }
            face_data_str = json.dumps(face_data, separators=(',', ':'))
            
            # Создаем multipart body с JSON данными и изображением
            body_parts = [
                f'--{boundary}\r\n',
                f'Content-Disposition: form-data; name="FaceDataRecord"\r\n',
                f'Content-Type: application/json\r\n',
                f'\r\n',
                f'{face_data_str}\r\n',
                f'--{boundary}\r\n',
                f'Content-Disposition: form-data; name="faceImage"; filename="face.jpg"\r\n',
                f'Content-Type: image/jpeg\r\n',
                f'\r\n'
            ]
            
            # Объединяем заголовки и изображение
            body_start = ''.join(body_parts).encode('utf-8')
            body_end = f'\r\n--{boundary}--\r\n'.encode('utf-8')
            body = body_start + image_bytes + body_end
            
            url = f"{self.base_url}/ISAPI/Intelligent/FDLib/FaceDataRecord?format=json"
            if self._token:
                url += f"&token={self._token}"
            
            response = await http_client.post(
                url,
                content=body,
                headers={
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "Content-Length": str(len(body))
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    if response_data.get("statusCode") == 1:
                        return {
                            "success": True,
                            "message": f"Face image uploaded successfully for user {employee_no}"
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"Upload failed: {response_data}",
                            "message": f"Face image upload failed for user {employee_no}"
                        }
                except:
                    return {
                        "success": True,
                        "message": f"Face image uploaded successfully for user {employee_no}"
                    }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text[:500]}",
                    "message": f"Face image upload failed for user {employee_no}: HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Error uploading face image: {str(e)}"
            }
    
    async def setup_user_face_fdlib(
        self,
        employee_no: str,
        face_url: str
    ) -> Dict[str, Any]:
        try:
            connected, error_msg = await self.check_connection()
            if not connected:
                return {
                    "success": False,
                    "error": f"Terminal is not accessible. {error_msg or 'Check network connection.'}"
                }
            http_client = await self._get_client()
            boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
            face_data = {
                "faceLibType": "blackFD",
                "FDID": "1",
                "FPID": employee_no,
                "faceURL": face_url
            }
            face_data_str = json.dumps(face_data, separators=(',', ':'))
            body_parts = [
                f'--{boundary}\r\nContent-Disposition: form-data; name="FaceDataRecord"\r\n\r\n{face_data_str}\r\n',
                f'--{boundary}--\r\n'
            ]
            body = ''.join(body_parts).encode('utf-8')
            url = f"{self.base_url}/ISAPI/Intelligent/FDLib/FDSetUp?format=json"
            response = await http_client.put(
                url,
                content=body,
                headers={
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "Content-Length": str(len(body))
                },
                timeout=self.timeout
            )
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    if response_data.get("statusCode") == 1:
                        return {
                            "success": True,
                            "message": f"Face data setup completed for user {employee_no}"
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"FDSetUp failed: {response_data}",
                            "message": f"Face setup failed for user {employee_no}"
                        }
                except:
                    return {
                        "success": True,
                        "message": f"Face data setup completed for user {employee_no}"
                    }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "message": f"Face setup failed for user {employee_no}: HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Error setting up face data: {str(e)}"
            }

    async def _get_security_token(self) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                auth=self.auth,
                verify=False,
                timeout=self.timeout
            ) as client:
                response = await client.get(
                    f"{self.base_url}/ISAPI/Security/token?format=json"
                )
                if response.status_code == 200:
                    data = response.json()
                    token = data.get("Token", {}).get("value")
                    if token:
                        self._token = token
                        return {
                            "success": True,
                            "token": token
                        }
                    else:
                        return {
                            "success": False,
                            "error": "Token not found in response"
                        }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


    async def start_face_capture_mode(self, max_retries: int = 3, retry_delay: float = 2.0):
        """
        Запускает режим захвата фото лица на терминале.
        Использует ISAPI/AccessControl/CaptureFaceData для запуска захвата.

        Args:
            max_retries: Максимальное количество повторных проверок статуса захвата
            retry_delay: Задержка между проверками в секундах

        Returns:
            Dict с результатом операции
        """
        try:
            connected, error_msg = await self.check_connection()
            if not connected:
                return {
                    "success": False,
                    "error": f"Terminal is not accessible. {error_msg or 'Check network connection.'}"
                }

            http_client = await self._get_client()

            capture_xml = """<CaptureFaceDataCond version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
    <captureInfrared>false</captureInfrared>
    <dataType>url</dataType>
</CaptureFaceDataCond>"""

            response = await http_client.post(
                f"{self.base_url}/ISAPI/AccessControl/CaptureFaceData",
                content=capture_xml,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                auth=self.auth,
                timeout=self.timeout
            )

            if response.status_code == 200:
                for attempt in range(max_retries + 1):
                    try:
                        root = ET.fromstring(response.text)
                        face_data_url = None
                        capture_progress = 0
                        for elem in root.iter():
                            if elem.tag.endswith('faceDataUrl') or elem.tag.endswith('faceURL'):
                                face_data_url = elem.text
                            elif elem.tag.endswith('captureProgress'):
                                try:
                                    capture_progress = int(elem.text)
                                except (ValueError, TypeError):
                                    capture_progress = 0

                        if capture_progress == 100 and face_data_url:
                            return {
                                "success": True,
                                "message": "Face capture completed successfully",
                                "face_data_url": face_data_url,
                                "capture_progress": capture_progress
                            }
                        elif capture_progress < 100 and attempt < max_retries:
                            await asyncio.sleep(retry_delay)

                            response = await http_client.post(
                                f"{self.base_url}/ISAPI/AccessControl/CaptureFaceData",
                                content=capture_xml,
                                headers={"Content-Type": "application/x-www-form-urlencoded"},
                                auth=self.auth,
                                timeout=self.timeout
                            )

                            if response.status_code != 200:
                                break
                            continue
                        elif capture_progress < 100:
                            return {
                                "success": True,
                                "message": f"Face capture in progress ({capture_progress}%). Please present your face to the terminal.",
                                "face_data_url": None,
                                "capture_progress": capture_progress,
                                "status": "waiting",
                                "note": "Terminal is now waiting for face detection. Call this endpoint again after presenting face."
                            }
                        else:
                            return {
                                "success": True,
                                "message": "Face capture completed, but photo URL not available",
                                "face_data_url": None,
                                "capture_progress": capture_progress
                            }

                    except ET.ParseError:
                        return {
                            "success": True,
                            "message": "Face capture started successfully"
                        }

                return {
                    "success": False,
                    "error": f"Face capture timeout after {max_retries + 1} attempts",
                    "message": "Terminal did not detect face within timeout period"
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "message": f"Failed to start face capture: HTTP {response.status_code}"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Error starting face capture: {str(e)}"
            }

    async def get_attendance_records(self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None, max_records: int = 100) -> List[Dict[str, Any]]:
        """
        Получение записей посещаемости (событий аутентификации) с терминала.

        Args:
            start_time: Начало периода (по умолчанию - последние 24 часа)
            end_time: Конец периода (по умолчанию - сейчас)
            max_records: Максимальное количество записей

        Returns:
            Список событий аутентификации
        """
        try:
            connected, error_msg = await self.check_connection()
            if not connected:
                return []

            http_client = await self._get_client()

            if not start_time:
                start_time = datetime.now() - timedelta(days=1)
            if not end_time:
                end_time = datetime.now()

            search_data = {
                "EventSearchCond": {
                    "searchID": str(uuid.uuid4()).replace('-', ''),
                    "searchResultPosition": 0,
                    "maxResults": max_records,
                    "eventType": "accessControllerEvent",
                    "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%S")
                }
            }


            url = f"{self.base_url}/ISAPI/Event/notification/eventSearch?format=json"
            if self._token:
                url += f"&token={self._token}"

            response = await http_client.post(url, json=search_data, timeout=self.timeout)

            
            if response.status_code == 200:
                try:
                    result = response.json()
                    
                    events = None
                    if "EventNotificationList" in result:
                        events = result.get("EventNotificationList", {}).get("EventNotification", [])
                    elif "EventNotification" in result:
                        events = result.get("EventNotification", [])
                    elif "AcsEvent" in result:
                        events = result.get("AcsEvent", {}).get("InfoList", [])
                    elif isinstance(result, list):
                        events = result
                    
                    if events is None:
                        events = []
                    
                    if not isinstance(events, list):
                        events = [events] if events else []


                    attendance_records = []
                    for event in events:
                        if not isinstance(event, dict):
                            continue
                            
                        event_type = event.get("eventType") or event.get("eventTypeAlias")
                        if event_type in ["accessControllerEvent", "AccessControllerEvent"] or "AccessControllerEvent" in event:
                            access_event = event.get("AccessControllerEvent") or event
                            record = self._parse_access_event({"AccessControllerEvent": access_event} if "AccessControllerEvent" not in event else event)
                            if record:
                                attendance_records.append(record)
                        elif "majorEventType" in event or "employeeNoString" in event:
                            record = self._parse_access_event({"AccessControllerEvent": event})
                            if record:
                                attendance_records.append(record)

                    return attendance_records

                except Exception as e:
                    pass
            else:
                pass

            acs_url = f"{self.base_url}/ISAPI/AccessControl/AcsEvent?format=json"
            if self._token:
                acs_url += f"&token={self._token}"

            acs_search_data = {
                "AcsEventCond": {
                    "searchID": str(uuid.uuid4()).replace('-', ''),
                    "searchResultPosition": 0,
                    "maxResults": max_records,
                    "major": 0,  # 0 = все типы событий, или можно указать конкретный (5 = Access Control)
                    "minor": 0,  # 0 = все подтипы, или можно указать конкретный
                    "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%S%z").replace("+0000", "+00:00") if start_time.tzinfo else start_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%S%z").replace("+0000", "+00:00") if end_time.tzinfo else end_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeReverseOrder": True  # Новые события первыми
                }
            }
            
            try:
                acs_response = await http_client.post(acs_url, json=acs_search_data, timeout=self.timeout)
                if acs_response.status_code == 200:
                    try:
                        acs_result = acs_response.json()
                        
                        events = None
                        if "AcsEvent" in acs_result:
                            acs_event = acs_result["AcsEvent"]
                            if "InfoList" in acs_event:
                                info_list = acs_event["InfoList"]
                                if isinstance(info_list, list):
                                    events = info_list
                                elif isinstance(info_list, dict):
                                    if "Info" in info_list:
                                        info = info_list["Info"]
                                        events = info if isinstance(info, list) else [info] if info else []
                                    else:
                                        for key, value in info_list.items():
                                            if isinstance(value, list):
                                                events = value
                                                break
                            elif "Info" in acs_event:
                                info = acs_event["Info"]
                                events = info if isinstance(info, list) else [info] if info else []
                            elif isinstance(acs_event, list):
                                events = acs_event
                        
                        if events is None:
                            for key in ["InfoList", "Info", "eventList", "events"]:
                                if key in acs_result:
                                    value = acs_result[key]
                                    events = value if isinstance(value, list) else [value] if value else []
                                    break
                        
                        if events is None:
                            events = []
                        
                        if not isinstance(events, list):
                            events = [events] if events else []
                        
                        
                        attendance_records = []
                        for event in events:
                            if isinstance(event, dict):
                                if "AccessControllerEvent" in event:
                                    record = self._parse_access_event(event)
                                elif "major" in event or "majorEventType" in event or "employeeNoString" in event:
                                    record = self._parse_access_event(event)
                                else:
                                    record = self._parse_access_event(event)
                                
                                if record:
                                    attendance_records.append(record)
                        
                        if attendance_records:
                            return attendance_records
                    except Exception as e:
                        pass
                else:
                    pass
            except Exception as e:
                pass
            return []

        except Exception as e:
            return []

    def _map_event_type(self, major_event_type: int, sub_event_type: int) -> str:
        """
        Маппинг кодов событий Hikvision на текстовые описания.
        
        Args:
            major_event_type: Основной тип события
            sub_event_type: Подтип события
            
        Returns:
            Текстовое описание типа события
        """
        event_key = f"{major_event_type}_{sub_event_type}"
        
        event_type_map = {
            "1_1": "Door Open",
            "1_2": "Door Closed",
            "1_3": "Door Opening",
            "1_4": "Door Closing",
            
            "2_1": "Authenticated via Face",
            "2_2": "Authenticated via Card",
            "2_3": "Authenticated via Fingerprint",
            "2_4": "Authenticated via Password",
            "2_5": "Authenticated via QR Code",
            "2_6": "Authenticated via Multiple",
            "2_7": "Person Not Assigned",
            "2_8": "Authentication Failed",
            
            "3_1": "Entry",
            "3_2": "Exit",
            
            "4_1": "System Startup",
            "4_2": "System Shutdown",
            "4_3": "System Error",
            
            "5_1": "Remote: Login",
            "5_2": "Local: Login",
            "5_3": "Remote: Logout",
            "5_4": "Local: Logout",
            
            "6_1": "Card Registered",
            "6_2": "Card Deleted",
            "6_3": "Card Expired",
            
            "7_1": "User Added",
            "7_2": "User Deleted",
            "7_3": "User Modified",
            
            "8_1": "Door Forced Open",
            "8_2": "Door Held Open",
            "8_3": "Door Tampered",
        }
        
        description = event_type_map.get(event_key)
        if description:
            return description
        
        major_type_names = {
            1: "Access",
            2: "Authentication",
            3: "Entry/Exit",
            4: "System",
            5: "Login",
            6: "Card",
            7: "User",
            8: "Door",
        }
        
        major_name = major_type_names.get(major_event_type, "Unknown")
        return f"{major_name} Event ({major_event_type}.{sub_event_type})"

    def _parse_access_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Парсит событие доступа и конвертирует в стандартный формат с полными данными.

        Поддерживает структуры:
        - AccessControllerEvent (из webhook/alertStream)
        - AcsEvent.InfoList (из POST /ISAPI/AccessControl/AcsEvent)
        - IDCardInfoEvent, QRCodeEvent, FaceTemperatureMeasurementEvent

        Args:
            event: Событие от Hikvision (может быть из разных источников)

        Returns:
            Словарь с полями: employee_no, name, card_no, card_reader_id, event_type_code,
            event_type_description, timestamp, event_type, terminal_ip, remote_host_ip
        """
        try:

            event_info = event.get("AccessControllerEvent", {})

            if not event_info:
                if "IDCardInfoEvent" in event:
                    event_info = event.get("IDCardInfoEvent", {})
                elif "QRCodeEvent" in event:
                    event_info = event.get("QRCodeEvent", {})
                elif "FaceTemperatureMeasurementEvent" in event:
                    event_info = event.get("FaceTemperatureMeasurementEvent", {})
                else:
                    event_info = event

            major_event_type = event_info.get("majorEventType") or event_info.get("major", 0)
            sub_event_type = event_info.get("subEventType") or event_info.get("minor", 0)
            event_type_code = f"{major_event_type}_{sub_event_type}" if major_event_type or sub_event_type else None
            event_type_description = self._map_event_type(major_event_type, sub_event_type) if major_event_type or sub_event_type else None

            employee_no = event_info.get("employeeNoString") or event_info.get("employeeNo")
            if employee_no:
                employee_no = str(employee_no)

            timestamp_str = event_info.get("time") or event_info.get("dateTime") or event.get("dateTime")
            timestamp = None
            
            if timestamp_str:
                try:
                    for fmt in [
                        "%Y-%m-%dT%H:%M:%S",
                        "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%dT%H:%M:%S.%f",
                        "%Y-%m-%dT%H:%M:%SZ",
                        "%Y-%m-%dT%H:%M:%S+00:00"
                    ]:
                        try:
                            timestamp = datetime.strptime(timestamp_str.replace("Z", "").replace("+00:00", ""), fmt.split(".")[0])
                            break
                        except ValueError:
                            continue
                    else:
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                            if timestamp.tzinfo is None:
                                timestamp = timestamp.replace(tzinfo=timezone.utc)
                        except Exception as iso_error:
                            pass
                except Exception as e:
                    pass
            
            if not timestamp:
                timestamp = datetime.now(timezone.utc)

            if major_event_type == 5:
                if sub_event_type == 21:
                    event_type = "entry"  # Local: Login
                elif sub_event_type == 22:
                    event_type = "exit"  # Local: Logout
                elif sub_event_type == 75:
                    event_type = "entry"  # Authenticated via... (обычно вход)
                else:
                    if event_type_description:
                        if "Entry" in event_type_description or "Login" in event_type_description or "Open" in event_type_description:
                            event_type = "entry"
                        elif "Exit" in event_type_description or "Logout" in event_type_description or "Closed" in event_type_description:
                            event_type = "exit"
                        else:
                            event_type = "entry"  # По умолчанию вход
                    else:
                        event_type = "entry"
            else:
                card_reader = event_info.get("cardReaderNo") or event_info.get("cardReaderNo", 0)
                if isinstance(card_reader, str):
                    try:
                        card_reader = int(card_reader)
                    except:
                        card_reader = 0

                if event_type_description:
                    if "Entry" in event_type_description or "Open" in event_type_description:
                        event_type = "entry"
                    elif "Exit" in event_type_description or "Closed" in event_type_description:
                        event_type = "exit"
                    else:
                        event_type = "entry" if card_reader % 2 == 0 else "exit"
                else:
                    event_type = "entry" if card_reader % 2 == 0 else "exit"

            name = event_info.get("name")
            card_no = event_info.get("cardNo") or event_info.get("cardNumber") or event_info.get("cardNoString")
            
            card_reader = event_info.get("cardReaderNo")
            if card_reader is not None:
                card_reader_id = str(card_reader)
            else:
                card_reader_id = None
            
            terminal_ip = self.base_url.replace("https://", "").replace("http://", "").split(":")[0]
            
            remote_host_ip = (
                event_info.get("remoteHostAddr") or  # Из AcsEvent (как в HAR файле)
                event_info.get("remoteHostIP") or 
                event_info.get("remoteHostIp") or 
                event.get("ipAddress") or 
                event_info.get("ipAddress")
            )

            result = {
                "employee_no": employee_no,
                "name": name,
                "card_no": card_no,
                "card_reader_id": card_reader_id,
                "event_type_code": event_type_code,
                "event_type_description": event_type_description,
                "timestamp": timestamp,
                "event_type": event_type,  # Базовый тип для совместимости
                "terminal_ip": terminal_ip,
                "remote_host_ip": remote_host_ip
            }

            return result

        except Exception as e:
            return None

    async def subscribe_to_events(self, event_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Подписка на события от устройства через ISAPI.
        
        Args:
            event_types: Список типов событий для подписки (по умолчанию "All")
        
        Returns:
            Dict с результатом подписки
        """
        try:
            http_client = await self._get_client()
            
            if event_types is None or "All" in event_types:
                event_type_xml = "<eventType>All</eventType>"
            else:
                event_types_xml = "".join([f"<eventType>{et}</eventType>" for et in event_types])
                event_type_xml = event_types_xml
            
            xml_body = f"<EventNotification>{event_type_xml}</EventNotification>"
            
            url = f"{self.base_url}/ISAPI/Event/notification/subscribeEvent"
            if self._token:
                url += f"?token={self._token}"
            
            response = await http_client.post(
                url,
                content=xml_body,
                headers={"Content-Type": "application/xml"},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "Successfully subscribed to events"
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def listen_to_alert_stream(
        self, 
        callback: callable,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Прослушивание потока событий в реальном времени через alertStream.
        
        Args:
            callback: Асинхронная функция-обработчик для новых событий (async def callback(event: Dict))
            timeout: Таймаут для подключения (None = бесконечно)
        
        Returns:
            Dict с результатом операции
        """
        try:
            http_client = await self._get_client()
            
            url = f"{self.base_url}/ISAPI/Event/notification/alertStream"
            if self._token:
                url += f"?token={self._token}"
            
            
            async with http_client.stream("GET", url, timeout=timeout or self.timeout) as response:
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text[:200]}"
                    }
                
                
                buffer = ""
                current_part = {}
                in_json = False
                json_content = ""
                boundary = None
                
                async for line_bytes in response.aiter_bytes():
                    if not line_bytes:
                        continue
                    
                    try:
                        line = line_bytes.decode('utf-8', errors='ignore')
                        buffer += line
                        
                        if boundary is None and line.strip().startswith('--'):
                            boundary = line.strip()
                            continue
                        
                        if boundary and line.strip() == boundary or line.strip() == boundary + '--':
                            if json_content and current_part.get('name'):
                                try:
                                    event_data = json.loads(json_content)
                                    
                                    parsed_event = None
                                    if current_part.get('name') == 'AccessControllerEvent':
                                        parsed_event = self._parse_access_event(event_data)
                                    elif 'AccessControllerEvent' in event_data:
                                        parsed_event = self._parse_access_event(event_data)
                                    
                                    if parsed_event:
                                        if asyncio.iscoroutinefunction(callback):
                                            await callback(parsed_event)
                                        else:
                                            callback(parsed_event)
                                    
                                except json.JSONDecodeError as e:
                                    pass
                            current_part = {}
                            json_content = ""
                            in_json = False
                            continue
                        
                        if ':' in line and not in_json:
                            if line.lower().startswith('content-disposition:'):
                                if 'name=' in line:
                                    name = line.split('name=')[1].strip().strip('"')
                                    current_part['name'] = name
                            elif line.lower().startswith('content-type:'):
                                current_part['content_type'] = line.split(':', 1)[1].strip()
                            elif line.strip() == '':
                                in_json = True
                                continue
                        
                        if in_json and current_part.get('name'):
                            json_content += line
                            
                    except Exception as e:
                        continue
                
                if json_content and current_part.get('name'):
                    try:
                        event_data = json.loads(json_content)
                        parsed_event = self._parse_access_event(event_data)
                        if parsed_event:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(parsed_event)
                            else:
                                callback(parsed_event)
                    except:
                        pass
            
            return {
                "success": True,
                "message": "Alert stream ended"
            }
            
        except asyncio.TimeoutError:
            return {
                "success": True,
                "message": "Alert stream timeout (expected)"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_http_hosts(self) -> Dict[str, Any]:
        """
        Получение текущих настроек HTTP Listening (HTTP Hosts) для уведомлений.
        
        Returns:
            Словарь с настройками HTTP хостов или ошибка
        """
        try:
            client = await self._get_client()
            url = f"{self.base_url}/ISAPI/Event/notification/httpHosts?format=json"
            
            response = await client.get(url)
            
            if response.status_code == 200:
                if not response.content or len(response.content) == 0:
                    return {
                        "success": False,
                        "error": "Empty response from device - HTTP Listening may not be configured",
                        "requires_manual_setup": True
                    }
                
                try:
                    result = response.json()
                    return {
                        "success": True,
                        "data": result
                    }
                except json.JSONDecodeError:
                    try:
                        root = ET.fromstring(response.text)
                        http_host_data = {}
                        
                        http_host_elem = root.find(".//{http://www.isapi.org/ver20/XMLSchema}HttpHostNotification")
                        if http_host_elem is None:
                            http_host_elem = root.find(".//HttpHostNotification")
                        
                        if http_host_elem is not None:
                            for child in http_host_elem:
                                tag = child.tag
                                if '}' in tag:
                                    tag = tag.split('}')[1]
                                http_host_data[tag] = child.text if child.text else ""
                            
                            if not http_host_data:
                                for child in root:
                                    if 'HttpHostNotification' in child.tag:
                                        for subchild in child:
                                            tag = subchild.tag
                                            if '}' in tag:
                                                tag = tag.split('}')[1]
                                            http_host_data[tag] = subchild.text if subchild.text else ""
                        
                        
                        return {
                            "success": True,
                            "data": {
                                "HttpHostNotificationList": {
                                    "HttpHostNotification": http_host_data if http_host_data else {}
                                }
                            },
                            "format": "xml",
                            "raw_xml": response.text[:500]  # Для отладки
                        }
                    except ET.ParseError as xml_error:
                        return {
                            "success": False,
                            "error": f"Response is neither JSON nor valid XML: {response.text[:200] if response.text else 'Empty response'}",
                            "response_text": response.text[:500] if response.text else "",
                            "requires_manual_setup": True
                        }
            elif response.status_code == 404:
                return {
                    "success": False,
                    "error": "HTTP hosts endpoint not supported",
                    "requires_manual_setup": True
                }
            else:
                error_text = response.text[:500]
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {error_text}",
                    "status_code": response.status_code
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def configure_http_host(
        self,
        server_ip: str,
        server_port: int = 80,
        url_path: str = "/events/webhook",
        protocol: str = "http",
        enabled: bool = True
    ) -> Dict[str, Any]:
        """
        Настройка HTTP Listening (HTTP Host) для отправки событий на сервер.
        
        Args:
            server_ip: IP адрес сервера для отправки событий
            server_port: Порт сервера (по умолчанию 80)
            url_path: Путь на сервере (по умолчанию /events/webhook)
            protocol: Протокол (http или https, по умолчанию http)
            enabled: Включить или выключить отправку событий
        
        Returns:
            Результат настройки
        """
        try:
            client = await self._get_client()
            
            url_json = f"{self.base_url}/ISAPI/Event/notification/httpHosts?format=json"
            payload = {
                "HttpHostNotification": {
                    "httpHostList": {
                        "httpHost": [
                            {
                                "id": 1,
                                "protocol": protocol.upper(),
                                "ipAddress": server_ip,
                                "portNo": server_port,
                                "url": url_path,
                                "addressingFormatType": "ipaddress"
                            }
                        ]
                    }
                }
            }
            
            
            response = await client.put(url_json, json=payload)
            
            if response.status_code not in [200, 201] and "badXmlFormat" not in response.text:
                url_xml = f"{self.base_url}/ISAPI/Event/notification/httpHosts"
                xml_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<HttpHostNotification version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
    <httpHostList>
        <httpHost>
            <id>1</id>
            <protocol>{protocol.upper()}</protocol>
            <ipAddress>{server_ip}</ipAddress>
            <portNo>{server_port}</portNo>
            <url>{url_path}</url>
            <addressingFormatType>ipaddress</addressingFormatType>
        </httpHost>
    </httpHostList>
</HttpHostNotification>"""
                response = await client.put(
                    url_xml,
                    content=xml_body,
                    headers={"Content-Type": "application/xml; charset=UTF-8"}
                )
            
            response_text = response.text if response.text else ""
            
            if response.status_code in [200, 201]:
                result = {}
                try:
                    if response_text.strip().startswith('<?xml') or response_text.strip().startswith('<'):
                        root = ET.fromstring(response_text)
                        result = self._xml_to_dict(root)
                    else:
                        result = response.json() if response.content else {}
                except Exception as parse_error:
                    result = {"raw_response": response_text[:500]}
                
                return {
                    "success": True,
                    "message": "HTTP host configured successfully",
                    "data": result
                }
            elif response.status_code == 404:
                return {
                    "success": False,
                    "error": "HTTP hosts endpoint not supported by this device",
                    "requires_manual_setup": True,
                    "manual_setup_instructions": {
                        "step": "Configure HTTP Listening manually in terminal web interface",
                        "path": "Configuration → Network → HTTP Listening",
                        "settings": {
                            "Event Alarm IP/Domain Name": server_ip,
                            "URL": url_path,
                            "Port": str(server_port),
                            "Protocol": protocol
                        }
                    }
                }
            else:
                error_text = response.text[:500]
                
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {error_text}",
                    "status_code": response.status_code,
                    "requires_manual_setup": True,
                    "manual_setup_instructions": {
                        "step": "Configure HTTP Listening manually in terminal web interface",
                        "path": "Configuration → Network → HTTP Listening",
                        "settings": {
                            "Event Alarm IP/Domain Name": server_ip,
                            "URL": url_path,
                            "Port": str(server_port),
                            "Protocol": protocol
                        }
                    }
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "requires_manual_setup": True,
                "manual_setup_instructions": {
                    "step": "Configure HTTP Listening manually in terminal web interface",
                    "path": "Configuration → Network → HTTP Listening",
                    "settings": {
                        "Event Alarm IP/Domain Name": server_ip,
                        "URL": url_path,
                        "Port": str(server_port),
                        "Protocol": protocol
                    }
                }
            }

