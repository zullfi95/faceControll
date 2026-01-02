# Устранение неисправностей

## Общие проблемы

### Сервер недоступен

**Симптомы:**
- Веб-интерфейс не открывается
- API возвращает 502/503 ошибки

**Решение:**
```bash
# Проверка статуса контейнеров
docker-compose ps

# Просмотр логов
docker-compose logs backend
docker-compose logs frontend

# Перезапуск сервисов
docker-compose restart backend frontend

# Проверка ресурсов
docker stats
```

### База данных недоступна

**Симптомы:**
- Ошибки подключения к БД
- Health check показывает `"database": "unhealthy"`

**Решение:**
```bash
# Проверка статуса PostgreSQL
docker-compose logs db

# Подключение к БД
docker-compose exec db psql -U postgres -d facerecog

# Проверка дискового пространства
df -h

# Перезапуск БД
docker-compose restart db
```

## VPN проблемы

### Терминал не доступен через VPN

**Симптомы:**
- `ping 10.0.0.100` не проходит
- Ошибки синхронизации пользователей

**Диагностика:**
```bash
# Проверка VPN статуса на сервере
sudo wg show

# Проверка логов WireGuard
sudo journalctl -u wg-quick@wg0 -f

# Проверка роутера
# В веб-интерфейсе Keenetic: Интернет → WireGuard
```

**Решения:**
1. **Перезагрузка VPN:**
   ```bash
   sudo systemctl restart wg-quick@wg0
   ```

2. **Проверка ключей:**
   ```bash
   # На сервере
   sudo wg show wg0 peers

   # Сравнить с конфигом роутера
   ```

3. **Перегенерация ключей:**
   ```bash
   cd wireguard
   bash generate-keys.sh
   # Обновить конфиги и перезапустить
   ```

### Проблемы с роутером Keenetic

**Симптомы:**
- VPN туннель не устанавливается
- Нет подключения к серверу

**Решение:**
```
Веб-интерфейс роутера → Система → Диагностика

1. Проверить интернет подключение
2. Перезагрузить роутер
3. Проверить настройки WireGuard:
   - Public Key сервера
   - Endpoint IP:порт
   - Private Key клиента
```

## Проблемы с терминалом Hikvision

### Терминал не отправляет события

**Симптомы:**
- Нет новых событий в системе
- Webhook эндпоинт не получает запросы

**Диагностика:**
```bash
# Проверка VPN
ping 10.0.0.100

# Проверка HTTP Listening настроек
# Веб-интерфейс терминала:
# Configuration → Network → Advanced Settings → HTTP Listening

# Проверка логов терминала
# Maintenance → Log → Access Control
```

**Решения:**
1. **Проверка настроек HTTP Listening:**
   ```
   Event Alarm IP: 10.0.0.1
   URL: /events/webhook
   Port: 8000
   Protocol: HTTP
   ```

2. **Проверка API ключа:**
   ```bash
   # В .env файле
   WEBHOOK_API_KEY=your_key_here
   ```

3. **Тест webhook:**
   ```bash
   curl -X POST http://localhost/api/events/webhook \
     -H "X-API-Key: your_key" \
     -H "Content-Type: application/json" \
     -d '{"test": "data"}'
   ```

### Не удается добавить пользователя

**Симптомы:**
- Ошибка "Connection failed" при синхронизации
- Пользователь не появляется на терминале

**Диагностика:**
```bash
# Проверка подключения к терминалу
curl -u admin:password http://10.0.0.100/ISAPI/System/deviceInfo

# Проверка учетных данных
# В настройках устройства в системе
```

**Решения:**
1. **Проверка IP и учетных данных:**
   ```
   IP Address: 10.0.0.100
   Username: admin
   Password: <правильный пароль>
   ```

2. **Включение ISAPI:**
   ```
   Configuration → Network → Advanced Settings → Integration Protocol
   ISAPI: Enabled
   ```

3. **Проверка качества фото:**
   - Разрешение минимум 200x200
   - Лицо четко видно
   - Достаточное освещение

### Распознавание лиц не работает

**Симптомы:**
- Терминал не распознает лица
- Ложные срабатывания

**Решения:**
```
Configuration → Face Recognition → General Settings
- Recognition Distance: 1-3 метра
- Recognition Angle: ±30°
- Face Quality Threshold: 70%

Configuration → Face Recognition → Capture Settings
- Face Size: 80x80 пикселей минимум
- Pose Angle Tolerance: Enabled
```

## Проблемы с пользователями и отчетами

### Отчеты показывают неправильные часы

**Симптомы:**
- Часы работы рассчитаны неправильно
- Опоздания не учитываются

