# Операции и Безопасность

## Операционное управление

### Мониторинг системы

#### Health Checks

Система предоставляет несколько эндпоинтов для мониторинга:

```bash
# Общий health check
curl http://your-server/api/health

# WebSocket соединения
curl -H "Authorization: Bearer <token>" http://your-server/api/ws/connections

# Статус миграций
cd backend && python run_migration.py --check
```

#### Метрики для отслеживания

**Системные метрики:**
- CPU usage (< 80%)
- Memory usage (< 85%)
- Disk space (> 10% free)
- Database connections (< 50 активных)

**Бизнес метрики:**
- Количество активных пользователей
- Среднее время обработки событий (< 100ms)
- Успешность синхронизации с терминалами (> 95%)
- Количество WebSocket соединений

### Резервное копирование

#### Автоматическое бэкапирование

```bash
#!/bin/bash
# daily_backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/backups"

# Бэкап базы данных
docker-compose exec db pg_dump -U postgres facerecog > $BACKUP_DIR/db_$DATE.sql

# Бэкап конфигураций
cp .env $BACKUP_DIR/env_$DATE.backup
cp docker-compose.yml $BACKUP_DIR/compose_$DATE.yml

# Бэкап загруженных файлов
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz uploads/

# Удаление старых бэкапов (старше 30 дней)
find $BACKUP_DIR -name "*.sql" -mtime +30 -delete
find $BACKUP_DIR -name "*.backup" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
```

#### Восстановление из бэкапа

```bash
# Остановка сервисов
docker-compose down

# Восстановление БД
docker-compose exec -T db psql -U postgres facerecog < backup.sql

# Восстановление файлов
tar -xzf uploads_backup.tar.gz

# Запуск сервисов
docker-compose up -d
```

### Логирование

#### Уровни логирования

```
DEBUG: Детальная отладочная информация
INFO: Общая информация о работе
WARNING: Предупреждения о потенциальных проблемах
ERROR: Ошибки выполнения
CRITICAL: Критические ошибки требующие внимания
```

#### Структурированные логи

Логи выводятся в JSON формате для удобного парсинга:

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "INFO",
  "logger": "app.main",
  "message": "User login successful",
  "request_id": "123e4567-e89b-12d3-a456-426614174000",
  "user_id": 123
}
```

#### Ротация логов

```bash
# В docker-compose.yml добавить
backend:
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"
```

### Обновление системы

#### Процесс обновления

1. **Создание бэкапа:**
   ```bash
   ./scripts/backup.sh
   ```

2. **Обновление кода:**
   ```bash
   git pull origin main
   ```

3. **Обновление зависимостей:**
   ```bash
   docker-compose build --no-cache backend frontend
   ```

4. **Миграции БД:**
   ```bash
   docker-compose run --rm backend python run_migration.py
   ```

5. **Перезапуск сервисов:**
   ```bash
   docker-compose up -d
   ```

6. **Проверка работоспособности:**
   ```bash
   curl http://your-server/api/health
   ```

#### Rollback при проблемах

```bash
# Откат кода
git checkout previous_commit

# Восстановление из бэкапа
./scripts/restore.sh backup_file.sql

# Перезапуск
docker-compose up -d
```

## Безопасность

### Аутентификация и авторизация

#### JWT токены

- **Алгоритм:** HS256
- **Срок жизни:** 30 дней
- **Обновление:** Автоматическое при активном использовании

#### Роли пользователей

| Роль | Права |
|------|-------|
| cleaner | Просмотр личных отчетов |
| security | Просмотр всех событий и отчетов |
| manager | Управление пользователями и устройствами |
| operations_manager | Полный доступ |

### Шифрование данных

#### В БД
- Пароли устройств: Fernet шифрование
- JWT секреты: HS256
- API ключи: SHA256 хэширование

#### В транзите
- HTTPS для всех внешних соединений
- VPN для связи с терминалами
- Digest аутентификация для Hikvision API

### Защита от атак

#### Rate Limiting

```nginx
# В nginx.conf
limit_req_zone $binary_remote_addr zone=events:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;

location /api/events/webhook {
    limit_req zone=events burst=20 nodelay;
}

location /api/ {
    limit_req zone=api burst=60 nodelay;
}
```

#### Защита от распространенных уязвимостей

- **SQL Injection:** Параметризованные запросы через SQLAlchemy
- **XSS:** Автоматическое escaping в шаблонах
- **CSRF:** JWT токены вместо сессий
- **Clickjacking:** X-Frame-Options headers

### Аудит и compliance

#### Логи аудита

Все важные действия логируются:

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "action": "user_login",
  "user_id": 123,
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "success": true
}
```

