"""
Hikvision Client - Клиент для работы с терминалами Hikvision через ISAPI
"""

from typing import Dict, Any, Optional, List, Tuple, Union
import asyncio
import httpx
import logging
import uuid
import xml.etree.ElementTree as ET
import json
import base64
import hashlib
import secrets
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

class HikvisionClient:
    def __init__(self, ip: str, username: str, password: str, use_https: bool = True):
        """
        Инициализация клиента Hikvision.

        Args:
            ip: IP адрес устройства
            username: Имя пользователя
            password: Пароль
            use_https: Использовать HTTPS (по умолчанию True, как в веб-интерфейсе)
        """
        protocol = "https" if use_https else "http"
        self.base_url = f"{protocol}://{ip}"
        self.username = username
        self.password = password
        # Используем Digest auth согласно документации ISAPI (RFC 2617)
        # Hikvision устройства используют Digest аутентификацию для ISAPI
        self.auth = httpx.DigestAuth(username, password)
        self.timeout = 30
        self._client = None
        self._token = None  # Кэшированный токен

    async def _get_client(self):
        """Получение HTTP клиента с автоматическим выбором аутентификации."""
        if self._client is None:
            # Если у нас есть токен, создаем клиент без auth
            # Токен будет добавляться в URL параметров
            if self._token:
                self._client = httpx.AsyncClient(
                    timeout=self.timeout,
                    verify=False
                )
            else:
                # Иначе используем Digest auth (как в тестах)
                self._client = httpx.AsyncClient(
                    auth=self.auth,  # DigestAuth
                    timeout=self.timeout,
                    verify=False
                )
        return self._client
    
    async def close(self):
        """Закрытие HTTP клиента."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def check_connection(self) -> Tuple[bool, Optional[str]]:
        """
        Проверка доступности устройства через ISAPI.
        
        Returns:
            Кортеж (успех, сообщение_об_ошибке):
            - (True, None) если устройство доступно
            - (False, описание_ошибки) если устройство недоступно
        """
        try:
            logger.info(f"Checking connection to {self.base_url} with username={self.username}")
            client = await self._get_client()

            # Формируем URL с токеном если он есть
            url = f"{self.base_url}/ISAPI/System/deviceInfo"
            if self._token:
                url += f"?token={self._token}"
                logger.info(f"Using token-based auth: {url}")
            else:
                logger.info(f"Using Basic auth: {url}")

            response = await client.get(url, timeout=5)
            
            if response.status_code == 200:
                # При успешном подключении пытаемся получить токен для будущих запросов
                if not self._token:
                    try:
                        token_result = await self._get_security_token()
                        if token_result.get("success"):
                            logger.info(f"Security token obtained for device {self.base_url}")
                        else:
                            logger.warning(f"Failed to get security token: {token_result.get('error')}")
                    except Exception as e:
                        logger.warning(f"Error getting security token: {e}")
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
            error_msg = f"Таймаут подключения. Устройство {self.base_url} не отвечает. Проверьте:\n- Правильность IP-адреса\n- Доступность устройства в сети\n- Настройки файрвола"
            logger.warning(f"[CHECK_CONNECTION] {error_msg}")
            return False, error_msg
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            error_str = str(e)
            # Проверяем, не является ли это ошибкой SSL
            if "SSL" in error_str or "certificate" in error_str.lower():
                error_msg = f"Ошибка SSL-сертификата: {error_str}. Используется самоподписанный сертификат устройства."
                logger.warning(f"[CHECK_CONNECTION] {error_msg}")
                return False, error_msg
            error_msg = f"Не удалось подключиться к {self.base_url}. Возможные причины:\n- Устройство выключено или недоступно в сети\n- Неверный IP-адрес\n- Проблемы с сетевым подключением\n- Блокировка файрволом\n\nДетали: {error_str}"
            logger.warning(f"[CHECK_CONNECTION] {error_msg}")
            return False, error_msg
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP ошибка {e.response.status_code}: {e.response.text[:200]}"
            logger.warning(f"[CHECK_CONNECTION] {error_msg}")
            return False, error_msg
        except Exception as e:
            error_type = type(e).__name__
            error_msg = f"Неожиданная ошибка подключения ({error_type}): {str(e)}"
            logger.warning(f"[CHECK_CONNECTION] {error_msg}", exc_info=True)
            return False, error_msg
    
    async def get_device_info(self) -> Optional[Dict[str, Any]]:
        """
        Получение информации об устройстве.
        Endpoint: GET /ISAPI/System/deviceInfo
        
        Returns:
            Словарь с информацией об устройстве (модель, серийный номер, версия прошивки и т.д.)
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/ISAPI/System/deviceInfo",
                auth=self.auth,
                timeout=self.timeout
            )
            if response.status_code == 200:
                # Парсим XML ответ
                from xml.etree import ElementTree as ET
                root = ET.fromstring(response.text)
                
                # Конвертируем в словарь
                device_info = self._xml_to_dict(root)
                
                # Извлекаем нужные поля
                result = {
                    "model": device_info.get("deviceName", "unknown"),
                    "serialNumber": device_info.get("serialNumber", "unknown"),
                    "firmwareVersion": device_info.get("firmwareVersion", "unknown"),
                    "deviceID": device_info.get("deviceID", "unknown"),
                }
                
                return result
            else:
                logger.warning(f"[GET_DEVICE_INFO] Не удалось получить информацию: HTTP {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"[GET_DEVICE_INFO] Ошибка получения информации об устройстве: {e}", exc_info=True)
            return None
    
    def _xml_to_dict(self, element):
        """Вспомогательный метод для конвертации XML в словарь."""
        result = {}
        for child in element:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if len(child) == 0:
                result[tag] = child.text
            else:
                result[tag] = self._xml_to_dict(child)
        return result
    
    async def get_user_info_direct(self, employee_no: str) -> Optional[Dict[str, Any]]:
        """
        Получение детальной информации о пользователе с терминала.
        
        Endpoint: GET /ISAPI/AccessControl/UserInfo/Detail?format=json&employeeNo={employee_no}
        
        Args:
            employee_no: ID сотрудника
        
        Returns:
            Словарь с информацией о пользователе или None при ошибке
        """
        try:
            client = await self._get_client()
            
            response = await client.get(
                f"{self.base_url}/ISAPI/AccessControl/UserInfo/Detail?format=json&employeeNo={employee_no}",
                auth=self.auth,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.warning(f"[GET_USER_INFO] Не удалось получить информацию о пользователе {employee_no}: HTTP {response.status_code}")
                return None
            
            data = response.json()
            user_info = data.get("UserInfo", {})
            
            return user_info
                
        except Exception as e:
            logger.error(f"[GET_USER_INFO] Ошибка получения информации о пользователе {employee_no}: {e}", exc_info=True)
            return None
    
    async def get_user_full_info(self, employee_no: str) -> Dict[str, Any]:
        """
        Получение МАКСИМАЛЬНО полной информации о пользователе с терминала.
        Собирает данные из всех доступных источников.
        
        Args:
            employee_no: ID сотрудника
        
        Returns:
            Словарь со всей доступной информацией о пользователе
        """
        full_info = {
            "employee_no": employee_no,
            "sources": {},
            "raw_data": {}
        }
        
        try:
            client = await self._get_client()
            
            # 1. Основная информация о пользователе (UserInfo/Detail)
            user_detail = await self.get_user_info_direct(employee_no)
            if user_detail:
                full_info["sources"]["UserInfo/Detail"] = user_detail
                full_info["raw_data"]["user_detail"] = user_detail
            
            # 2. Информация из FDLib (библиотека лиц)
            try:
                # Пробуем получить информацию о лице из FDLib
                fdlib_search = {
                    "FaceDataRecordSearch": {
                        "searchID": str(uuid.uuid4()).replace('-', ''),
                        "searchResultPosition": 0,
                        "maxResults": 1,
                        "searchResultPosition": 0,
                        "FPID": employee_no
                    }
                }
                
                fdlib_url = f"{self.base_url}/ISAPI/Intelligent/FDLib/FaceDataRecord?format=json"
                fdlib_response = await client.post(
                    fdlib_url,
                    json=fdlib_search,
                    timeout=self.timeout
                )
                
                if fdlib_response.status_code == 200:
                    fdlib_data = fdlib_response.json()
                    full_info["sources"]["FDLib/FaceDataRecord"] = fdlib_data
                    full_info["raw_data"]["fdlib_search"] = fdlib_data
            except Exception as e:
                logger.warning(f"[GET_USER_FULL_INFO] Не удалось получить информацию из FDLib: {e}")
            
            # 3. Информация о картах доступа (если есть)
            try:
                card_url = f"{self.base_url}/ISAPI/AccessControl/CardInfo/Search?format=json"
                card_search = {
                    "CardInfoSearchCond": {
                        "searchID": str(uuid.uuid4()).replace('-', ''),
                        "searchResultPosition": 0,
                        "maxResults": 10,
                        "EmployeeNoList": [employee_no]
                    }
                }
                
                card_response = await client.post(
                    card_url,
                    json=card_search,
                    timeout=self.timeout
                )
                
                if card_response.status_code == 200:
                    card_data = card_response.json()
                    full_info["sources"]["CardInfo/Search"] = card_data
                    full_info["raw_data"]["card_info"] = card_data
            except Exception as e:
                logger.warning(f"[GET_USER_FULL_INFO] Не удалось получить информацию о картах: {e}")
            
            # 4. Информация о группах доступа (если есть groupId)
            if user_detail and user_detail.get("groupId"):
                try:
                    group_url = f"{self.base_url}/ISAPI/AccessControl/UserGroup/Detail?format=json&groupId={user_detail.get('groupId')}"
                    group_response = await client.get(group_url, timeout=self.timeout)
                    
                    if group_response.status_code == 200:
                        group_data = group_response.json()
                        full_info["sources"]["UserGroup/Detail"] = group_data
                        full_info["raw_data"]["group_info"] = group_data
                except Exception as e:
                    logger.warning(f"[GET_USER_FULL_INFO] Не удалось получить информацию о группе: {e}")
            
            # 5. Структурированная сводка всех полей
            full_info["structured"] = {
                "basic": {
                    "employeeNo": user_detail.get("employeeNo") if user_detail else None,
                    "name": user_detail.get("name") if user_detail else None,
                    "userType": user_detail.get("userType") if user_detail else None,
                    "gender": user_detail.get("gender") if user_detail else None,
                },
                "validity": user_detail.get("Valid", {}) if user_detail else {},
                "face": {
                    "faceURL": user_detail.get("faceURL") if user_detail else None,
                    "has_face": bool(user_detail.get("faceURL")) if user_detail else False,
                },
                "group": {
                    "groupId": user_detail.get("groupId") if user_detail else None,
                },
                "card": {
                    "has_card": False,
                    "card_count": 0,
                },
                "fdlib": {
                    "in_fdlib": False,
                    "fpid": None,
                    "fdid": None,
                }
            }
            
            # Заполняем информацию о картах
            if "card_info" in full_info["raw_data"]:
                card_list = full_info["raw_data"]["card_info"].get("CardInfoSearch", {}).get("CardInfo", [])
                if isinstance(card_list, list):
                    full_info["structured"]["card"]["has_card"] = len(card_list) > 0
                    full_info["structured"]["card"]["card_count"] = len(card_list)
                elif isinstance(card_list, dict):
                    full_info["structured"]["card"]["has_card"] = True
                    full_info["structured"]["card"]["card_count"] = 1
            
            # Заполняем информацию о FDLib
            if "fdlib_search" in full_info["raw_data"]:
                fdlib_result = full_info["raw_data"]["fdlib_search"].get("FaceDataRecordSearch", {})
                if fdlib_result:
                    full_info["structured"]["fdlib"]["in_fdlib"] = True
                    face_record = fdlib_result.get("FaceDataRecord", {})
                    if isinstance(face_record, list) and len(face_record) > 0:
                        face_record = face_record[0]
                    full_info["structured"]["fdlib"]["fpid"] = face_record.get("FPID")
                    full_info["structured"]["fdlib"]["fdid"] = face_record.get("FDID")
            
            return full_info
            
        except Exception as e:
            logger.error(f"[GET_USER_FULL_INFO] Ошибка получения полной информации о пользователе {employee_no}: {e}", exc_info=True)
            full_info["error"] = str(e)
            return full_info
    
    async def get_user_face_photo(self, employee_no: str) -> Optional[bytes]:
        """
        Получение фото лица пользователя с терминала.
        
        Endpoint: GET /ISAPI/AccessControl/UserInfo/Detail?format=json&employeeNo={employee_no}
        Затем скачивание фото по faceURL из ответа.
        
        Args:
            employee_no: ID сотрудника
        
        Returns:
            Байты изображения (JPEG) или None при ошибке
        """
        try:
            user_info = await self.get_user_info_direct(employee_no)
            if not user_info:
                return None
            
            face_url = user_info.get("faceURL")
            
            if not face_url:
                logger.warning(f"[GET_USER_FACE_PHOTO] У пользователя {employee_no} нет faceURL")
                return None
            
            # Нормализуем URL
            face_url = self._normalize_face_url(face_url)
            
            # Скачиваем фото
            client = await self._get_client()
            photo_response = await client.get(
                f"{self.base_url}{face_url}",
                auth=self.auth,
                timeout=self.timeout
            )
            
            if photo_response.status_code == 200:
                return photo_response.content
            else:
                logger.warning(f"[GET_USER_FACE_PHOTO] Не удалось скачать фото: HTTP {photo_response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"[GET_USER_FACE_PHOTO] Ошибка получения фото пользователя {employee_no}: {e}", exc_info=True)
            return None
    
    def _normalize_face_url(self, face_url: str) -> str:
        """
        Нормализация face URL для скачивания.
        
        Примеры входных данных:
        1. "/ISAPI/AccessControl/UserFace/faceData?..." -> "/ISAPI/..."
        2. "192.168.1.67/ISAPI/..." -> "/ISAPI/..."
        3. "http://192.168.1.67/ISAPI/...@..." -> "/ISAPI/..."
        """
        if not face_url:
            return ""
        
        # Убираем @ и все после него (некоторые терминалы добавляют метаданные)
        if "@" in face_url:
            face_url = face_url.split("@")[0]
        
        # Убираем протокол
        face_url = face_url.replace("https://", "").replace("http://", "")
        
        # Убираем IP адрес в начале (если есть)
        if "/" in face_url:
            # Ищем первый "/" и берем все после него
            parts = face_url.split("/", 1)
            if len(parts) == 2:
                face_url = "/" + parts[1]
        
        # Если URL уже начинается с "/" - оставляем как есть
        if not face_url.startswith("/"):
            face_url = "/" + face_url
        
        return face_url
    
    async def get_users(self, max_results: int = 1000) -> Optional[List[Dict[str, Any]]]:
        """
        Получение списка пользователей с терминала.
        
        Endpoint: POST /ISAPI/AccessControl/UserInfo/Search?format=json
        
        Args:
            max_results: Максимальное количество пользователей для получения (по умолчанию 1000)
        
        Returns:
            Список словарей с информацией о пользователях или None при ошибке
        
        Raises:
            PermissionError: Если получен HTTP 401/403 (недостаточно прав)
        """
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
                
                # Если пользователь один, API может вернуть объект вместо списка
                if not isinstance(users, list):
                    users = [users] if users else []
                
                return users
            elif response.status_code in [401, 403]:
                logger.error(f"[GET_USERS] Недостаточно прав для доступа к UserInfo/Search: HTTP {response.status_code}")
                logger.error(f"[GET_USERS] Пользователь '{self.username}' должен иметь права на просмотр пользователей")
                raise PermissionError(f"User '{self.username}' lacks permission to access UserInfo/Search (HTTP {response.status_code})")
            else:
                logger.warning(f"[GET_USERS] Не удалось получить пользователей: HTTP {response.status_code}")
                return None
        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"[GET_USERS] Ошибка получения пользователей: {e}", exc_info=True)
            return None

    async def create_user_basic(
        self,
        employee_no: str,
        name: str,
        group_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Создание пользователя через обычный AccessControl API (без фото).

        Returns:
            Dict с результатом операции
        """
        try:
            connected, error_msg = await self.check_connection()
            http_client = await self._get_client()

            # Используем текущую дату для beginTime (как у рабочего пользователя)
            from datetime import datetime, timedelta
            begin_time = datetime.now().strftime("%Y-%m-%dT00:00:00")
            end_time = (datetime.now() + timedelta(days=3650)).strftime("%Y-%m-%dT23:59:59")  # +10 лет

            # Создаем данные пользователя
            # ВАЖНО: Добавляем обязательные поля для аутентификации:
            # - doorRight: права доступа к дверям
            # - RightPlan: шаблон прав доступа с planTemplateNo
            # - groupId: группа доступа (по умолчанию 1, если не указан)
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
                    # КРИТИЧНО: Права доступа к дверям (без этого пользователь не может пройти аутентификацию)
                    "doorRight": "1",
                    # КРИТИЧНО: Шаблон прав доступа (без этого пользователь не может пройти аутентификацию)
                    "RightPlan": [
                        {
                            "doorNo": 1,
                            "planTemplateNo": "1"
                        }
                    ]
                }
            }

            # Устанавливаем groupId (по умолчанию 1, если не указан)
            if group_id is not None:
                user_data["UserInfo"]["groupId"] = group_id
            else:
                user_data["UserInfo"]["groupId"] = 1  # По умолчанию группа 1

            # Формируем URL с токеном если он есть
            url = f"{self.base_url}/ISAPI/AccessControl/UserInfo/Record?format=json"
            if self._token:
                url += f"&token={self._token}"

            # Пробуем запрос
            response = await http_client.post(url, json=user_data, timeout=self.timeout)

            # Если получаем 401, попробуем с шифрованием
            if response.status_code == 401:
                logger.info("Standard auth failed, trying encrypted request...")
                # Для шифрования нужен IV (initialization vector)
                # Пока оставим без шифрования, так как это требует дополнительной реализации
                pass

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
            logger.error(f"Error creating user {employee_no}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": f"Error creating user: {str(e)}"
            }

    async def setup_user_face_fdlib(
        self,
        employee_no: str,
        face_url: str
    ) -> Dict[str, Any]:
        """
        Привязка фото к пользователю через FDLib/FDSetUp.
        Используется после создания пользователя для привязки лица.

        Args:
            employee_no: ID сотрудника
            face_url: URL фото (может быть локальным или на терминале)

        Returns:
            Dict с результатом операции
        """
        try:
            # Проверяем соединение
            connected, error_msg = await self.check_connection()
            if not connected:
                return {
                    "success": False,
                    "error": f"Terminal is not accessible. {error_msg or 'Check network connection.'}"
                }

            http_client = await self._get_client()

            # Создаем multipart данные для FDSetUp
            boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
            face_data = {
                "faceLibType": "blackFD",
                "FDID": "1",
                "FPID": employee_no,
                "faceURL": face_url
            }

            # Формируем multipart body
            face_data_str = json.dumps(face_data, separators=(',', ':'))
            body_parts = [
                f'--{boundary}\r\nContent-Disposition: form-data; name="FaceDataRecord"\r\n\r\n{face_data_str}\r\n',
                f'--{boundary}--\r\n'
            ]
            body = ''.join(body_parts).encode('utf-8')

            # Создаем URL без токена (токен не обязателен для FDSetUp)
            url = f"{self.base_url}/ISAPI/Intelligent/FDLib/FDSetUp?format=json"

            # Отправляем запрос (используем auth из клиента, как в тестах)
            logger.info(f"FDSetUp request: URL={url}, faceURL={face_url}, employee_no={employee_no}")
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
            logger.error(f"Error setting up face data for user {employee_no}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": f"Error setting up face data: {str(e)}"
            }

    async def _get_security_token(self) -> Dict[str, Any]:
        """
        Получение токена безопасности для операций FDLib.
        Использует Digest аутентификацию для получения токена.
        """
        try:
            # Создаем отдельный клиент с Basic auth для получения токена
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
                        self._token = token  # Кэшируем токен
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
            logger.error(f"Error getting security token: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def _encrypt_data(self, data: str) -> tuple[str, str]:
        """
        Шифрование данных по протоколу Hikvision.
        Возвращает (encrypted_data, iv_hex)
        """
        try:
            # Генерируем случайный IV (16 байт для AES)
            iv = secrets.token_bytes(16)
            iv_hex = iv.hex()

            # Используем пароль как ключ (нужно хэшировать до 32 байт для AES-256)
            password = self.password.encode('utf-8')
            key = hashlib.sha256(password).digest()

            # Создаем шифратор AES-CBC
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            encryptor = cipher.encryptor()

            # Подготавливаем данные (дополняем до размера блока)
            data_bytes = data.encode('utf-8')
            # PKCS7 padding
            block_size = 16
            padding_length = block_size - (len(data_bytes) % block_size)
            padded_data = data_bytes + bytes([padding_length] * padding_length)

            # Шифруем
            encrypted = encryptor.update(padded_data) + encryptor.finalize()

            # Кодируем в base64
            encrypted_b64 = base64.b64encode(encrypted).decode('utf-8')

            return encrypted_b64, iv_hex

        except Exception as e:
            logger.error(f"Error encrypting data: {e}")
            raise

    def _decrypt_data(self, encrypted_data: str, iv_hex: str) -> str:
        """
        Расшифровка данных по протоколу Hikvision.
        """
        try:
            # Декодируем IV
            iv = bytes.fromhex(iv_hex)

            # Используем пароль как ключ
            password = self.password.encode('utf-8')
            key = hashlib.sha256(password).digest()

            # Создаем дешифратор
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()

            # Декодируем зашифрованные данные
            encrypted_bytes = base64.b64decode(encrypted_data)

            # Расшифровываем
            decrypted_padded = decryptor.update(encrypted_bytes) + decryptor.finalize()

            # Убираем padding (PKCS7)
            padding_length = decrypted_padded[-1]
            decrypted = decrypted_padded[:-padding_length]

            return decrypted.decode('utf-8')

        except Exception as e:
            logger.error(f"Error decrypting data: {e}")
            raise

    async def create_user_with_encryption(
        self,
        employee_no: str,
        name: str,
        group_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Создание пользователя с шифрованием данных (как в Hikvision веб-интерфейсе).
        """
        try:
            # Проверяем соединение (но не блокируем выполнение при ошибке аутентификации)
            connected, error_msg = await self.check_connection()
            logger.info(f"create_user_with_encryption: connection check result: connected={connected}, error='{error_msg}'")

            # Продолжаем даже если check_connection вернул False
            # Это может быть из-за проблем с аутентификацией, которые мы попробуем обойти

            # Создаем данные пользователя
            user_data = {
                "UserInfo": {
                    "employeeNo": employee_no,
                    "name": name,
                    "userType": "normal",
                    "Valid": {
                        "enable": True,
                        "beginTime": "2025-01-01T00:00:00",
                        "endTime": "2035-01-01T00:00:00",
                        "timeType": "local"
                    },
                    "gender": "unknown"
                }
            }

            if group_id is not None:
                user_data["UserInfo"]["groupId"] = group_id

            # Преобразуем в JSON
            json_data = json.dumps(user_data, separators=(',', ':'))

            # Шифруем данные
            encrypted_data, iv_hex = self._encrypt_data(json_data)

            # Создаем form data
            form_data = encrypted_data

            http_client = await self._get_client()

            # Формируем URL с токеном если он есть
            url = f"{self.base_url}/ISAPI/AccessControl/UserInfo/Record?format=json&security=1&iv={iv_hex}"
            if self._token:
                url += f"&token={self._token}"

            # Отправляем запрос с шифрованием
            response = await http_client.post(
                url,
                content=form_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                timeout=self.timeout
            )

            if response.status_code == 200:
                return {
                    "success": True,
                    "message": f"User {employee_no} created successfully with encryption"
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "message": f"Failed to create user with encryption: HTTP {response.status_code}"
                }

        except Exception as e:
            logger.error(f"Error creating user with encryption {employee_no}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": f"Error creating user with encryption: {str(e)}"
            }

    async def add_face_data_record(
        self,
        employee_no: str,
        face_url: str
    ) -> Dict[str, Any]:
        """
        Добавление записи лица через FDLib FaceDataRecord.
        Привязывает существующее фото (по URL) к пользователю.
        """
        try:
            # Проверяем соединение
            connected, error_msg = await self.check_connection()
            if not connected:
                return {
                    "success": False,
                    "error": f"Terminal is not accessible. {error_msg or 'Check network connection.'}"
                }

            http_client = await self._get_client()

            # Создаем multipart/form-data запрос как в HAR файле
            face_data_json = {
                "faceLibType": "blackFD",
                "FDID": "1",
                "FPID": employee_no,
                "faceURL": face_url
            }

            # Используем multipart/form-data с полем FaceDataRecord
            import secrets
            boundary = f"----WebKitFormBoundary{secrets.token_hex(12)}"

            face_data_str = json.dumps(face_data_json, separators=(',', ':'))
            body_parts = [
                f'--{boundary}\r\nContent-Disposition: form-data; name="FaceDataRecord"\r\n\r\n{face_data_str}\r\n',
                f'--{boundary}--\r\n'
            ]
            body = ''.join(body_parts).encode('utf-8')

            headers = {
                'Content-Type': f'multipart/form-data; boundary={boundary}',
                'Content-Length': str(len(body))
            }

            # Формируем URL с токеном если он есть
            url = f"{self.base_url}/ISAPI/Intelligent/FDLib/FaceDataRecord?format=json"
            if self._token:
                url += f"&token={self._token}"

            logger.info(f"FaceDataRecord URL: {url}")
            logger.info(f"FaceDataRecord data: {face_data_str}")

            # Отправляем multipart запрос
            response = await http_client.post(url, content=body, headers=headers, timeout=self.timeout)

            if response.status_code == 200:
                try:
                    result = response.json()
                    if result.get("statusCode") == 1:
                        return {
                            "success": True,
                            "message": f"Face data record added for user {employee_no}"
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"FaceDataRecord failed: {result}",
                            "message": f"Face data record failed for user {employee_no}"
                        }
                except:
                    return {
                        "success": True,
                        "message": f"Face data record added for user {employee_no}"
                    }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "message": f"FaceDataRecord request failed: HTTP {response.status_code}"
                }

        except Exception as e:
            logger.error(f"Error adding face data record for user {employee_no}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": f"Error adding face data record: {str(e)}"
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
            # Проверяем соединение
            connected, error_msg = await self.check_connection()
            if not connected:
                return {
                    "success": False,
                    "error": f"Terminal is not accessible. {error_msg or 'Check network connection.'}"
                }

            http_client = await self._get_client()

            # XML тело для запуска захвата фото согласно документации
            capture_xml = """<CaptureFaceDataCond version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
    <captureInfrared>false</captureInfrared>
    <dataType>url</dataType>
</CaptureFaceDataCond>"""

            # Отправляем команду на запуск захвата фото
            # POST запрос к /ISAPI/AccessControl/CaptureFaceData с XML телом
            response = await http_client.post(
                f"{self.base_url}/ISAPI/AccessControl/CaptureFaceData",
                content=capture_xml,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                auth=self.auth,
                timeout=self.timeout
            )

            if response.status_code == 200:
                # Retry логика для ожидания захвата лица
                for attempt in range(max_retries + 1):
                    try:
                        root = ET.fromstring(response.text)
                        face_data_url = None
                        capture_progress = 0

                        # Парсим ответ согласно HAR файлу
                        for elem in root.iter():
                            if elem.tag.endswith('faceDataUrl') or elem.tag.endswith('faceURL'):
                                face_data_url = elem.text
                            elif elem.tag.endswith('captureProgress'):
                                try:
                                    capture_progress = int(elem.text)
                                except (ValueError, TypeError):
                                    capture_progress = 0

                        logger.info(f"CaptureFaceData attempt {attempt + 1}: progress={capture_progress}, url={face_data_url}")

                        # Логика обработки согласно HAR файлу
                        if capture_progress == 100 and face_data_url:
                            # Захват завершен успешно
                            return {
                                "success": True,
                                "message": "Face capture completed successfully",
                                "face_data_url": face_data_url,
                                "capture_progress": capture_progress
                            }
                        elif capture_progress < 100 and attempt < max_retries:
                            # Терминал еще ждет предъявления лица, ждем и повторяем
                            logger.info(f"Waiting {retry_delay}s before retry {attempt + 2}/{max_retries + 1}")
                            await asyncio.sleep(retry_delay)

                            # Повторный запрос для проверки статуса
                            response = await http_client.post(
                                f"{self.base_url}/ISAPI/AccessControl/CaptureFaceData",
                                content=capture_xml,
                                headers={"Content-Type": "application/x-www-form-urlencoded"},
                                auth=self.auth,
                                timeout=self.timeout
                            )

                            if response.status_code != 200:
                                break  # Выходим из цикла если ошибка

                            continue  # Продолжаем цикл для повторного парсинга

                        elif capture_progress < 100:
                            # Все попытки исчерпаны, терминал все еще ждет
                            return {
                                "success": True,
                                "message": f"Face capture in progress ({capture_progress}%). Please present your face to the terminal.",
                                "face_data_url": None,
                                "capture_progress": capture_progress,
                                "status": "waiting",
                                "note": "Terminal is now waiting for face detection. Call this endpoint again after presenting face."
                            }
                        else:
                            # Захват завершен, но URL не получен
                            return {
                                "success": True,
                                "message": "Face capture completed, but photo URL not available",
                                "face_data_url": None,
                                "capture_progress": capture_progress
                            }

                    except ET.ParseError:
                        # Если не XML, возвращаем просто успех
                        return {
                            "success": True,
                            "message": "Face capture started successfully"
                        }

                # Если дошли сюда, значит все попытки исчерпаны
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
            logger.error(f"Error starting face capture: {e}", exc_info=True)
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
            # Проверяем соединение
            connected, error_msg = await self.check_connection()
            if not connected:
                return []

            http_client = await self._get_client()

            # По умолчанию получаем события за последние 24 часа
            if not start_time:
                start_time = datetime.now() - timedelta(days=1)
            if not end_time:
                end_time = datetime.now()

            # Формируем запрос для поиска событий
            # Используем Event/notification для получения исторических событий
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

            logger.info(f"Searching attendance records from {start_time} to {end_time}")

            # Сначала пробуем стандартный endpoint для поиска событий
            url = f"{self.base_url}/ISAPI/Event/notification/eventSearch?format=json"
            if self._token:
                url += f"&token={self._token}"

            response = await http_client.post(url, json=search_data, timeout=self.timeout)

            if response.status_code == 200:
                try:
                    result = response.json()
                    events = result.get("EventNotificationList", {}).get("EventNotification", [])

                    # Парсим события и конвертируем в стандартный формат
                    attendance_records = []
                    for event in events:
                        if isinstance(event, dict) and event.get("eventType") == "accessControllerEvent":
                            record = self._parse_access_event(event)
                            if record:
                                attendance_records.append(record)

                    logger.info(f"Found {len(attendance_records)} attendance records")
                    return attendance_records

                except Exception as e:
                    logger.warning(f"Failed to parse event search response: {e}")

            # Если eventSearch не работает, пробуем alertStream для получения текущих событий
            logger.info("Trying alertStream for current events...")
            alert_url = f"{self.base_url}/ISAPI/Event/notification/alertStream"
            if self._token:
                alert_url += f"?token={self._token}"

            # Для alertStream делаем короткий запрос с таймаутом
            try:
                alert_response = await http_client.get(alert_url, timeout=5)
                if alert_response.status_code == 200:
                    # Парсим поток событий (обычно XML)
                    content = alert_response.text
                    if content.strip():
                        logger.info("Received alert stream data")
                        # Здесь можно добавить парсинг XML событий
                        # Пока возвращаем пустой список
                        return []
            except Exception as e:
                logger.warning(f"Failed to get alert stream: {e}")

            logger.warning("No attendance records found or unsupported by device")
            return []

        except Exception as e:
            logger.error(f"Error getting attendance records: {e}", exc_info=True)
            return []

    def _parse_access_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Парсит событие доступа и конвертирует в стандартный формат.

        Args:
            event: Событие от Hikvision

        Returns:
            Словарь с полями: employee_no, timestamp, event_type, terminal_ip
        """
        try:
            # Извлекаем информацию о событии
            event_info = event.get("AccessControllerEvent", {})

            # Получаем ID сотрудника
            employee_no = event_info.get("employeeNoString") or event_info.get("employeeNo")
            if not employee_no:
                return None

            # Получаем время события
            timestamp_str = event_info.get("time")
            if not timestamp_str:
                return None

            # Парсим время (может быть в разных форматах)
            try:
                # Пробуем разные форматы времени
                for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        timestamp = datetime.strptime(timestamp_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    logger.warning(f"Could not parse timestamp: {timestamp_str}")
                    return None
            except Exception as e:
                logger.warning(f"Error parsing timestamp {timestamp_str}: {e}")
                return None

            # Определяем тип события (вход/выход)
            # В Hikvision событиях обычно есть cardType, cardReaderNo и т.д.
            card_reader = event_info.get("cardReaderNo", 0)

            # Предполагаем: четные номера - вход, нечетные - выход
            # Это может зависеть от конфигурации терминала
            if card_reader % 2 == 0:
                event_type = "entry"
            else:
                event_type = "exit"

            return {
                "employee_no": str(employee_no),
                "timestamp": timestamp,
                "event_type": event_type,
                "terminal_ip": self.base_url.replace("https://", "").replace("http://", "").split(":")[0]
            }

        except Exception as e:
            logger.warning(f"Error parsing access event: {e}")
            return None

