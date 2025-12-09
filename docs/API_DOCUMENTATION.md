# API Документация

Полная документация REST API системы Face Access Control.

## Базовый URL

- **Production:** `http://46.62.223.55/api`
- **Local:** `http://localhost/api`

## Аутентификация

В текущей версии аутентификация не требуется. Для production рекомендуется добавить JWT или API ключи.

## Endpoints

### Пользователи

#### Создание пользователя

**POST** `/users/`

**Request Body:**
```json
{
  "hikvision_id": "1001",
  "full_name": "Иван Иванов",
  "department": "IT"
}
```

**Response (200):**
```json
{
  "id": 1,
  "hikvision_id": "1001",
  "full_name": "Иван Иванов",
  "department": "IT",
  "is_active": true,
  "photo_path": null,
  "synced_to_device": false,
  "created_at": "2025-12-08T10:00:00"
}
```

**Валидация:**
- `hikvision_id`: обязательное, 1-32 символа, только ASCII (`a-zA-Z0-9_-`)
- `full_name`: обязательное
- `department`: опциональное

#### Получение списка пользователей

**GET** `/users/`

**Query Parameters:**
- `limit` (int, default: 100) - количество записей
- `offset` (int, default: 0) - смещение

**Response (200):**
```json
[
  {
    "id": 1,
    "hikvision_id": "1001",
    "full_name": "Иван Иванов",
    "department": "IT",
    "is_active": true,
    "photo_path": "/uploads/1001_abc123.jpg",
    "synced_to_device": true,
    "created_at": "2025-12-08T10:00:00"
  }
]
```

#### Загрузка фото

**POST** `/users/{user_id}/upload-photo`

**Request:** `multipart/form-data`
- `photo` (file) - файл изображения (JPEG, PNG)

**Response (200):**
```json
{
  "message": "Photo uploaded successfully",
  "photo_path": "/uploads/1001_abc123.jpg"
}
```

**Ограничения:**
- Максимальный размер: 5 MB
- Форматы: JPEG, PNG
- Автоматическое сжатие до 200 KB

#### Синхронизация с терминалом

**POST** `/users/{user_id}/sync-to-device`

**Response (200):**
```json
{
  "message": "User synchronized successfully",
  "face_uploaded": true,
  "photo_already_on_terminal": false
}
```

**Response (400):**
```json
{
  "detail": "User has no photo. Upload photo first."
}
```

**Response (500):**
```json
{
  "detail": "Failed to sync user: <error message>"
}
```

### Устройства

#### Добавление устройства

**POST** `/devices/`

**Request Body:**
```json
{
  "name": "Терминал Вход",
  "ip_address": "10.0.0.100",
  "username": "admin",
  "password": "password123"
}
```

**Response (200):**
```json
{
  "id": 1,
  "name": "Терминал Вход",
  "ip_address": "10.0.0.100",
  "username": "admin",
  "is_active": true,
  "last_sync": null
}
```

#### Получение списка устройств

**GET** `/devices/`

**Response (200):**
```json
[
  {
    "id": 1,
    "name": "Терминал Вход",
    "ip_address": "10.0.0.100",
    "username": "admin",
    "is_active": true,
    "last_sync": "2025-12-08T10:00:00"
  }
]
```

#### Проверка статуса устройства

**GET** `/devices/{device_id}/status`

**Response (200):**
```json
{
  "available": true,
  "device_info": {
    "deviceName": "DS-K1T343EFWX",
    "serialNumber": "DS-K1T343EFWX20241208AABBCCDD",
    "firmwareVersion": "V4.38.0"
  }
}
```

#### Запуск захвата фото

**POST** `/devices/{device_id}/start-face-capture`

**Request Body:**
```json
{
  "hikvision_id": "1001"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Face captured and uploaded successfully for employee 1001",
  "photo_path": "/uploads/captured_1001_abc123.jpg",
  "face_uploaded": false,
  "face_data_url": "http://10.0.0.100/LOCALS/pic/web_face_enrollpic.jpg@WEB000000000207"
}
```

