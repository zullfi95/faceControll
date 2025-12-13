# Автоматическая настройка HTTP Listening (Webhook)

## Обзор

Система поддерживает автоматическую настройку HTTP Listening на терминалах Hikvision через ISAPI API. Это позволяет настроить отправку событий на сервер без необходимости ручной настройки через веб-интерфейс терминала.

## API Endpoints

### 1. Получение статуса настройки Webhook

**Endpoint:** `GET /api/devices/{device_id}/webhook/status`

**Описание:** Получает текущие настройки HTTP Listening на терминале.

**Пример запроса:**
```bash
curl -X GET http://localhost/api/devices/1/webhook/status
```

**Пример ответа (успех):**
```json
{
  "success": true,
  "device_id": 1,
  "device_name": "Terminal 1",
  "device_ip": "192.168.1.67",
  "http_hosts": {
    "HttpHostNotification": {
      "httpHostList": {
        "httpHost": [
          {
            "id": 1,
            "protocol": "http",
            "ipAddress": "192.168.1.64",
            "portNo": 80,
            "url": "/events/webhook"
          }
        ]
      }
    }
  },
  "requires_manual_setup": false
}
```

**Пример ответа (endpoint не поддерживается):**
```json
{
  "success": false,
  "device_id": 1,
  "device_name": "Terminal 1",
  "device_ip": "192.168.1.67",
  "requires_manual_setup": true,
  "error": "HTTP hosts endpoint not supported"
}
```

### 2. Настройка Webhook

**Endpoint:** `POST /api/devices/{device_id}/webhook/configure`

**Описание:** Настраивает HTTP Listening на терминале для отправки событий на сервер.

**Параметры запроса (query parameters):**
- `server_ip` (опционально) - IP адрес сервера. Если не указан, используется `SERVER_IP` из переменных окружения или определяется автоматически.
- `server_port` (опционально, по умолчанию 80) - Порт сервера
- `url_path` (опционально, по умолчанию `/events/webhook`) - Путь на сервере
- `protocol` (опционально, по умолчанию `http`) - Протокол (`http` или `https`)

**Пример запроса:**
```bash
curl -X POST "http://localhost/api/devices/1/webhook/configure?server_ip=192.168.1.64&server_port=80&url_path=/events/webhook&protocol=http"
```

**Пример ответа (успех):**
```json
{
  "success": true,
  "device_id": 1,
  "device_name": "Terminal 1",
  "message": "HTTP host configured successfully",
  "configuration": {
    "server_ip": "192.168.1.64",
    "server_port": 80,
    "url_path": "/events/webhook",
    "protocol": "http",
    "full_url": "http://192.168.1.64:80/events/webhook"
  },
  "requires_manual_setup": false
}
```

**Пример ответа (требуется ручная настройка):**
```json
{
  "success": false,
  "device_id": 1,
  "device_name": "Terminal 1",
  "message": "HTTP hosts endpoint not supported by this device",
  "configuration": {
    "server_ip": "192.168.1.64",
    "server_port": 80,
    "url_path": "/events/webhook",
    "protocol": "http",
    "full_url": "http://192.168.1.64:80/events/webhook"
  },
  "requires_manual_setup": true,
  "manual_setup_instructions": {
    "step": "Configure HTTP Listening manually in terminal web interface",
    "path": "Configuration → Network → HTTP Listening",
    "settings": {
      "Event Alarm IP/Domain Name": "192.168.1.64",
      "URL": "/events/webhook",
      "Port": "80",
      "Protocol": "http"
    }
  },
  "error": "HTTP hosts endpoint not supported by this device"
}
```

## Использование

### Автоматическая настройка через API

1. **Проверьте текущий статус:**
   ```bash
   GET /api/devices/1/webhook/status
   ```

2. **Настройте webhook:**
   ```bash
   POST /api/devices/1/webhook/configure?server_ip=192.168.1.64
   ```

3. **Проверьте результат:**
   ```bash
   GET /api/devices/1/webhook/status
   ```

### Ручная настройка (если автоматическая не поддерживается)

Если терминал не поддерживает настройку через ISAPI (endpoint `/ISAPI/Event/notification/httpHosts` возвращает 404), необходимо настроить вручную:

1. Откройте веб-интерфейс терминала
2. Перейдите в **Configuration → Network → HTTP Listening**
3. Настройте параметры согласно инструкциям в ответе API:
   - **Event Alarm IP/Domain Name:** IP адрес сервера
   - **URL:** `/events/webhook`
   - **Port:** `80` (или другой порт)
   - **Protocol:** `http` (или `https`)
4. Сохраните настройки

## Переменные окружения

Для автоматического определения IP сервера можно использовать переменные окружения:

```bash
# IP адрес сервера (используется если server_ip не указан в запросе)
SERVER_IP=192.168.1.64

# IP адрес терминала в VPN сети (используется для определения IP сервера в VPN)
TERMINAL_IN_IP=10.0.0.100
```

## Проверка работы

После настройки webhook:

1. **Сделайте авторизацию на терминале** (приложите карту, распознавание лица и т.д.)

2. **Проверьте логи backend:**
   ```bash
   docker-compose logs -f backend | grep "\[WEBHOOK\]"
   ```

3. **Проверьте события в БД:**
   ```bash
   docker-compose exec db psql -U postgres -d facerecog -c "SELECT * FROM attendance_events ORDER BY timestamp DESC LIMIT 5;"
   ```

## Troubleshooting

### Endpoint не поддерживается (404)

**Проблема:** Терминал возвращает 404 при попытке настроить через ISAPI.

**Решение:** Используйте ручную настройку через веб-интерфейс терминала. Инструкции будут предоставлены в ответе API.

### События не приходят после настройки

1. **Проверьте настройки на терминале:**
   - Убедитесь, что HTTP Listening включен
   - Проверьте правильность IP адреса, порта и URL

2. **Проверьте сетевую доступность:**
   ```bash
   # С терминала (если есть доступ)
   ping 192.168.1.64
   ```

3. **Проверьте логи backend:**
   ```bash
   docker-compose logs -f backend | grep webhook
   ```

4. **Проверьте, что nginx проксирует запросы:**
   - Убедитесь, что `/events/webhook` проксируется на backend
   - Проверьте конфигурацию nginx

### Ошибка аутентификации

**Проблема:** Ошибка при попытке настроить webhook (401, 403).

**Решение:**
1. Проверьте правильность логина и пароля устройства
2. Убедитесь, что пользователь имеет права на изменение настроек
3. Проверьте, что пароль устройства правильно расшифровывается (см. `docs/FIX_DEVICE_PASSWORD.md`)

## Примечания

- Не все модели терминалов Hikvision поддерживают настройку HTTP Listening через ISAPI
- Если автоматическая настройка не работает, используйте ручную настройку через веб-интерфейс
- После настройки события должны приходить в реальном времени на endpoint `/events/webhook`
- События сохраняются в БД автоматически при получении через webhook