#### Аудит событий доступа

- Входы/выходы фиксируются с фото (опционально)
- Все изменения пользователей/устройств логируются
- Экспорт логов для compliance

### Мониторинг безопасности

#### SIEM интеграция

Логи можно отправлять в SIEM системы через:

```python
# В logging конфигурации
import logging.handlers

# Syslog handler для SIEM
syslog_handler = logging.handlers.SysLogHandler(
    address=('siem-server', 514),
    facility=logging.handlers.SysLogHandler.LOG_USER
)
```

#### Алерты безопасности

Настройка алертов на:
- Неудачные попытки входа (> 5 за 5 минут)
- Доступ из неизвестных IP
- Изменения критических настроек
- Сбои в VPN соединении

## Производительность

### Оптимизация базы данных

#### Индексы

```sql
-- Основные индексы (уже созданы)
CREATE INDEX ix_attendance_events_timestamp ON attendance_events(timestamp);
CREATE INDEX ix_attendance_events_user_id ON attendance_events(user_id);
CREATE INDEX ix_users_hikvision_id ON users(hikvision_id);

-- Дополнительные индексы для отчетов
CREATE INDEX ix_attendance_events_terminal_ip ON attendance_events(terminal_ip);
CREATE INDEX ix_attendance_events_event_type ON attendance_events(event_type);
```

#### Partitioning

Для больших объемов данных:

```sql
-- Партиционирование по месяцам
CREATE TABLE attendance_events_y2024m01 PARTITION OF attendance_events
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

### Кэширование

#### Redis для сессий (опционально)

```python
# В requirements.txt добавить
redis==4.5.0

# В docker-compose.yml
redis:
  image: redis:7-alpine
  networks:
    - app-network
```

### Масштабирование

#### Горизонтальное масштабирование

```yaml
# В docker-compose.yml
backend:
  deploy:
    replicas: 3
    resources:
      limits:
        cpus: '1.0'
        memory: 1G
```

#### Балансировка нагрузки

```nginx
# В nginx.conf
upstream backend {
    server backend1:8000;
    server backend2:8000;
    server backend3:8000;
}

location /api/ {
    proxy_pass http://backend;
}
```

## Аварийное восстановление

### Disaster Recovery Plan

#### RTO/RPO цели
- **RTO (Recovery Time Objective):** 4 часа
- **RPO (Recovery Point Objective):** 1 час

#### Процедура восстановления

1. **Оценка ущерба**
   - Определить scope проблемы
   - Связаться с командой

2. **Восстановление данных**
   ```bash
   ./scripts/restore.sh latest_backup.sql
   ```

3. **Восстановление сервисов**
   ```bash
   docker-compose up -d
   ```

4. **Тестирование**
   ```bash
   ./scripts/health_check.sh
   ```

### Георезервирование

#### Multi-region setup

```yaml
# Primary region (Europe)
version: '3.8'
services:
  db-primary:
    image: postgres:15
    environment:
      - POSTGRES_DB=facerecog

  db-replica:
    image: postgres:15
    environment:
      - POSTGRES_DB=facerecog

# Secondary region (Asia)
services:
  db-secondary:
    # Аналогичная конфигурация
```

## Соответствие требованиям

### GDPR Compliance

#### Обработка персональных данных

- Фото лиц: Шифрование в хранилище
- Логи доступа: Анонимизация через 90 дней
- Право на удаление: API для удаления данных пользователя

#### Data Processing Agreement

```json
{
  "data_controller": "Company Name",
  "processing_purpose": "Access control and time tracking",
  "data_retention": "3 years",
  "legal_basis": "Legitimate interest"
}
```

### SOX Compliance

#### Аудит доступа

- Все изменения конфигурации логируются
- Неизменяемые логи аудита
- Регулярные проверки доступа

#### Change Management

- Одобрение изменений через pull requests
- Автоматическое тестирование
- Rollback capability

## Контакты и эскалация

### Команда поддержки

- **DevOps:** devops@company.com
- **Security:** security@company.com
- **Business:** support@company.com

### Эскалационные процедуры

1. **Уровень 1:** Локальная команда (15 минут)
2. **Уровень 2:** DevOps команда (1 час)
3. **Уровень 3:** Вендоры/поставщики (4 часа)

### Дежурство

- **Основное:** Пн-Пт 9:00-18:00
- **Расширенное:** Пн-Вс 8:00-20:00
- **Критическое:** 24/7
