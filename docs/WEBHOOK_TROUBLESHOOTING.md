# Диагностика проблем с Webhook

## Проблема: События не приходят с терминала

### Шаг 1: Проверка настроек на терминале

1. Зайдите в веб-интерфейс терминала
2. Перейдите в **Configuration → Network → HTTP Listening**
3. Проверьте настройки:
   - **Event Alarm IP/Domain Name:** `192.168.1.64`
   - **URL:** `/events/webhook`
   - **Port:** `80`
   - **Protocol:** `HTTP`
   - **HTTP Listening должен быть ВКЛЮЧЕН**

### Шаг 2: Проверка доступности сервера

Выполните с терминала или с компьютера в той же сети:

```bash
# Проверка доступности сервера
ping 192.168.1.64

# Проверка порта
telnet 192.168.1.64 80

# Тестовый запрос к webhook
curl -X POST http://192.168.1.64:80/events/webhook \
     -H 'Content-Type: application/json' \
     -d '{"test":"data"}'
```

Если запросы не проходят:
- Проверьте firewall на сервере
- Проверьте, что порт 80 открыт
- Проверьте маршрутизацию между терминалом и сервером

### Шаг 3: Проверка логов в реальном времени

Откройте терминал и выполните:

```bash
# Windows PowerShell
docker-compose logs -f backend | Select-String -Pattern "WEBHOOK"

# Linux/Mac
docker-compose logs -f backend | grep WEBHOOK
```

Затем выполните авторизацию на терминале (приложите карту или используйте распознавание лица).

### Шаг 4: Проверка генерации событий на терминале

1. Убедитесь, что пользователь существует на терминале
2. Выполните авторизацию на терминале
3. Проверьте логи терминала (если доступны)

### Шаг 5: Тестирование webhook endpoint

Выполните тестовый запрос с компьютера в той же сети:

```bash
curl -X POST http://192.168.1.64:80/events/webhook \
     -H 'Content-Type: application/json' \
     -d '{"test":"event"}'
```

Затем проверьте логи:

```bash
docker-compose logs --tail=50 backend | Select-String -Pattern "WEBHOOK"
```

Должны увидеть запись `[WEBHOOK] ===== NEW WEBHOOK REQUEST =====`

### Шаг 6: Проверка через скрипт диагностики

```bash
docker-compose exec backend python /app/scripts/diagnose_webhook.py
```

## Частые проблемы

### Проблема 1: Терминал не может достучаться до сервера

**Решение:**
- Проверьте firewall на сервере
- Убедитесь, что порт 80 открыт
- Проверьте, что сервер доступен по IP 192.168.1.64

### Проблема 2: HTTP Listening не включен

**Решение:**
- Зайдите в веб-интерфейс терминала
- Configuration → Network → HTTP Listening
- Убедитесь, что HTTP Listening **ВКЛЮЧЕН**

### Проблема 3: События не генерируются

**Решение:**
- Убедитесь, что пользователь существует на терминале
- Выполните авторизацию на терминале
- Проверьте настройки событий на терминале

### Проблема 4: Неправильный URL

**Решение:**
- URL должен быть точно: `/events/webhook` (с начальным слэшем, без завершающего)
- Проверьте настройки на терминале

## Мониторинг в реальном времени

Для постоянного мониторинга входящих событий:

```bash
# Windows PowerShell
docker-compose logs -f backend | Select-String -Pattern "WEBHOOK"

# Linux/Mac  
docker-compose logs -f backend | grep WEBHOOK
```

## Проверка через API

```bash
# Получить последние логи webhook
curl http://localhost/api/debug/logs?prefix=WEBHOOK

# Проверить статус webhook на терминале
curl http://localhost/api/devices/1/webhook/status
```

