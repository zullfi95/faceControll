# API Документация

## Обзор

Face Access Control System предоставляет REST API для управления пользователями, устройствами, событиями и отчетами.

**Базовый URL:** `http://your-server/api`

## Аутентификация

### JWT Токены

Большинство эндпоинтов требуют аутентификации с помощью JWT токена.

```http
Authorization: Bearer <your-jwt-token>
```

#### Получение токена
```http
POST /auth/login
Content-Type: application/json

{
    "username": "admin",
    "password": "your_password"
}
```

**Ответ:**
```json
{
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "token_type": "bearer"
}
```

#### Проверка токена
```http
GET /auth/me
Authorization: Bearer <token>
```

## Пользователи

### Создание пользователя
```http
POST /users/
Authorization: Bearer <token>
Content-Type: application/json

{
    "hikvision_id": "001",
    "full_name": "Иванов Иван Иванович",
    "department": "IT",
    "role": "cleaner"
}
```

### Получение пользователей
```http
GET /users/?skip=0&limit=100
Authorization: Bearer <token>
```

### Получение пользователя
```http
GET /users/{user_id}
Authorization: Bearer <token>
```

### Обновление пользователя
```http
PUT /users/{user_id}
Authorization: Bearer <token>
Content-Type: application/json

{
    "full_name": "Новое имя",
    "department": "Новый отдел"
}
```

### Загрузка фото
```http
POST /users/{user_id}/upload-photo
Authorization: Bearer <token>
Content-Type: multipart/form-data

photo: <image-file>
```

### Синхронизация с устройством
```http
POST /users/{user_id}/sync-to-device
Authorization: Bearer <token>
```

## Устройства (Терминалы)

### Добавление устройства
```http
POST /devices/
Authorization: Bearer <token>
Content-Type: application/json

{
    "name": "Терминал Вход",
    "ip_address": "10.0.0.100",
    "username": "admin",
    "password_encrypted": "<encrypted-password>",
    "device_type": "entry"
}
```

### Получение устройств
```http
GET /devices/
Authorization: Bearer <token>
```

### Проверка статуса устройства
```http
GET /devices/{id}/status
Authorization: Bearer <token>
```

## События (Events)

### Вебхук от терминала
```http
POST /events/webhook
X-API-Key: <webhook-api-key>
Content-Type: application/json

{
    "AccessControllerEvent": {
        "employeeNoString": "001",
        "name": "Иванов Иван",
        "eventType": "entry",
        "eventTime": "2024-01-01T09:00:00+04:00"
    }
}
```

### Получение событий
```http
GET /events/?start_date=2024-01-01&end_date=2024-01-01&user_id=1&event_type=entry
Authorization: Bearer <token>
```

## Отчеты

### Дневной отчет
```http
GET /reports/daily?date_str=2024-01-01
Authorization: Bearer <token>
```

**Ответ:**
```json
{
    "date": "2024-01-01",
    "shifts": [
        {
            "shift_name": "Утренняя смена",
            "days": [
                {
                    "day_name": "Понедельник",
                    "employees": [
                        {
                            "user_name": "Иванов Иван",
                            "first_entry_time": "09:05:00",
                            "last_exit_time": "18:30:00",
                            "hours_worked_total": 8.5,
                            "delay_minutes": 5,
                            "status": "present"
                        }
                    ]
                }
            ]
        }
    ]
}
```

### Отчет по сменам
```http
GET /reports/shifts?date_str=2024-01-01
Authorization: Bearer <token>
```

## Системные пользователи

### Создание системного пользователя
```http
POST /system-users/
Authorization: Bearer <token>
Content-Type: application/json

{
    "username": "manager",
    "email": "manager@company.com",
    "password": "secure_password",
    "full_name": "Менеджер",
    "role": "operations_manager"
}
```

### Получение пользователей
```http
GET /system-users/
Authorization: Bearer <token>
```

## Роли и права

### Доступные роли

```http
GET /roles
```

**Ответ:**
```json
{
    "roles": [
        {"value": "cleaner", "display_name": "Уборщик"},
        {"value": "security", "display_name": "Охрана"},
        {"value": "manager", "display_name": "Менеджер"},
        {"value": "operations_manager", "display_name": "Операционный менеджер"}
    ]
}
```

### Права доступа

- **cleaner**: Просмотр своих отчетов
- **security**: Просмотр всех событий и отчетов
- **manager**: Управление пользователями и устройствами
- **operations_manager**: Полный доступ включая системных пользователей

## WebSocket соединения

### События в реальном времени
```javascript
const ws = new WebSocket('ws://your-server/api/ws/events');

// Подключение
ws.onopen = () => {
    ws.send(JSON.stringify({type: 'connected'}));
};

// Получение событий
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('New event:', data);
};
```

### Доступные каналы
- `/ws/events` - Новые события доступа
- `/ws/reports` - Обновления отчетов
- `/ws/dashboard` - Данные главной панели

## Ошибки

### Формат ошибок

```json
{
    "detail": "Описание ошибки",
    "type": "тип_ошибки"
}
```

### Коды HTTP статусов
- `200` - Успех
- `400` - Неверный запрос
- `401` - Не авторизован
- `403` - Доступ запрещен
- `404` - Не найдено
- `500` - Внутренняя ошибка сервера

## Rate Limiting

API имеет ограничения на количество запросов:
- `/events/webhook`: 10 запросов в секунду
- `/api/*`: 30 запросов в секунду

## Безопасность

### Заголовки безопасности
Все ответы включают:
```
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
```

### Валидация входных данных
- Все входные данные валидируются с помощью Pydantic
- SQL injection защита через SQLAlchemy
- XSS защита через escaping

## Мониторинг

### Health Check
```http
GET /health
```

**Ответ:**
```json
{
    "status": "healthy",
    "timestamp": "2024-01-01T12:00:00Z",
    "version": "1.0.0",
    "database": "healthy",
    "system": {
        "cpu_percent": 15.2,
        "memory_percent": 45.8
    }
}
```

### WebSocket соединения
```http
GET /ws/connections
Authorization: Bearer <token>
```

**Ответ:**
```json
{
    "events": 5,
    "reports": 2,
    "dashboard": 1,
    "total": 8
}
```

## SDK и интеграции

### Python клиент
```python
import httpx
import json

class FaceControlClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token
        self.client = httpx.Client(
            headers={"Authorization": f"Bearer {token}"}
        )

    def get_users(self):
        response = self.client.get(f"{self.base_url}/users/")
        return response.json()
```

### JavaScript клиент
```javascript
class FaceControlAPI {
    constructor(baseURL, token) {
        this.baseURL = baseURL;
        this.token = token;
    }

    async getUsers() {
        const response = await fetch(`${this.baseURL}/users/`, {
            headers: {
                'Authorization': `Bearer ${this.token}`,
                'Content-Type': 'application/json'
            }
        });
        return response.json();
    }
}
```
