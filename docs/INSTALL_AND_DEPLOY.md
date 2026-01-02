# Установка и Развертывание

## Быстрый старт

### 1. Клонирование и инициализация

```bash
# Клонирование репозитория
git clone <repo-url>
cd face-access-control

# Генерация ключей и создание .env
bash scripts/init-local.sh
```

### 2. Локальная разработка

```bash
# Запуск всех сервисов
docker-compose up -d

# Проверка логов
docker-compose logs -f

# Открыть в браузере
http://localhost
```

### 3. Развертывание на сервере

#### Требования к серверу
- Ubuntu 22.04 или новее
- 2+ CPU cores, 4GB+ RAM, 20GB+ SSD
- Docker & Docker Compose
- WireGuard VPN

#### Автоматическое развертывание
```bash
bash scripts/deploy.sh
```

#### Ручное развертывание
```bash
# Копирование файлов на сервер
scp -r . root@your-server:/opt/face-control/

# На сервере
cd /opt/face-control
docker-compose up -d
```

## Конфигурация

### Переменные окружения

Создайте файл `.env` на основе `env.template`:

```bash
# База данных
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=facerecog

# Backend
WEBHOOK_API_KEY=your_webhook_api_key
JWT_SECRET_KEY=your_jwt_secret_key
ENCRYPTION_KEY=your_encryption_key

# Hikvision
TERMINAL_IN_IP=10.0.0.100

# Опционально
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Генерация ключей

```bash
# JWT секрет (32 символа)
openssl rand -hex 32

# Ключ шифрования
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Webhook API ключ
openssl rand -hex 16
```

## Docker Compose

### Структура сервисов

```yaml
services:
  db:           # PostgreSQL база данных
  backend:      # FastAPI приложение
  frontend:     # React SPA
```

### Профили запуска

```bash
# Только backend для разработки
docker-compose --profile backend up

# Полная система
docker-compose up
```

## Миграции базы данных

### Инициализация (новые установки)

```bash
cd backend
python run_migration.py --init
```

### Обновление (существующие установки)

```bash
cd backend
python run_migration.py
```

## Проверка здоровья

```bash
# Health check endpoint
curl http://localhost/api/health

# Статус миграций
cd backend && python run_migration.py --check
```

## Тестирование

```bash
# Запуск тестов
cd backend && pytest

# С покрытием
pytest --cov=app --cov-report=html
```
