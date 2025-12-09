"""
Hikvision Client - Клиент для работы с терминалами Hikvision через ISAPI
"""

import asyncio
import base64
import hashlib
from typing import Dict, Any, Optional, List
import httpx
from urllib.parse import urljoin
import logging

logger = logging.getLogger(__name__)

class HikvisionClient:
    def __init__(self, ip: str, username: str, password: str):
        self.base_url = f"http://{ip}"
        self.auth = httpx.DigestAuth(username, password)
        self.timeout = 30
        self._client = None

    async def _get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
        
    async def check_connection(self) -> bool:
        """
        Проверка доступности устройства через ISAPI.
        Возвращает True если устройство доступно и отвечает на запросы.
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/ISAPI/System/deviceInfo",
                auth=self.auth,
                timeout=5  # Короткий таймаут для быстрой проверки
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"[CHECK_CONNECTION] Устройство недоступно: {e}")
            return False
    
    async def get_device_info(self) -> Optional[Dict[str, Any]]:
        """
        Получение информации об устройстве.
        Возвращает словарь с информацией о модели, серийном номере, версии прошивки и т.д.
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
                
                logger.info(f"[GET_DEVICE_INFO] Информация об устройстве: {result}")
                return result
            else:
                logger.warning(f"[GET_DEVICE_INFO] Не удалось получить информацию: HTTP {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"[GET_DEVICE_INFO] Ошибка получения информации об устройстве: {e}", exc_info=True)
            return None
    
    async def get_fdlib_capabilities(self) -> Optional[Dict[str, Any]]:
        """Получение возможностей FDLib"""
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/ISAPI/Intelligent/FDLib/capabilities?format=json",
                auth=self.auth,
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                logger.info(f"[FD_LIB_CAPS] FDLib capabilities: {data}")
                return data
            else:
                logger.warning(f"[FD_LIB_CAPS] Failed to get FDLib capabilities: HTTP {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"[FD_LIB_CAPS] Exception getting FDLib capabilities: {e}", exc_info=True)
            return None
    
    async def get_fdlib_list(self) -> Optional[Dict[str, Any]]:
        """
        Получение списка лиц из FDLib.
        GET /ISAPI/Intelligent/FDLib?format=json
        
        Возвращает структуру:
        {
            "statusCode": 1,
            "statusString": "OK",
            "FDLib": [
                {
                    "FDID": "1",
                    "faceLibType": "blackFD",
                    "name": "test_face_001_face"
                }
            ]
        }
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/ISAPI/Intelligent/FDLib?format=json",
                auth=self.auth,
                timeout=self.timeout
            )

            logger.info(f"[GET_FDLIB_LIST] Status: {response.status_code}")

            if response.status_code == 200:
                try:
                    data = response.json()

                    # Обрабатываем структуру ответа
                    fdlib_list = data.get("FDLib", [])
                    if not isinstance(fdlib_list, list):
                        fdlib_list = [fdlib_list] if fdlib_list else []

                    logger.info(f"[GET_FDLIB_LIST] Найдено лиц в FDLib: {len(fdlib_list)}")
                    for face in fdlib_list:
                        logger.info(f"[GET_FDLIB_LIST] - FDID: {face.get('FDID')}, name: {face.get('name')}, type: {face.get('faceLibType')}")

                    return {
                        "statusCode": data.get("statusCode"),
                        "statusString": data.get("statusString"),
                        "subStatusCode": data.get("subStatusCode"),
                        "FDLib": fdlib_list,
                        "total_faces": len(fdlib_list)
                    }
                except Exception as e:
                    logger.warning(f"[GET_FDLIB_LIST] Failed to parse JSON: {e}")
                    logger.info(f"[GET_FDLIB_LIST] Raw response: {response.text}")
                    return {
                        "error": f"Failed to parse JSON: {e}",
                        "raw_response": response.text[:1000],
                        "content_type": response.headers.get("content-type")
                    }

            logger.warning(f"[GET_FDLIB_LIST] HTTP {response.status_code}: {response.text[:500]}")
            return {
                "error": f"HTTP {response.status_code}",
                "status_code": response.status_code,
                "response": response.text[:500]
            }
        except Exception as e:
            logger.error(f"[GET_FDLIB_LIST] Exception: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def create_fdlib(self, fdid: str = "1", name: str = "mainlib", face_lib_type: str = "normalFD") -> Dict[str, Any]:
        """
        Создание FDLib на устройстве DS-K1T343EFWX.
        POST /ISAPI/Intelligent/FDLib/FDID?format=json
        
        Args:
            fdid: ID библиотеки (для DS-K1T343EFWX всегда "1")
            name: Имя библиотеки (латиница, без пробелов, ≤16 символов)
            face_lib_type: Тип библиотеки ("normalFD" или "blackFD")
        """
        result = {
            "success": False,
            "error": None
        }

        logger.info(f"[CREATE_FDLIB] ===== СОЗДАНИЕ FDLIB FDID={fdid}, name={name}, type={face_lib_type} =====")

        try:
            payload = {
                "FDID": fdid,
                "faceLibType": face_lib_type,
                "name": name
            }

            client = await self._get_client()
            url = f"{self.base_url}/ISAPI/Intelligent/FDLib/FDID?format=json"

            logger.info(f"[CREATE_FDLIB] Отправка запроса: POST {url}")
            logger.info(f"[CREATE_FDLIB] Payload: {payload}")

            response = await client.post(
                url,
                auth=self.auth,
                json=payload,
                timeout=self.timeout
            )

            logger.info(f"[CREATE_FDLIB] Ответ: Status={response.status_code}")
            logger.info(f"[CREATE_FDLIB] Тело ответа: {response.text[:500]}")

            if response.status_code in [200, 201]:
                try:
                    resp_data = response.json()
                    if resp_data.get("statusCode") == 1 or resp_data.get("statusString") == "OK":
                        logger.info(f"[CREATE_FDLIB] ✅ FDLib успешно создана")
                        result["success"] = True
                    else:
                        error_msg = resp_data.get("errorMsg", resp_data.get("statusString", "Unknown error"))
                        logger.error(f"[CREATE_FDLIB] ❌ Ошибка создания FDLib: {error_msg}")
                        result["error"] = f"Failed to create FDLib: {error_msg}"
                except Exception as e:
                    logger.error(f"[CREATE_FDLIB] Ошибка парсинга ответа: {e}")
                    result["error"] = f"Failed to parse response: {e}"
            else:
                logger.error(f"[CREATE_FDLIB] ❌ HTTP ошибка: {response.status_code} - {response.text}")
                result["error"] = f"HTTP {response.status_code}: {response.text}"

        except Exception as e:
            logger.error(f"[CREATE_FDLIB] Критическая ошибка: {e}", exc_info=True)
            result["error"] = str(e)

        logger.info(f"[CREATE_FDLIB] ===== ЗАВЕРШЕНИЕ (success={result['success']}) =====")
        return result

    async def delete_fdlib(self, fdid: str = "1") -> Dict[str, Any]:
        """
        Удаление FDLib с устройства DS-K1T343EFWX.
        DELETE /ISAPI/Intelligent/FDLib/{fdid}

        Args:
            fdid: ID библиотеки для удаления
        """
        result = {
            "success": False,
            "error": None
        }

        logger.info(f"[DELETE_FDLIB] ===== УДАЛЕНИЕ FDLIB FDID={fdid} =====")

        try:
            client = await self._get_client()
            url = f"{self.base_url}/ISAPI/Intelligent/FDLib/{fdid}"

            logger.info(f"[DELETE_FDLIB] Отправка запроса: DELETE {url}")

            response = await client.delete(
                url,
                auth=self.auth,
                timeout=self.timeout
            )

            logger.info(f"[DELETE_FDLIB] Ответ: Status={response.status_code}")
            logger.info(f"[DELETE_FDLIB] Тело ответа: {response.text[:500]}")

            if response.status_code == 200:
                try:
                    resp_data = response.json()
                    if resp_data.get("statusCode") == 1 or resp_data.get("statusString") == "OK":
                        logger.info(f"[DELETE_FDLIB] ✅ FDLib успешно удалена")
                        result["success"] = True
                    else:
                        error_msg = resp_data.get("errorMsg", resp_data.get("statusString", "Unknown error"))
                        logger.error(f"[DELETE_FDLIB] ❌ Ошибка удаления FDLib: {error_msg}")
                        result["error"] = f"Failed to delete FDLib: {error_msg}"
                except Exception as e:
                    logger.error(f"[DELETE_FDLIB] Ошибка парсинга ответа: {e}")
                    result["error"] = f"Failed to parse response: {e}"
            else:
                logger.error(f"[DELETE_FDLIB] ❌ HTTP ошибка: {response.status_code} - {response.text}")
                result["error"] = f"HTTP {response.status_code}: {response.text}"

        except Exception as e:
            logger.error(f"[DELETE_FDLIB] Критическая ошибка: {e}", exc_info=True)
            result["error"] = str(e)

        logger.info(f"[DELETE_FDLIB] ===== ЗАВЕРШЕНИЕ (success={result['success']}) =====")
        return result

    async def ensure_fdlib_exists(self) -> Dict[str, Any]:
        """
        Гарантирует существование корректной FDLib для DS-K1T343EFWX.
        На устройстве может быть только один FDLib с FDID=1 типа normalFD.

        Логика:
        1. Получить список FDLib
        2. Если FDLib отсутствует → создать normalFD
        3. Если есть но тип blackFD → удалить и создать normalFD
        4. Если есть и тип normalFD → ничего не делать
            
        Returns:
            {"success": bool, "action_taken": str, "error": str}
        """
        result = {
            "success": False,
            "action_taken": "none",
            "error": None
        }

        logger.info("[ENSURE_FDLIB] ===== ПРОВЕРКА И ОБЕСПЕЧЕНИЕ FDLIB =====")

        try:
            # Шаг 1: Получить текущий список FDLib
            logger.info("[ENSURE_FDLIB] Получение списка FDLib...")
            fdlib_data = await self.get_fdlib_list()

            if "error" in fdlib_data:
                logger.error(f"[ENSURE_FDLIB] Ошибка получения списка FDLib: {fdlib_data['error']}")
                result["error"] = f"Failed to get FDLib list: {fdlib_data['error']}"
                return result

            fdlib_list = fdlib_data.get("FDLib", [])
            logger.info(f"[ENSURE_FDLIB] Найдено FDLib: {len(fdlib_list)}")

            # Ищем FDLib с FDID=1
            fdlib_1 = None
            for fdlib in fdlib_list:
                if str(fdlib.get("FDID")) == "1":
                    fdlib_1 = fdlib
                    break

            if not fdlib_1:
                # FDLib не существует, создаем новую
                logger.info("[ENSURE_FDLIB] FDLib с FDID=1 не найдена, создаем новую...")
                create_result = await self.create_fdlib("1", "mainlib", "normalFD")
                if create_result["success"]:
                    result["success"] = True
                    result["action_taken"] = "created"
                    logger.info("[ENSURE_FDLIB] ✅ FDLib успешно создана")
                else:
                    result["error"] = f"Failed to create FDLib: {create_result['error']}"
                    logger.error(f"[ENSURE_FDLIB] ❌ Ошибка создания FDLib: {result['error']}")
                return result

            # FDLib существует, проверяем тип
            current_type = fdlib_1.get("faceLibType")
            logger.info(f"[ENSURE_FDLIB] FDLib найдена: FDID={fdlib_1.get('FDID')}, type={current_type}, name={fdlib_1.get('name')}")

            if current_type == "blackFD":
                # Нужно удалить blackFD и создать normalFD
                logger.info("[ENSURE_FDLIB] FDLib имеет тип blackFD, заменяем на normalFD...")

                # Шаг 1: Удалить существующую
                delete_result = await self.delete_fdlib("1")
                if not delete_result["success"]:
                    # Устройство может не поддерживать удаление (statusString=Invalid Operation/notSupport)
                    # В этом случае пробуем сразу создать normalFD поверх существующей
                    error_text = str(delete_result["error"])
                    if "notSupport" in error_text or "Invalid Operation" in error_text:
                        logger.warning("[ENSURE_FDLIB] Удаление не поддерживается (notSupport). Пробуем создать normalFD без удаления.")
                        create_result = await self.create_fdlib("1", "mainlib", "normalFD")
                        if create_result["success"]:
                            result["success"] = True
                            result["action_taken"] = "replaced_without_delete"
                            logger.info("[ENSURE_FDLIB] ✅ Создали normalFD без удаления blackFD (notSupport на DELETE)")
                            return result

                        # Если и создание вернуло notSupport/Invalid Operation — вероятно, FDLib уже существует и не перезаписывается.
                        create_error = str(create_result.get("error", ""))
                        if "notSupport" in create_error or "Invalid Operation" in create_error:
                            logger.warning("[ENSURE_FDLIB] CREATE тоже notSupport. Проверяем текущее состояние FDLib...")
                            recheck = await self.get_fdlib_list()
                            fdlibs = recheck.get("FDLib", []) if isinstance(recheck, dict) else []
                            if not isinstance(fdlibs, list):
                                fdlibs = [fdlibs] if fdlibs else []
                            fdlib_1_re = None
                            for fdlib in fdlibs:
                                if str(fdlib.get("FDID")) == "1":
                                    fdlib_1_re = fdlib
                                    break
                            if fdlib_1_re:
                                current_type_re = fdlib_1_re.get("faceLibType")
                                if current_type_re == "normalFD":
                                    result["success"] = True
                                    result["action_taken"] = "use_existing_normal"
                                    logger.info("[ENSURE_FDLIB] ✅ Используем существующий normalFD (create/notSupport).")
                                    return result
                                else:
                                    logger.warning("[ENSURE_FDLIB] FDID=1 существует, но тип!=normalFD; устройство не дает заменить (notSupport). Продолжаем с имеющимся.")
                                    result["success"] = True
                                    result["action_taken"] = "use_existing_blackfd_not_support"
                                    result["warning"] = "FDLib remains blackFD; device returned notSupport on replace"
                                    return result

                        result["error"] = f"Failed to create normalFD FDLib after notSupport delete: {create_result.get('error')}"
                        logger.error(f"[ENSURE_FDLIB] ❌ Ошибка создания normalFD после notSupport: {result['error']}")
                        return result

                    result["error"] = f"Failed to delete blackFD FDLib: {delete_result['error']}"
                    logger.error(f"[ENSURE_FDLIB] ❌ Ошибка удаления blackFD FDLib: {result['error']}")
                    return result

                # Шаг 2: Создать новую normalFD
                create_result = await self.create_fdlib("1", "mainlib", "normalFD")
                if create_result["success"]:
                    result["success"] = True
                    result["action_taken"] = "replaced"
                    logger.info("[ENSURE_FDLIB] ✅ FDLib успешно заменена с blackFD на normalFD")
                else:
                    result["error"] = f"Failed to create normalFD FDLib: {create_result['error']}"
                    logger.error(f"[ENSURE_FDLIB] ❌ Ошибка создания normalFD FDLib: {result['error']}")
                return result

            elif current_type == "normalFD":
                # Уже правильный тип, ничего не делаем
                logger.info("[ENSURE_FDLIB] FDLib уже имеет правильный тип normalFD")
                result["success"] = True
                result["action_taken"] = "none"
                return result

            else:
                # Неизвестный тип
                logger.warning(f"[ENSURE_FDLIB] FDLib имеет неизвестный тип: {current_type}")
                result["error"] = f"Unknown FDLib type: {current_type}"
                return result
                
        except Exception as e:
            logger.error(f"[ENSURE_FDLIB] Критическая ошибка: {e}", exc_info=True)
            result["error"] = str(e)

        logger.info(f"[ENSURE_FDLIB] ===== ЗАВЕРШЕНИЕ (success={result['success']}, action={result['action_taken']}) =====")
        return result

    async def add_face_to_user_json(self, employee_no: str, photo_bytes: bytes, user_name: str = None) -> Dict[str, Any]:
        """
        Добавление фото лица через FDLib FaceDataRecord API для DS-K1T343EFWX.
        POST /ISAPI/Intelligent/FDLib/FaceDataRecord?format=json

        Особенности DS-K1T343EFWX:
        - Использует только FDID=1
        - Перед загрузкой лица FDLib должна существовать и быть типа normalFD
        """
        result = {
            "success": False,
            "face_uploaded": False,
            "fdlib_ensured": False,
            "error": None
        }

        logger.info(f"[ADD_FACE_JSON] ===== НАЧАЛО ДОБАВЛЕНИЯ ЛИЦА ДЛЯ {employee_no} (DS-K1T343EFWX) =====")

        try:
            # Шаг 1: Гарантируем существование правильной FDLib
            logger.info(f"[ADD_FACE_JSON] Шаг 1: Проверка FDLib...")
            ensure_result = await self.ensure_fdlib_exists()

            if not ensure_result["success"]:
                logger.error(f"[ADD_FACE_JSON] ❌ Не удалось обеспечить FDLib: {ensure_result['error']}")
                result["error"] = f"Failed to ensure FDLib: {ensure_result['error']}"
                return result

            result["fdlib_ensured"] = True
            logger.info(f"[ADD_FACE_JSON] ✅ FDLib готова (action: {ensure_result['action_taken']})")

            # Шаг 2: Конвертируем фото в base64 с префиксом
            import base64
            face_data_base64 = base64.b64encode(photo_bytes).decode('utf-8')
            face_data_with_prefix = f"data:image/jpeg;base64,{face_data_base64}"

            logger.info(f"[ADD_FACE_JSON] Шаг 2: Фото конвертировано в base64 (размер: {len(face_data_base64)} символов)")

            # Шаг 3: Формируем payload для FaceDataRecord
            # Для DS-K1T343EFWX используем только FDID=1
            payload = {
                "FaceDataRecord": {
                    "FDID": "1",
                    "faceURL": face_data_with_prefix
                }
            }

            logger.info(f"[ADD_FACE_JSON] Шаг 3: Payload подготовлен для FaceDataRecord")
            logger.info(f"[ADD_FACE_JSON] FDID: 1, faceURL length: {len(face_data_with_prefix)}")

            # Шаг 4: Отправляем запрос на добавление лица
            client = await self._get_client()
            url = f"{self.base_url}/ISAPI/Intelligent/FDLib/FaceDataRecord?format=json"

            logger.info(f"[ADD_FACE_JSON] Шаг 4: Отправка POST {url}")
            logger.info(f"[ADD_FACE_JSON] Payload structure: {list(payload.keys())}")

            response = await client.post(
                url,
                auth=self.auth,
                json=payload,
                timeout=self.timeout
            )

            logger.info(f"[ADD_FACE_JSON] Ответ: Status={response.status_code}")
            logger.info(f"[ADD_FACE_JSON] Тело ответа (первые 500 символов): {response.text[:500]}")

            # Шаг 5: Обрабатываем ответ
            if response.status_code in [200, 201]:
                try:
                    resp_data = response.json()
                    logger.info(f"[ADD_FACE_JSON] JSON ответ: {resp_data}")

                    status_code = resp_data.get("statusCode")
                    status_string = resp_data.get("statusString", "").lower()

                    if status_code == 1 or status_string == "ok":
                        logger.info(f"[ADD_FACE_JSON] ✅ Лицо успешно добавлено для {employee_no}")
                        result["success"] = True
                        result["face_uploaded"] = True
                    else:
                        error_msg = resp_data.get("errorMsg", resp_data.get("statusString", "Unknown error"))
                        logger.error(f"[ADD_FACE_JSON] ❌ Ошибка добавления лица: {error_msg}")

                        # Специальная обработка для faceLibraryNumError
                        if "facelibrarynumerror" in error_msg.lower():
                            logger.warning("[ADD_FACE_JSON] Обнаружена ошибка faceLibraryNumError - возможно проблема с FDLib")
                            result["error"] = f"Face library error: {error_msg}. Try recreating FDLib."
                        else:
                            result["error"] = f"Failed to add face: {error_msg}"

                except Exception as e:
                    logger.error(f"[ADD_FACE_JSON] Ошибка парсинга JSON ответа: {e}")
                    result["error"] = f"Failed to parse response: {e}"
            else:
                error_msg = response.text[:500]
                logger.error(f"[ADD_FACE_JSON] ❌ HTTP ошибка: {response.status_code} - {error_msg}")

                # Проверяем на специфические ошибки DS-K1T343EFWX
                if "faceLibraryNumError" in error_msg:
                    result["error"] = "Face library number error - check FDLib configuration"
                else:
                    result["error"] = f"HTTP {response.status_code}: {error_msg}"

        except Exception as e:
            logger.error(f"[ADD_FACE_JSON] Критическая ошибка: {e}", exc_info=True)
            result["error"] = str(e)

        logger.info(f"[ADD_FACE_JSON] ===== ЗАВЕРШЕНИЕ (success={result['success']}, fdlib_ensured={result['fdlib_ensured']}) =====")
        return result

    async def add_user_with_face(self, employee_no: str, name: str, photo_bytes: bytes, department: Optional[str] = None) -> Dict[str, Any]:
        """
        Создание пользователя с лицом через трехэтапный процесс для DS-K1T343EFWX:
        1. Гарантировать существование корректной FDLib (normalFD)
        2. Создать пользователя через UserInfo/Record
        3. Добавить лицо через FaceDataRecord
        """
        result = {
            "success": False,
            "fdlib_ensured": False,
            "user_created": False,
            "face_uploaded": False,
            "error": None
        }

        logger.info(f"[ADD_USER_WITH_FACE] ===== НАЧАЛО СОЗДАНИЯ ПОЛЬЗОВАТЕЛЯ С ЛИЦОМ: {employee_no} (DS-K1T343EFWX) =====")

        try:
            # Шаг 1: Гарантируем существование правильной FDLib
            logger.info(f"[ADD_USER_WITH_FACE] Шаг 1: Проверка FDLib...")
            ensure_result = await self.ensure_fdlib_exists()

            if not ensure_result["success"]:
                logger.error(f"[ADD_USER_WITH_FACE] ❌ Не удалось обеспечить FDLib: {ensure_result['error']}")
                result["error"] = f"Failed to ensure FDLib: {ensure_result['error']}"
                return result

            result["fdlib_ensured"] = True
            logger.info(f"[ADD_USER_WITH_FACE] ✅ FDLib готова (action: {ensure_result['action_taken']})")

            # Шаг 2: Создаем пользователя
            user_payload = {
                "UserInfo": {
                    "employeeNo": employee_no,
                    "name": name,
                    "userType": "normal",
                    "Valid": {
                        "enable": True,
                        "beginTime": "2025-01-01T00:00:00",
                        "endTime": "2035-12-31T23:59:59"
                    },
                    "doorRight": "1",
                    "RightPlan": [{"doorNo": 1, "planTemplateNo": "1"}]
                }
            }

            logger.info(f"[ADD_USER_WITH_FACE] Шаг 2: Создание пользователя...")
            logger.info(f"[ADD_USER_WITH_FACE] Payload: {user_payload}")
            client = await self._get_client()
            user_url = f"{self.base_url}/ISAPI/AccessControl/UserInfo/Record?format=json"

            user_response = await client.post(user_url, auth=self.auth, json=user_payload, timeout=self.timeout)
            logger.info(f"[ADD_USER_WITH_FACE] Ответ на создание пользователя: {user_response.status_code}")
            logger.info(f"[ADD_USER_WITH_FACE] Тело ответа: {user_response.text[:500]}")

            if user_response.status_code not in [200, 201]:
                result["error"] = f"Failed to create user: HTTP {user_response.status_code} - {user_response.text}"
                return result

            result["user_created"] = True
            logger.info(f"[ADD_USER_WITH_FACE] ✅ Пользователь {employee_no} создан")

            # Шаг 3: Добавляем лицо
            logger.info(f"[ADD_USER_WITH_FACE] Шаг 3: Добавление лица...")
            face_result = await self.add_face_to_user_json(employee_no, photo_bytes, name)

            if face_result["success"]:
                result["face_uploaded"] = True
                result["success"] = True
                logger.info(f"[ADD_USER_WITH_FACE] ✅ Лицо для {employee_no} добавлено")
            else:
                result["error"] = f"Failed to add face: {face_result['error']}"
                logger.error(f"[ADD_USER_WITH_FACE] ❌ Ошибка добавления лица: {face_result['error']}")

        except Exception as e:
            logger.error(f"[ADD_USER_WITH_FACE] Критическая ошибка: {e}", exc_info=True)
            result["error"] = str(e)
        finally:
            logger.info(f"[ADD_USER_WITH_FACE] ===== ЗАВЕРШЕНИЕ (success={result['success']}, fdlib_ensured={result['fdlib_ensured']}) =====")

        return result

    async def create_user_basic(self, employee_no: str, name: str, department: Optional[str] = None) -> Dict[str, Any]:
        """
        Создание пользователя БЕЗ фото. Используется перед запуском CaptureFaceData,
        чтобы терминал ожидал фото существующего user.
        """
        result = {
            "success": False,
            "error": None
        }

        try:
            user_payload = {
                "UserInfo": {
                    "employeeNo": employee_no,
                    "name": name,
                    "userType": "normal",
                    "Valid": {
                        "enable": True,
                        "beginTime": "2025-01-01T00:00:00",
                        "endTime": "2035-12-31T23:59:59"
                    },
                    "doorRight": "1",
                    "RightPlan": [{"doorNo": 1, "planTemplateNo": "1"}]
                }
            }
            if department:
                user_payload["UserInfo"]["department"] = department

            client = await self._get_client()
            user_url = f"{self.base_url}/ISAPI/AccessControl/UserInfo/Record?format=json"
            user_response = await client.post(user_url, auth=self.auth, json=user_payload, timeout=self.timeout)

            if user_response.status_code in [200, 201]:
                result["success"] = True
            else:
                result["error"] = f"HTTP {user_response.status_code}: {user_response.text}"
        except Exception as e:
            logger.error(f"[CREATE_USER_BASIC] Ошибка: {e}", exc_info=True)
            result["error"] = str(e)

        return result
    
    async def get_users(self) -> Optional[List[Dict[str, Any]]]:
        """
        Получение списка пользователей с терминала.
        Возвращает список словарей с информацией о пользователях.
        """
        try:
            client = await self._get_client()
            import uuid
            search_id = str(uuid.uuid4()).replace('-', '')
            
            payload = {
                "UserInfoSearchCond": {
                    "searchID": search_id,
                    "maxResults": 1000,
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
                logger.info(f"[GET_USERS] Найдено пользователей: {len(users)}")
                return users
            else:
                logger.warning(f"[GET_USERS] Не удалось получить пользователей: HTTP {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"[GET_USERS] Ошибка получения пользователей: {e}", exc_info=True)
            return None
    
    async def start_face_capture_mode(self, employee_no: Optional[str] = None, user_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Запуск режима захвата фото с терминала.
        Если employee_no указан, терминал будет ожидать фото для этого пользователя.
        """
        result = {
            "success": False,
            "message": "",
            "photo_path": None,
            "face_data_url": None,
            "face_uploaded": False
        }
        
        try:
            client = await self._get_client()
            
            # Пробуем несколько вариантов XML (некоторые прошивки требуют пустое тело)
            payloads = []
            if employee_no:
                payloads.append(f"""<?xml version="1.0" encoding="UTF-8"?>
<CaptureFaceData>
    <employeeNo>{employee_no}</employeeNo>
</CaptureFaceData>""")
            payloads.append("""<?xml version="1.0" encoding="UTF-8"?>
<CaptureFaceData>
</CaptureFaceData>""")

            responses_debug = []
            success = False
            face_data_url = None

            for idx, xml_data in enumerate(payloads):
                response = await client.post(
                    f"{self.base_url}/ISAPI/AccessControl/CaptureFaceData",
                    auth=self.auth,
                    content=xml_data.encode('utf-8'),
                    headers={"Content-Type": "application/xml; charset=UTF-8"},
                    timeout=self.timeout
                )

                responses_debug.append({"variant": idx + 1, "status": response.status_code, "body": response.text[:500]})
                logger.info(f"[START_FACE_CAPTURE] variant={idx+1} HTTP {response.status_code}, body: {response.text[:500]}")

                if response.status_code == 200:
                    try:
                        from xml.etree import ElementTree as ET
                        root = ET.fromstring(response.text)
                        for elem in root.iter():
                            if 'faceURL' in elem.tag or 'faceDataURL' in elem.tag:
                                face_data_url = elem.text
                                break
                        success = True
                        break
                    except Exception as parse_err:
                        logger.warning(f"[START_FACE_CAPTURE] variant={idx+1} parse error: {parse_err}")
                        continue

            if success:
                result["success"] = True
                result["face_data_url"] = face_data_url
                result["message"] = f"Face captured successfully for employee {employee_no}" if employee_no else "Face captured successfully"
                result["raw_response"] = str(responses_debug)
            else:
                result["message"] = "Failed to capture face with all variants"
                result["raw_response"] = str(responses_debug)

        except Exception as e:
            logger.error(f"[START_FACE_CAPTURE] Ошибка: {e}", exc_info=True)
            result["message"] = f"Error: {str(e)}"
        
        return result

    async def check_face_info(self, employee_no: str) -> Optional[Dict[str, Any]]:
        """
        Проверка наличия фото лица для пользователя.
        """
        try:
            users = await self.get_users()
            if users:
                for user in users:
                    if user.get("employeeNo") == employee_no:
                        num_of_face = user.get("numOfFace", 0)
                        face_url = user.get("faceURL")
                        return {
                            "has_face": num_of_face > 0,
                            "num_of_face": num_of_face,
                            "face_url": face_url
                        }
            return None
        except Exception as e:
            logger.error(f"[CHECK_FACE_INFO] Ошибка: {e}", exc_info=True)
            return None
    
    async def add_face_to_user(self, employee_no: str, photo_bytes: bytes) -> bool:
        """
        Добавление фото к существующему пользователю (алиас для add_face_to_user_json).
        """
        result = await self.add_face_to_user_json(employee_no, photo_bytes)
        return result.get("success", False)

    async def capture_snapshot(self, channel_id: int = 1) -> bytes:
        """
        Получение снимка с камеры терминала.
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/ISAPI/Streaming/channels/{channel_id}/picture",
                auth=self.auth,
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.content
            else:
                raise Exception(f"Failed to capture snapshot: HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"[CAPTURE_SNAPSHOT] Ошибка: {e}", exc_info=True)
            raise

    async def get_user_face_data(self, employee_no: str) -> Optional[bytes]:
        """
        Получение фото лица пользователя с терминала.
        """
        try:
            face_info = await self.check_face_info(employee_no)
            if face_info and face_info.get("face_url"):
                face_url = face_info["face_url"]
                # Извлекаем путь из URL
                if "@" in face_url:
                    path = face_url.split("@")[0].replace("https://", "").replace("http://", "")
                    if "/" in path:
                        path = "/" + "/".join(path.split("/")[1:])
                else:
                    path = face_url
                
                client = await self._get_client()
                response = await client.get(
                    f"{self.base_url}{path}",
                    auth=self.auth,
                    timeout=self.timeout
                )
                if response.status_code == 200:
                    return response.content
            return None
        except Exception as e:
            logger.error(f"[GET_USER_FACE_DATA] Ошибка: {e}", exc_info=True)
            return None

    async def get_system_capabilities(self, format: str = "json") -> Optional[Dict[str, Any]]:
        """
        Получение capabilities системы.
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/ISAPI/AccessControl/capabilities?format={format}",
                auth=self.auth,
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json() if format == "json" else response.text
            return None
        except Exception as e:
            logger.error(f"[GET_SYSTEM_CAPABILITIES] Ошибка: {e}", exc_info=True)
            return None

    async def check_remote_control_settings(self) -> Optional[Dict[str, Any]]:
        """
        Проверка настроек Remote Control.
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/ISAPI/AccessControl/RemoteControl/capabilities?format=json",
                auth=self.auth,
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"[CHECK_REMOTE_CONTROL] Ошибка: {e}", exc_info=True)
            return None
    
    async def get_supported_features_summary(self) -> Optional[Dict[str, Any]]:
        """
        Получение сводки поддерживаемых функций.
        """
        try:
            capabilities = await self.get_system_capabilities()
            if not capabilities:
                return None
            
            # Упрощенная версия - возвращаем основные возможности
            return {
                "user_management": capabilities.get("isSupportUserInfo", False),
                "face_recognition": True,  # Предполагаем поддержку
                "remote_control": False  # Требует проверки
            }
        except Exception as e:
            logger.error(f"[GET_FEATURES_SUMMARY] Ошибка: {e}", exc_info=True)
            return None

    async def discover_isapi_endpoints(self) -> Optional[Dict[str, Any]]:
        """
        Обнаружение доступных ISAPI endpoints.
        """
        try:
            # Базовая проверка основных endpoints
            endpoints = {
                "deviceInfo": f"{self.base_url}/ISAPI/System/deviceInfo",
                "userInfo": f"{self.base_url}/ISAPI/AccessControl/UserInfo",
                "fdLib": f"{self.base_url}/ISAPI/Intelligent/FDLib"
            }
            return endpoints
        except Exception as e:
            logger.error(f"[DISCOVER_ENDPOINTS] Ошибка: {e}", exc_info=True)
            return None

    async def start_remote_registration(self, employee_no: str, name: str, timeout: int = 60) -> Dict[str, Any]:
        """
        Запуск удаленной регистрации на терминале.
        """
        result = {
            "success": False,
            "message": "",
            "error": None
        }
        
        try:
            client = await self._get_client()
            payload = {
                "RemoteControl": {
                    "cmd": "register",
                    "employeeNo": employee_no,
                    "name": name,
                    "timeout": timeout
                }
            }
            
            response = await client.put(
                f"{self.base_url}/ISAPI/AccessControl/RemoteControl/register?format=json",
                auth=self.auth,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result["success"] = True
                result["message"] = "Remote registration started"
            else:
                error_data = response.json() if response.status_code == 400 else {}
                result["error"] = error_data.get("errorMsg", f"HTTP {response.status_code}")
                result["message"] = f"Failed to start remote registration: {result['error']}"
        except Exception as e:
            logger.error(f"[START_REMOTE_REGISTRATION] Ошибка: {e}", exc_info=True)
            result["error"] = str(e)
            result["message"] = f"Error: {str(e)}"
        
        return result
    
    async def get_face_data_by_id(self, face_id: str) -> Optional[bytes]:
        """
        Получение фото лица по ID.
        """
        # Алиас для get_user_face_data
        return await self.get_user_face_data(face_id)

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
