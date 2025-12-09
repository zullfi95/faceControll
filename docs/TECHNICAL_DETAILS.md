# Технические детали реализации

Документация по техническим аспектам интеграции с терминалами Hikvision через ISAPI.

## Архитектура системы

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Frontend  │ ──────► │    Backend   │ ──────► │  Hikvision   │
│   (React)   │         │   (FastAPI)  │         │   Terminal   │
└─────────────┘         └──────────────┘         └─────────────┘
                              │
                              ▼
                        ┌─────────────┐
                        │  PostgreSQL  │
                        └─────────────┘
```

## Процесс создания пользователя с фото

### Текущая реализация (двухэтапный процесс)

Система использует двухэтапный процесс для создания пользователя с фото:

#### Шаг 1: Создание пользователя

**Endpoint:** `POST /ISAPI/AccessControl/UserInfo/Record?format=json`

**Payload (JSON):**
```json
{
  "UserInfo": {
    "employeeNo": "1001",
    "name": "Иван Иванов",
    "userType": "normal",
    "Valid": {
      "enable": true,
      "beginTime": "2025-01-01T00:00:00",
      "endTime": "2035-12-31T23:59:59"
    },
    "doorRight": "1",
    "RightPlan": [
      {
        "doorNo": 1,
        "planTemplateNo": "1"
      }
    ]
  }
}
```

**Ответ:**
```json
{
  "ResponseStatus": {
    "statusCode": 1,
    "statusString": "OK"
  }
}
```

#### Шаг 2: Добавление фото лица

**Endpoint:** `POST /ISAPI/Intelligent/FDLib?format=json`

**Payload (JSON):**
```json
{
  "faceLibType": "blackFD",
  "name": "1001_1234567890",
  "FaceDataRecord": {
    "FDID": "2",
    "faceURL": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
  }
}
```

**Важные моменты:**
- `FDID` должен быть уникальным числом (строка)
- `name` должен быть уникальным (используется timestamp для уникальности)
- `faceURL` содержит base64-encoded JPEG с префиксом `data:image/jpeg;base64,`
- Размер base64 данных не должен превышать лимит `faceURLLen` из capabilities (обычно 1024 символа)

**Ответ:**
```json
{
  "statusCode": 1,
  "statusString": "OK"
}
```

### Ограничения и требования

1. **EmployeeNo (hikvision_id):**
   - Только ASCII символы: `a-zA-Z0-9_-`
   - Максимальная длина: 32 символа
   - Должен быть уникальным

2. **Фото:**
   - Формат: JPEG
   - Рекомендуемый размер: до 200 KB
   - Качество: анфас, хорошее освещение
   - Автоматическое сжатие до 200 KB при загрузке

3. **FDLib:**
   - Максимальное количество лиц: `FDMaxNum` (обычно 2)
   - Максимальная длина имени: `FDNameMaxLen` (обычно 48 символов)
   - Максимальная длина faceURL: `faceURLLen` (обычно 1024 символа)

## ISAPI Endpoints

### Получение информации об устройстве

**Endpoint:** `GET /ISAPI/System/deviceInfo`

**Использование:**
```python
response = await client.get(f"{base_url}/ISAPI/System/deviceInfo", auth=auth)
device_info = response.json()
```

### Получение списка пользователей

**Endpoint:** `GET /ISAPI/AccessControl/UserInfo/Search?format=json`

**Payload:**
```json
{
  "UserInfoSearchCond": {
    "searchID": "unique_search_id",
    "maxResults": 100,
    "searchResultPosition": 0
  }
}
```

### Проверка capabilities

**UserInfo capabilities:**
```
GET /ISAPI/AccessControl/UserInfo/capabilities?format=json
```

**FDLib capabilities:**
```
GET /ISAPI/Intelligent/FDLib/capabilities?format=json
```

## Обработка ошибок

### Типичные ошибки

1. **`badJsonContent`** - Неправильный формат JSON payload
   - Проверьте структуру payload
   - Убедитесь, что все обязательные поля присутствуют

2. **`employeeNoAlreadyExist`** - Пользователь уже существует
   - Проверьте существование пользователя перед созданием
   - Используйте другой `employeeNo`

3. **`faceLibraryNumError`** - Ошибка при добавлении лица в FDLib
   - Проверьте уникальность `FDID` и `name`
   - Убедитесь, что не превышен лимит `FDMaxNum`
   - Проверьте размер `faceURL`

4. **`401 Unauthorized`** - Проблема с аутентификацией
   - Проверьте логин/пароль
   - Убедитесь, что ISAPI включен на терминале

5. **`notSupport`** - Операция не поддерживается
   - Проверьте capabilities устройства
   - Обновите прошивку терминала

## Аутентификация

Система использует **Digest Authentication** для всех ISAPI запросов:

```python
from httpx import DigestAuth

auth = DigestAuth(username, password)
response = await client.get(url, auth=auth)
```

## Логирование

Все операции логируются с префиксами:
- `[ADD_USER_WITH_FACE]` - создание пользователя
- `[ADD_FACE_JSON]` - добавление фото
- `[FD_LIB_CAPS]` - получение capabilities

Пример лога:
```
[ADD_USER_WITH_FACE] ===== НАЧАЛО СОЗДАНИЯ ПОЛЬЗОВАТЕЛЯ С ЛИЦОМ: 1001 =====
[ADD_USER_WITH_FACE] Шаг 1: Создание пользователя...
[ADD_USER_WITH_FACE] ✅ Пользователь 1001 создан
[ADD_USER_WITH_FACE] Шаг 2: Добавление лица...
[ADD_FACE_JSON] Используем FDID: 2, name: 1001_1234567890 для employeeNo: 1001
[ADD_FACE_JSON] ✅ Лицо успешно добавлено для 1001
[ADD_USER_WITH_FACE] ✅ Лицо для 1001 добавлено
```

## Производительность

- Создание пользователя: ~1-2 секунды
- Добавление фото: ~2-5 секунд (зависит от размера фото)
- Общее время синхронизации: ~3-7 секунд

## Безопасность

1. **Пароли устройств:**
   - Хранятся в зашифрованном виде в БД
   - Используется Fernet encryption (AES-128)

2. **API ключ для webhook:**
   - Генерируется случайно при инициализации
   - Хранится в `.env` файле
   - Используется для защиты webhook endpoint

3. **VPN туннель:**
   - Все коммуникации с терминалом через WireGuard VPN
   - Защита от несанкционированного доступа

## Известные ограничения

1. **FDLib API:**
   - Добавление лица к существующему пользователю через FDLib API работает нестабильно
   - Ошибка `faceLibraryNumError` с `errorMsg: "name"` может возникать
   - **Решение:** Использовать двухэтапный процесс (создание пользователя + добавление фото)

2. **Remote Registration:**
   - Не поддерживается на прошивке V4.38.0
   - Требуется обновление прошивки до V4.50+

3. **Размер фото:**
   - Большие фото (>200 KB) могут вызывать таймауты
   - Система автоматически сжимает фото до 200 KB

## Ссылки

- [ISAPI Documentation](docs/ISAPI_Face Recognition Terminals_Value Series-111-125.txt)
- [Hikvision Technical Support](https://www.hikvision.com/en/support/)

