#!/bin/bash

# Скрипт инициализации проекта на локальной машине
# Генерирует ключи, создает .env файл

set -e

echo "=== Инициализация проекта Face Access Control ==="
echo ""

# Проверка наличия необходимых утилит
echo "Проверка зависимостей..."

if ! command -v openssl &> /dev/null; then
    echo "Ошибка: openssl не установлен!"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "Ошибка: python3 не установлен!"
    exit 1
fi

echo "✓ Все зависимости установлены"
echo ""

# Создание .env файла
if [ -f ".env" ]; then
    echo "⚠️  Файл .env уже существует. Пропускаем..."
else
    echo "Создание .env файла из шаблона..."
    cp env.template .env
    
    # Генерация WEBHOOK_API_KEY
    echo "Генерация WEBHOOK_API_KEY..."
    WEBHOOK_KEY=$(openssl rand -hex 32)
    sed -i.bak "s/your_webhook_api_key_here/$WEBHOOK_KEY/" .env
    
    # Генерация ENCRYPTION_KEY
    echo "Генерация ENCRYPTION_KEY..."
    ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    sed -i.bak "s|your_encryption_key_here|$ENCRYPTION_KEY|" .env
    
    # Генерация случайного пароля для БД
    echo "Генерация пароля для PostgreSQL..."
    DB_PASSWORD=$(openssl rand -base64 16)
    sed -i.bak "s/your_secure_password_here/$DB_PASSWORD/" .env
    
    rm .env.bak 2>/dev/null || true
    
    echo "✓ Файл .env создан"
fi

echo ""
echo "════════════════════════════════════════════"
echo "ИНИЦИАЛИЗАЦИЯ ЗАВЕРШЕНА"
echo "════════════════════════════════════════════"
echo ""
echo "Следующие шаги:"
echo ""
echo "1. ЛОКАЛЬНАЯ РАЗРАБОТКА:"
echo "   docker-compose up -d"
echo "   Откройте http://localhost в браузере"
echo ""
echo "2. ГЕНЕРАЦИЯ VPN КЛЮЧЕЙ:"
echo "   cd wireguard"
echo "   bash generate-keys.sh"
echo ""
echo "3. РАЗВЕРТЫВАНИЕ НА СЕРВЕРЕ:"
echo "   bash scripts/deploy.sh"
echo ""
echo "⚠️  ВАЖНО: Проверьте файл .env и настройте переменные под вашу среду!"
echo ""