### События

#### Webhook для событий от терминала

**POST** `/events/webhook`

**Headers:**
- `X-API-Key` (optional) - API ключ для защиты

**Request Body:**
```json
{
  "ipAddress": "10.0.0.100",
  "dateTime": "2025-12-08T10:00:00",
  "AccessControllerEvent": {
    "majorEventType": 5,
    "subEventType": 75,
    "employeeNoString": "1001",
    "name": "Иван Иванов"
  }
}
```

**Response (200):**
```json
{
  "status": "ok"
}
```

### Отчеты

#### Дневной отчет

**GET** `/reports/daily`

**Query Parameters:**
- `date_str` (string, format: YYYY-MM-DD, default: today)

**Response (200):**
```json
{
  "date": "2025-12-08",
  "users": [
    {
      "user_id": 1,
      "hikvision_id": "1001",
      "full_name": "Иван Иванов",
      "first_event": "2025-12-08T09:00:00",
      "last_event": "2025-12-08T18:00:00",
      "hours_worked": 9.0,
      "status": "present"
    }
  ]
}
```

**Статусы:**
- `present` - есть вход и выход
- `absent` - нет событий
- `error` - только одно событие (вход или выход)

## Коды ошибок

### HTTP Status Codes

- `200` - Успешно
- `400` - Ошибка валидации или неправильный запрос
- `404` - Ресурс не найден
- `500` - Внутренняя ошибка сервера

### Формат ошибок

```json
{
  "detail": "Error message"
}
```

## Swagger UI

Интерактивная документация доступна по адресу:
- **Swagger UI:** `http://your-server/docs`
- **ReDoc:** `http://your-server/redoc`

## Примеры использования

### Python

```python
import requests

# Создание пользователя
response = requests.post(
    "http://46.62.223.55/api/users/",
    json={
        "hikvision_id": "1001",
        "full_name": "Иван Иванов",
        "department": "IT"
    }
)
user = response.json()

# Загрузка фото
with open("photo.jpg", "rb") as f:
    response = requests.post(
        f"http://46.62.223.55/api/users/{user['id']}/upload-photo",
        files={"photo": f}
    )

# Синхронизация с терминалом
response = requests.post(
    f"http://46.62.223.55/api/users/{user['id']}/sync-to-device"
)
```

### cURL

```bash
# Создание пользователя
curl -X POST http://46.62.223.55/api/users/ \
  -H "Content-Type: application/json" \
  -d '{
    "hikvision_id": "1001",
    "full_name": "Иван Иванов",
    "department": "IT"
  }'

# Загрузка фото
curl -X POST http://46.62.223.55/api/users/1/upload-photo \
  -F "photo=@photo.jpg"

# Синхронизация
curl -X POST http://46.62.223.55/api/users/1/sync-to-device
```

### JavaScript (Fetch API)

```javascript
// Создание пользователя
const response = await fetch('http://46.62.223.55/api/users/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    hikvision_id: '1001',
    full_name: 'Иван Иванов',
    department: 'IT'
  })
});
const user = await response.json();

// Загрузка фото
const formData = new FormData();
formData.append('photo', photoFile);

const uploadResponse = await fetch(
  `http://46.62.223.55/api/users/${user.id}/upload-photo`,
  {
    method: 'POST',
    body: formData
  }
);

// Синхронизация
const syncResponse = await fetch(
  `http://46.62.223.55/api/users/${user.id}/sync-to-device`,
  {
    method: 'POST'
  }
);
```

## Rate Limiting

В текущей версии rate limiting не реализован. Для production рекомендуется добавить ограничения:
- 100 запросов в минуту на IP
- 10 запросов в секунду на endpoint

## Версионирование

Текущая версия API: **v1**

В будущем версионирование будет через URL: `/api/v1/`, `/api/v2/`

