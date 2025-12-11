# Полное руководство: Регистрация пользователя с лицом через ISAPI

**Версия:** 1.0  
**Дата:** 2025-01-10  
**Для:** Внешние интерфейсы, использующие Hikvision ISAPI

---

## Содержание

1. [Обзор процесса](#обзор-процесса)
2. [Аутентификация](#аутентификация)
3. [Шаг 1: Захват фото с терминала](#шаг-1-захват-фото-с-терминала)
4. [Шаг 2: Создание пользователя](#шаг-2-создание-пользователя)
5. [Шаг 3: Привязка фото к пользователю](#шаг-3-привязка-фото-к-пользователю)
6. [Полный пример реализации](#полный-пример-реализации)
7. [Обработка ошибок](#обработка-ошибок)
8. [Нерабочие методы (справочно)](#нерабочие-методы-справочно)

---

## Обзор процесса

Регистрация пользователя с лицом на терминале Hikvision состоит из **трех основных шагов**:

```
┌─────────────────────────────────────────────────────────────┐
│  ШАГ 1: CaptureFaceData                                     │
│  POST /ISAPI/AccessControl/CaptureFaceData                   │
│  → Пользователь предъявляет лицо к терминалу                │
│  → Терминал создает файл web_face_enrollpic.jpg              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  ШАГ 2: UserInfo/Record                                     │
│  POST /ISAPI/AccessControl/UserInfo/Record                   │
│  → Создание пользователя на терминале                       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  ШАГ 3: FDSetUp                                             │
│  PUT /ISAPI/Intelligent/FDLib/FDSetUp                       │
│  → Привязка фото (web_face_enrollpic.jpg) к пользователю    │
└─────────────────────────────────────────────────────────────┘
```

**Важно:** Это **единственный рабочий способ** загрузки фото на терминал. Все остальные методы не поддерживаются или возвращают ошибки.

---

## Аутентификация

Все запросы к терминалу Hikvision требуют **Digest Authentication** (RFC 2617).

### Параметры подключения

- **Протокол:** HTTPS (рекомендуется) или HTTP
- **IP адрес:** IP адрес терминала (например: `192.168.1.67`)
- **Порт:** 443 (HTTPS) или 80 (HTTP)
- **Username:** Имя пользователя администратора
- **Password:** Пароль администратора

### Пример настройки клиента (Python httpx)

```python
import httpx

base_url = "https://192.168.1.67:443"
username = "admin"
password = "your_password"

# Создание клиента с Digest Auth
client = httpx.AsyncClient(
    auth=httpx.DigestAuth(username, password),
    verify=False,  # Отключение проверки SSL для самоподписанных сертификатов
    timeout=30.0
)
```

### Пример настройки клиента (JavaScript/Node.js)

```javascript
const axios = require('axios');
const http = require('http');

const baseURL = 'https://192.168.1.67:443';
const username = 'admin';
const password = 'your_password';

// Для Digest Auth в Node.js используйте библиотеку axios-digest
const axiosDigest = require('axios-digest');
const client = axiosDigest.default(username, password);
```

---

## Шаг 1: Захват фото с терминала

### Endpoint

**POST** `/ISAPI/AccessControl/CaptureFaceData`

### Описание

Запускает режим захвата лица на терминале. После предъявления лица к терминалу, устройство создает временный файл `web_face_enrollpic.jpg` в папке `/LOCALS/pic/` и возвращает его URL.

### Запрос

**URL:** `https://192.168.1.67:443/ISAPI/AccessControl/CaptureFaceData`

**Headers:**
```
Content-Type: application/x-www-form-urlencoded
```

**Body (XML):**
```xml
<CaptureFaceDataCond version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
    <captureInfrared>false</captureInfrared>
    <dataType>url</dataType>
</CaptureFaceDataCond>
```

### Ответ (успех)

**HTTP Status:** `200 OK`

**Body (XML):**
```xml
<CaptureFaceDataResponse version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
    <captureProgress>100</captureProgress>
    <faceDataUrl>https://192.168.1.67/LOCALS/pic/web_face_enrollpic.jpg@WEB000000000020</faceDataUrl>
</CaptureFaceDataResponse>
```

**Поля ответа:**
- `captureProgress` - прогресс захвата (0-100). `100` означает успешный захват.
- `faceDataUrl` - URL созданного файла на терминале. Этот URL используется в шаге 3.

### Ответ (ожидание)

Если лицо еще не предъявлено, терминал возвращает:

```xml
<CaptureFaceDataResponse version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
    <captureProgress>0</captureProgress>
</CaptureFaceDataResponse>
```

В этом случае нужно:
1. Подождать несколько секунд (например, 2-5 секунд)
2. Повторить запрос
3. Пользователь должен предъявить лицо к терминалу в течение этого времени

### Пример реализации (Python)

```python
import httpx
import asyncio
import xml.etree.ElementTree as ET

async def capture_face_data(base_url: str, auth: httpx.DigestAuth, max_retries: int = 10, retry_delay: float = 2.0):
    """
    Захват фото с терминала.
    
    Args:
        base_url: Базовый URL терминала (например: "https://192.168.1.67:443")
        auth: Объект DigestAuth для аутентификации
        max_retries: Максимальное количество повторных попыток
        retry_delay: Задержка между попытками в секундах
    
    Returns:
        dict: {"success": bool, "face_data_url": str, "error": str}
    """
    client = httpx.AsyncClient(auth=auth, verify=False, timeout=30.0)
    
    capture_xml = """<CaptureFaceDataCond version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
    <captureInfrared>false</captureInfrared>
    <dataType>url</dataType>
</CaptureFaceDataCond>"""
    
    try:
        for attempt in range(max_retries + 1):
            response = await client.post(
                f"{base_url}/ISAPI/AccessControl/CaptureFaceData",
                content=capture_xml,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
            
            # Парсим XML ответ
            root = ET.fromstring(response.text)
            capture_progress = 0
            face_data_url = None
            
            for elem in root.iter():
                if elem.tag.endswith('captureProgress'):
                    try:
                        capture_progress = int(elem.text)
                    except (ValueError, TypeError):
                        capture_progress = 0
                elif elem.tag.endswith('faceDataUrl') or elem.tag.endswith('faceURL'):
                    face_data_url = elem.text
            
            # Если захват завершен
            if capture_progress == 100 and face_data_url:
                return {
                    "success": True,
                    "face_data_url": face_data_url
                }
            
            # Если еще ждем предъявления лица
            if capture_progress < 100 and attempt < max_retries:
                await asyncio.sleep(retry_delay)
                continue
            
            # Все попытки исчерпаны
            return {
                "success": False,
                "error": f"Face capture timeout. Progress: {capture_progress}%"
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        await client.aclose()
```

### Пример реализации (JavaScript/Node.js)

```javascript
const axios = require('axios');
const xml2js = require('xml2js');

async function captureFaceData(baseURL, auth, maxRetries = 10, retryDelay = 2000) {
    const captureXML = `<CaptureFaceDataCond version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
    <captureInfrared>false</captureInfrared>
    <dataType>url</dataType>
</CaptureFaceDataCond>`;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
            const response = await axios.post(
                `${baseURL}/ISAPI/AccessControl/CaptureFaceData`,
                captureXML,
                {
                    auth: auth,
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    httpsAgent: new https.Agent({ rejectUnauthorized: false })
                }
            );

            // Парсим XML
            const parser = new xml2js.Parser();
            const result = await parser.parseStringPromise(response.data);
            
            const responseData = result.CaptureFaceDataResponse || {};
            const captureProgress = parseInt(responseData.captureProgress?.[0] || '0');
            const faceDataUrl = responseData.faceDataUrl?.[0] || responseData.faceURL?.[0];

            if (captureProgress === 100 && faceDataUrl) {
                return {
                    success: true,
                    face_data_url: faceDataUrl
                };
            }

            if (captureProgress < 100 && attempt < maxRetries) {
                await new Promise(resolve => setTimeout(resolve, retryDelay));
                continue;
            }

            return {
                success: false,
                error: `Face capture timeout. Progress: ${captureProgress}%`
            };

        } catch (error) {
            if (attempt === maxRetries) {
                return {
                    success: false,
                    error: error.message
                };
            }
            await new Promise(resolve => setTimeout(resolve, retryDelay));
        }
    }
}
```

### Важные замечания

1. **Таймаут:** Пользователь должен предъявить лицо к терминалу в течение 5-10 секунд после вызова.
2. **Повторные запросы:** Если `captureProgress < 100`, нужно повторить запрос через 2-5 секунд.
3. **Файл на терминале:** После успешного захвата файл `web_face_enrollpic.jpg` создается на терминале и доступен по URL из `faceDataUrl`.

---

## Шаг 2: Создание пользователя

### Endpoint

**POST** `/ISAPI/AccessControl/UserInfo/Record?format=json`

### Описание

Создает нового пользователя на терминале с указанными параметрами (ID, имя, группа и т.д.).

### Запрос

**URL:** `https://192.168.1.67:443/ISAPI/AccessControl/UserInfo/Record?format=json`

**Headers:**
```
Content-Type: application/json
```

**Body (JSON):**
```json
{
  "UserInfo": {
    "employeeNo": "100222",
    "name": "Иван Иванов",
    "userType": "normal",
    "Valid": {
      "enable": true,
      "beginTime": "2025-01-01T00:00:00",
      "endTime": "2035-01-01T00:00:00",
      "timeType": "local"
    },
    "gender": "unknown"
  }
}
```

**Поля:**
- `employeeNo` (обязательно) - ID сотрудника (строка, максимум 32 символа, только ASCII)
- `name` (обязательно) - ФИО пользователя
- `userType` - Тип пользователя: `"normal"` (обычный) или `"blacklist"` (черный список)
- `Valid.enable` - Включена ли валидность пользователя
- `Valid.beginTime` - Начало действия (ISO 8601)
- `Valid.endTime` - Конец действия (ISO 8601)
- `Valid.timeType` - Тип времени: `"local"` или `"utc"`
- `gender` - Пол: `"male"`, `"female"` или `"unknown"`

**С группой:**
```json
{
  "UserInfo": {
    "employeeNo": "100222",
    "name": "Иван Иванов",
    "userType": "normal",
    "groupId": 1,
    "Valid": {
      "enable": true,
      "beginTime": "2025-01-01T00:00:00",
      "endTime": "2035-01-01T00:00:00",
      "timeType": "local"
    },
    "gender": "unknown"
  }
}
```

### Ответ (успех)

**HTTP Status:** `200 OK`

**Body (JSON):**
```json
{
  "statusCode": 1,
  "statusString": "OK",
  "subStatusCode": "ok"
}
```

### Ответ (ошибка)

**HTTP Status:** `400 Bad Request` или `401 Unauthorized`

**Body (JSON):**
```json
{
  "statusCode": 4,
  "statusString": "Invalid Operation",
  "subStatusCode": "deviceUserAlreadyExist",
  "errorCode": 1610612753,
  "errorMsg": "The user already exists"
}
```

### Пример реализации (Python)

```python
async def create_user(
    base_url: str,
    auth: httpx.DigestAuth,
    employee_no: str,
    name: str,
    group_id: int = None
):
    """
    Создание пользователя на терминале.
    
    Args:
        base_url: Базовый URL терминала
        auth: Объект DigestAuth
        employee_no: ID сотрудника
        name: ФИО пользователя
        group_id: ID группы (опционально)
    
    Returns:
        dict: {"success": bool, "error": str}
    """
    client = httpx.AsyncClient(auth=auth, verify=False, timeout=30.0)
    
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
    
    try:
        response = await client.post(
            f"{base_url}/ISAPI/AccessControl/UserInfo/Record?format=json",
            json=user_data
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("statusCode") == 1:
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error": data.get("errorMsg", "Unknown error")
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
    finally:
        await client.aclose()
```

### Пример реализации (JavaScript/Node.js)

```javascript
async function createUser(baseURL, auth, employeeNo, name, groupId = null) {
    const userData = {
        UserInfo: {
            employeeNo: employeeNo,
            name: name,
            userType: "normal",
            Valid: {
                enable: true,
                beginTime: "2025-01-01T00:00:00",
                endTime: "2035-01-01T00:00:00",
                timeType: "local"
            },
            gender: "unknown"
        }
    };

    if (groupId !== null) {
        userData.UserInfo.groupId = groupId;
    }

    try {
        const response = await axios.post(
            `${baseURL}/ISAPI/AccessControl/UserInfo/Record?format=json`,
            userData,
            {
                auth: auth,
                httpsAgent: new https.Agent({ rejectUnauthorized: false })
            }
        );

        if (response.data.statusCode === 1) {
            return { success: true };
        } else {
            return {
                success: false,
                error: response.data.errorMsg || "Unknown error"
            };
        }
    } catch (error) {
        return {
            success: false,
            error: error.message
        };
    }
}
```

---

## Шаг 3: Привязка фото к пользователю

### Endpoint

**PUT** `/ISAPI/Intelligent/FDLib/FDSetUp?format=json`

### Описание

Привязывает существующий файл фото на терминале к пользователю через FDLib (Face Detection Library). Использует URL файла, созданного в шаге 1 (`web_face_enrollpic.jpg`).

### Запрос

**URL:** `https://192.168.1.67:443/ISAPI/Intelligent/FDLib/FDSetUp?format=json`

**Headers:**
```
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary...
```

**Body (multipart/form-data):**
```
------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="FaceDataRecord"

{"faceLibType":"blackFD","FDID":"1","FPID":"100222","faceURL":"https://192.168.1.67/LOCALS/pic/web_face_enrollpic.jpg@WEB000000000020"}
------WebKitFormBoundary7MA4YWxkTrZu0gW--
```

**JSON в поле FaceDataRecord:**
```json
{
  "faceLibType": "blackFD",
  "FDID": "1",
  "FPID": "100222",
  "faceURL": "https://192.168.1.67/LOCALS/pic/web_face_enrollpic.jpg@WEB000000000020"
}
```

**Поля:**
- `faceLibType` - Тип библиотеки лиц: `"blackFD"` (черный список) или `"whiteFD"` (белый список)
- `FDID` - ID библиотеки лиц (обычно `"1"`)
- `FPID` - ID пользователя (должен совпадать с `employeeNo` из шага 2)
- `faceURL` - URL файла фото на терминале (из шага 1)

### Ответ (успех)

**HTTP Status:** `200 OK`

**Body (JSON):**
```json
{
  "statusCode": 1,
  "statusString": "OK",
  "subStatusCode": "ok"
}
```

### Ответ (ошибка)

**HTTP Status:** `400 Bad Request`

**Body (JSON):**
```json
{
  "statusCode": 5,
  "statusString": "Invalid Format",
  "subStatusCode": "badJsonFormat",
  "errorCode": 1342177282,
  "errorMsg": "JSON format error"
}
```

### Пример реализации (Python)

```python
import json
import uuid

async def setup_user_face(
    base_url: str,
    auth: httpx.DigestAuth,
    employee_no: str,
    face_url: str
):
    """
    Привязка фото к пользователю через FDSetUp.
    
    Args:
        base_url: Базовый URL терминала
        auth: Объект DigestAuth
        employee_no: ID сотрудника (FPID)
        face_url: URL файла фото на терминале (из CaptureFaceData)
    
    Returns:
        dict: {"success": bool, "error": str}
    """
    client = httpx.AsyncClient(auth=auth, verify=False, timeout=30.0)
    
    # Формируем JSON данные
    face_data = {
        "faceLibType": "blackFD",
        "FDID": "1",
        "FPID": employee_no,
        "faceURL": face_url
    }
    
    # Формируем multipart body
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    face_data_str = json.dumps(face_data, separators=(',', ':'))
    
    body_parts = [
        f'--{boundary}\r\n',
        f'Content-Disposition: form-data; name="FaceDataRecord"\r\n\r\n',
        f'{face_data_str}\r\n',
        f'--{boundary}--\r\n'
    ]
    body = ''.join(body_parts).encode('utf-8')
    
    try:
        response = await client.put(
            f"{base_url}/ISAPI/Intelligent/FDLib/FDSetUp?format=json",
            content=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body))
            }
        )
        
        if response.status_code == 200:
            try:
                data = response.json()
                if data.get("statusCode") == 1:
                    return {"success": True}
                else:
                    return {
                        "success": False,
                        "error": data.get("errorMsg", "Unknown error")
                    }
            except:
                # Если ответ не JSON, но статус 200 - считаем успехом
                return {"success": True}
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
    finally:
        await client.aclose()
```

### Пример реализации (JavaScript/Node.js)

```javascript
const FormData = require('form-data');

async function setupUserFace(baseURL, auth, employeeNo, faceURL) {
    const faceData = {
        faceLibType: "blackFD",
        FDID: "1",
        FPID: employeeNo,
        faceURL: faceURL
    };

    const form = new FormData();
    form.append('FaceDataRecord', JSON.stringify(faceData));

    try {
        const response = await axios.put(
            `${baseURL}/ISAPI/Intelligent/FDLib/FDSetUp?format=json`,
            form,
            {
                auth: auth,
                headers: form.getHeaders(),
                httpsAgent: new https.Agent({ rejectUnauthorized: false })
            }
        );

        if (response.data.statusCode === 1) {
            return { success: true };
        } else {
            return {
                success: false,
                error: response.data.errorMsg || "Unknown error"
            };
        }
    } catch (error) {
        return {
            success: false,
            error: error.message
        };
    }
}
```

### Важные замечания

1. **Токен не требуется:** FDSetUp работает с Digest Auth, токен безопасности не обязателен.
2. **Формат multipart:** Важно правильно сформировать multipart/form-data с полем `FaceDataRecord`.
3. **URL должен быть внутренним:** `faceURL` должен указывать на файл на самом терминале (например, `web_face_enrollpic.jpg`), а не на внешний сервер.

---

## Полный пример реализации

### Python (asyncio)

```python
import httpx
import asyncio
import xml.etree.ElementTree as ET
import json
import uuid

class HikvisionUserRegistration:
    def __init__(self, ip: str, username: str, password: str, use_https: bool = True):
        protocol = "https" if use_https else "http"
        port = 443 if use_https else 80
        self.base_url = f"{protocol}://{ip}:{port}"
        self.auth = httpx.DigestAuth(username, password)
        self.client = None
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            auth=self.auth,
            verify=False,
            timeout=30.0
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def capture_face(self, max_retries: int = 10, retry_delay: float = 2.0):
        """Шаг 1: Захват фото"""
        capture_xml = """<CaptureFaceDataCond version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
    <captureInfrared>false</captureInfrared>
    <dataType>url</dataType>
</CaptureFaceDataCond>"""
        
        for attempt in range(max_retries + 1):
            response = await self.client.post(
                f"{self.base_url}/ISAPI/AccessControl/CaptureFaceData",
                content=capture_xml,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            root = ET.fromstring(response.text)
            capture_progress = 0
            face_data_url = None
            
            for elem in root.iter():
                if elem.tag.endswith('captureProgress'):
                    try:
                        capture_progress = int(elem.text)
                    except:
                        capture_progress = 0
                elif elem.tag.endswith('faceDataUrl') or elem.tag.endswith('faceURL'):
                    face_data_url = elem.text
            
            if capture_progress == 100 and face_data_url:
                return {"success": True, "face_data_url": face_data_url}
            
            if capture_progress < 100 and attempt < max_retries:
                await asyncio.sleep(retry_delay)
                continue
            
            return {"success": False, "error": f"Timeout. Progress: {capture_progress}%"}
    
    async def create_user(self, employee_no: str, name: str, group_id: int = None):
        """Шаг 2: Создание пользователя"""
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
        
        response = await self.client.post(
            f"{self.base_url}/ISAPI/AccessControl/UserInfo/Record?format=json",
            json=user_data
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("statusCode") == 1:
                return {"success": True}
            else:
                return {"success": False, "error": data.get("errorMsg", "Unknown error")}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}"}
    
    async def setup_face(self, employee_no: str, face_url: str):
        """Шаг 3: Привязка фото"""
        face_data = {
            "faceLibType": "blackFD",
            "FDID": "1",
            "FPID": employee_no,
            "faceURL": face_url
        }
        
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        face_data_str = json.dumps(face_data, separators=(',', ':'))
        
        body_parts = [
            f'--{boundary}\r\n',
            f'Content-Disposition: form-data; name="FaceDataRecord"\r\n\r\n',
            f'{face_data_str}\r\n',
            f'--{boundary}--\r\n'
        ]
        body = ''.join(body_parts).encode('utf-8')
        
        response = await self.client.put(
            f"{self.base_url}/ISAPI/Intelligent/FDLib/FDSetUp?format=json",
            content=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body))
            }
        )
        
        if response.status_code == 200:
            try:
                data = response.json()
                if data.get("statusCode") == 1:
                    return {"success": True}
                else:
                    return {"success": False, "error": data.get("errorMsg", "Unknown error")}
            except:
                return {"success": True}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}"}
    
    async def register_user_with_face(
        self,
        employee_no: str,
        name: str,
        group_id: int = None,
        max_capture_retries: int = 10
    ):
        """Полный процесс регистрации пользователя с лицом"""
        # Шаг 1: Захват фото
        print("Шаг 1: Захват фото с терминала...")
        print("Пожалуйста, предъявите лицо к терминалу в течение 10 секунд")
        
        capture_result = await self.capture_face(max_retries=max_capture_retries)
        if not capture_result.get("success"):
            return {
                "success": False,
                "error": f"Face capture failed: {capture_result.get('error')}"
            }
        
        face_url = capture_result.get("face_data_url")
        print(f"✅ Фото захвачено: {face_url}")
        
        # Шаг 2: Создание пользователя
        print(f"Шаг 2: Создание пользователя {employee_no}...")
        create_result = await self.create_user(employee_no, name, group_id)
        if not create_result.get("success"):
            return {
                "success": False,
                "error": f"User creation failed: {create_result.get('error')}"
            }
        
        print(f"✅ Пользователь {employee_no} создан")
        
        # Шаг 3: Привязка фото
        print(f"Шаг 3: Привязка фото к пользователю {employee_no}...")
        setup_result = await self.setup_face(employee_no, face_url)
        if not setup_result.get("success"):
            return {
                "success": False,
                "error": f"Face setup failed: {setup_result.get('error')}"
            }
        
        print(f"✅ Фото привязано к пользователю {employee_no}")
        
        return {
            "success": True,
            "employee_no": employee_no,
            "face_url": face_url
        }


# Использование
async def main():
    async with HikvisionUserRegistration(
        ip="192.168.1.67",
        username="admin",
        password="your_password"
    ) as client:
        result = await client.register_user_with_face(
            employee_no="100222",
            name="Иван Иванов",
            group_id=1
        )
        
        if result.get("success"):
            print("✅ Пользователь успешно зарегистрирован с фото!")
        else:
            print(f"❌ Ошибка: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Обработка ошибок

### Типичные ошибки и решения

#### 1. HTTP 401 Unauthorized

**Причина:** Неверные учетные данные или проблемы с Digest Auth.

**Решение:**
- Проверьте username и password
- Убедитесь, что используется Digest Auth, а не Basic Auth
- Проверьте, что пользователь имеет права администратора

#### 2. HTTP 400 Bad Request (UserInfo/Record)

**Ошибка:** `"deviceUserAlreadyExist"`

**Причина:** Пользователь с таким `employeeNo` уже существует.

**Решение:**
- Используйте другой `employeeNo`
- Или сначала удалите существующего пользователя

#### 3. HTTP 400 Bad Request (FDSetUp)

**Ошибка:** `"badJsonFormat"` или `"badJsonContent"`

**Причина:** Неправильный формат multipart/form-data или JSON.

**Решение:**
- Убедитесь, что multipart body правильно сформирован
- Проверьте, что JSON в поле `FaceDataRecord` валиден
- Убедитесь, что `faceURL` указывает на файл на терминале

#### 4. Face capture timeout

**Причина:** Пользователь не предъявил лицо к терминалу в течение таймаута.

**Решение:**
- Увеличьте `max_retries` и `retry_delay`
- Убедитесь, что пользователь предъявляет лицо к терминалу
- Проверьте освещение и расстояние до терминала

#### 5. HTTP 404 Not Found

**Причина:** Неверный URL эндпоинта или файл не найден.

**Решение:**
- Проверьте правильность URL эндпоинта
- Убедитесь, что файл `web_face_enrollpic.jpg` существует (из шага 1)

---

## Нерабочие методы (справочно)

Следующие методы **не работают** на терминале Hikvision и были удалены из кода:

### 1. pictureUpload

**Endpoint:** `POST /ISAPI/Intelligent/FDLib/pictureUpload`

**Ошибка:** `"notSupport"` - метод не поддерживается терминалом.

### 2. FaceDataRecord с внешним URL

**Endpoint:** `POST /ISAPI/Intelligent/FDLib/FaceDataRecord`

**Ошибка:** `"urlDownloadFail"` - терминал не может скачать фото по внешнему URL.

### 3. FaceDataRecord с base64

**Endpoint:** `POST /ISAPI/Intelligent/FDLib/FaceDataRecord`

**Ошибка:** `"badJsonContent"` - терминал не принимает base64 формат.

### 4. Прямая загрузка в /LOCALS/

**Endpoint:** `PUT /LOCALS/pic/enrlFace/0/{id}.jpg`

**Ошибка:** `405 Method Not Allowed` - PUT не поддерживается для этих путей.

---

## Заключение

**Единственный рабочий способ** регистрации пользователя с лицом:

1. ✅ `CaptureFaceData` - захват фото с терминала
2. ✅ `UserInfo/Record` - создание пользователя
3. ✅ `FDSetUp` - привязка фото к пользователю

Все остальные методы не поддерживаются терминалом или возвращают ошибки.

---

**Версия документа:** 1.0  
**Дата обновления:** 2025-01-10  
**Автор:** FaceControll Development Team

