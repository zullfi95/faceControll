# Справочник API для получения событий с терминала

## Два способа получения событий

### 1. HTTP Listening (Webhook) - РЕКОМЕНДУЕТСЯ ✅

Терминал автоматически отправляет события на сервер через HTTP POST.

**Настройка терминала:**
- Event Alarm IP: `192.168.1.64` (IP вашего сервера)
- URL: `/events/webhook`
- Port: `80`
- Protocol: `http`

**Endpoint:** `POST /events/webhook`

**Формат данных:** MIME multipart с JSON

**Преимущества:**
- ✅ События приходят в реальном времени автоматически
- ✅ Не требует постоянного подключения
- ✅ Надежнее, чем streaming

**Пример события:**
```json
{
  "AccessControllerEvent": {
    "majorEventType": 5,
    "subEventType": 21,
    "employeeNoString": "12345",
    "name": "Иван Иванов",
    "cardNo": "12345678",
    "time": "2025-12-11T17:31:18+04:00"
  }
}
```

### 2. ISAPI Event Search (Polling)

Получение исторических событий через ISAPI.

**Endpoint:** `GET /api/devices/{device_id}/events?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`

**Пробуемые endpoints:**
1. `POST /ISAPI/Event/notification/eventSearch` - стандартный поиск событий
2. `POST /ISAPI/AccessControl/AcsEvent` - поиск событий доступа (если поддерживается)

**Формат запроса AcsEvent:**
```json
{
  "AcsEventCond": {
    "searchID": "uuid",
    "searchResultPosition": 0,
    "maxResults": 100,
    "timeSpanList": {
      "timeSpan": [{
        "startTime": "2025-12-10T00:00:00",
        "endTime": "2025-12-11T23:59:59"
      }]
    }
  }
}
```

### 3. ISAPI Alert Stream (Streaming)

Поток событий в реальном времени через ISAPI.

**Endpoint:** `GET /ISAPI/Event/notification/alertStream`

**Формат:** MIME multipart stream

**Использование:** 
- Подписка через `POST /api/devices/{device_id}/events/subscribe`
- События автоматически сохраняются в БД

## Проверка поддержки

Терминал поддерживает события, если в capabilities есть:
- `isSupportAcsEvent>true` - поддержка событий доступа
- `isSupportAcsEventTotalNum>true` - поддержка подсчета событий

Проверка:
```bash
GET /ISAPI/AccessControl/capabilities
```

## Рекомендации

**Для получения событий в реальном времени:**
1. ✅ Используйте **HTTP Listening (Webhook)** - самый надежный способ
2. Настройте терминал на отправку событий на `/events/webhook`
3. События будут автоматически сохраняться в БД

**Для получения исторических событий:**
1. Используйте `GET /api/devices/{device_id}/events` с указанием периода
2. Или синхронизируйте через `POST /api/devices/{device_id}/sync-events`

## Troubleshooting

### События не приходят через webhook

1. Проверьте настройки HTTP Listening на терминале
2. Проверьте доступность сервера: `ping 192.168.1.64` с терминала
3. Проверьте логи: `docker-compose logs -f backend | grep webhook`

### События не находятся через ISAPI

1. Проверьте пароль устройства (может быть зашифрован другим ключом)
2. Проверьте логи: `docker-compose logs backend | grep "AcsEvent\|eventSearch"`
3. Убедитесь, что терминал поддерживает `isSupportAcsEvent`