**Диагностика:**
```bash
# Проверка настроек смен
# Веб-интерфейс → Настройки → Смены

# Проверка событий пользователя
GET /events/?user_id=123&start_date=2024-01-01&end_date=2024-01-01
```

**Решения:**
1. **Проверка расписания смен:**
   ```json
   {
     "0": {
       "start": "09:00",
       "end": "18:00",
       "enabled": true
     }
   }
   ```

2. **Проверка часового пояса:**
   - Система использует Baku timezone (UTC+4)
   - Все события конвертируются в этот часовой пояс

### Пользователь не найден в отчетах

**Симптомы:**
- Сотрудник отмечен как "Прогул"
- Нет событий входа/выхода

**Решения:**
1. **Проверка привязки к смене:**
   ```
   Веб-интерфейс → Сотрудники → [Пользователь] → Смена
   ```

2. **Проверка событий:**
   ```bash
   # Поиск событий по ID пользователя
   GET /events/?user_id=123&start_date=2024-01-01
   ```

## Проблемы с производительностью

### Высокая загрузка CPU

**Симптомы:**
- Сервер тормозит
- Health check показывает высокий CPU usage

**Решения:**
```bash
# Проверка нагрузки
docker stats

# Оптимизация количества воркеров
# В docker-compose.yml для backend:
environment:
  - GUNICORN_WORKERS=2
  - GUNICORN_THREADS=4

# Очистка логов
docker-compose exec backend truncate -s 0 /app/logs/*.log
```

### Замедление базы данных

**Симптомы:**
- Запросы выполняются долго
- API отвечает с задержкой

**Решения:**
```bash
# Проверка индексов
docker-compose exec db psql -U postgres -d facerecog -c "\di"

# Анализ медленных запросов
docker-compose exec db psql -U postgres -d facerecog -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"

# Очистка старых событий (старше 1 года)
DELETE FROM attendance_events WHERE timestamp < NOW() - INTERVAL '1 year';
```

## Безопасность

### Обнаружены подозрительные запросы

**Симптомы:**
- Необычно высокий трафик
- Неизвестные IP в логах

**Решения:**
```bash
# Проверка логов
docker-compose logs nginx | grep -i suspicious

# Блокировка IP
sudo ufw deny from suspicious_ip

# Проверка rate limiting
# В nginx.conf проверить лимиты
```

### Утечка JWT токенов

**Симптомы:**
- Неавторизованный доступ
- Изменения без логина

**Решения:**
1. **Ротация JWT секрета:**
   ```bash
   # Сгенерировать новый секрет
   openssl rand -hex 32

   # Обновить .env
   JWT_SECRET_KEY=new_secret

   # Перезапустить сервисы
   docker-compose restart backend
   ```

2. **Отзыв сессий:**
   ```bash
   # Все пользователи должны перелогиниться
   # Изменить секрет заставит все токены устареть
   ```

## SSH проблемы

### Невозможно подключиться по SSH

**Симптомы:**
- `ssh root@server` не работает
- Connection refused

**Решения (на сервере через консоль Hetzner):**

```bash
# Запуск SSH
systemctl start sshd
systemctl enable sshd

# Проверка статуса
systemctl status sshd

# Разрешение в firewall
ufw allow 22/tcp
ufw reload

# Проверка логов
journalctl -u sshd -f
```

**Локальная диагностика:**
```bash
# Проверка доступности порта
.\scripts\diagnose-ssh-local.ps1

# Проверка DNS
nslookup your-server-ip
```

## Логи и мониторинг

### Сбор логов

```bash
# Все логи
docker-compose logs

# Логи конкретного сервиса
docker-compose logs backend

# Следить за логами в реальном времени
docker-compose logs -f backend

# Логи за последний час
docker-compose logs --since 1h backend
```

### Экспорт логов для анализа

```bash
# Экспорт в файл
docker-compose logs backend > backend_logs.txt

# Фильтрация ошибок
docker-compose logs backend | grep -i error
```

### Мониторинг ресурсов

```bash
# Использование ресурсов
docker stats

# Дисковое пространство
df -h

# Память и CPU
htop  # или top
```

## Восстановление после сбоев

### Восстановление базы данных

```bash
# Бэкап
docker-compose exec db pg_dump -U postgres facerecog > backup.sql

# Восстановление
docker-compose exec -T db psql -U postgres facerecog < backup.sql
```

### Полный перезапуск системы

```bash
# Остановка
docker-compose down

# Очистка (осторожно!)
docker system prune -a

# Запуск
docker-compose up -d

# Инициализация
docker-compose exec backend python run_migration.py --init
```

## Контакты поддержки

Если проблема не решена:
1. Соберите логи: `docker-compose logs > debug_logs.txt`
2. Опишите шаги воспроизведения
3. Укажите версию системы и конфигурацию
4. Создайте issue в репозитории с собранной информацией
