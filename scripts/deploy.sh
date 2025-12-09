#!/bin/bash

# Скрипт развертывания проекта на сервере Hetzner
# Использование: bash scripts/deploy.sh

set -e

# Переменные
SERVER_IP="46.62.223.55"
SERVER_USER="root"
PROJECT_NAME="face-access-control"
DEPLOY_DIR="/opt/$PROJECT_NAME"

echo "=== Развертывание Face Access Control на $SERVER_IP ==="
echo ""

# Проверка .env файла
if [ ! -f ".env" ]; then
    echo "Ошибка: Файл .env не найден!"
    echo "Запустите сначала: bash scripts/init-local.sh"
    exit 1
fi

echo "1. Проверка подключения к серверу..."
if ! ssh -o ConnectTimeout=5 $SERVER_USER@$SERVER_IP "echo 'OK'" &> /dev/null; then
    echo "Ошибка: Не удается подключиться к серверу $SERVER_IP"
    echo "Проверьте SSH ключи и доступность сервера"
    exit 1
fi
echo "✓ Подключение установлено"
echo ""

echo "2. Установка зависимостей на сервере..."
ssh $SERVER_USER@$SERVER_IP << 'ENDSSH'
    # Обновление системы
    apt-get update
    
    # Установка Docker
    if ! command -v docker &> /dev/null; then
        echo "Установка Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        rm get-docker.sh
    fi
    
    # Установка Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        echo "Установка Docker Compose..."
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
    fi
    
    # Установка WireGuard
    if ! command -v wg &> /dev/null; then
        echo "Установка WireGuard..."
        apt-get install -y wireguard
    fi
    
    # Установка Git
    if ! command -v git &> /dev/null; then
        echo "Установка Git..."
        apt-get install -y git
    fi
    
    echo "✓ Все зависимости установлены"
ENDSSH

echo ""
echo "3. Создание директории проекта..."
ssh $SERVER_USER@$SERVER_IP "mkdir -p $DEPLOY_DIR"
echo "✓ Директория создана: $DEPLOY_DIR"
echo ""

echo "4. Копирование файлов на сервер..."
# Исключаем ненужные файлы
rsync -avz --exclude 'node_modules' \
           --exclude '__pycache__' \
           --exclude '.git' \
           --exclude 'uploads' \
           --exclude '.env' \
           --exclude '*.pyc' \
           ./ $SERVER_USER@$SERVER_IP:$DEPLOY_DIR/

echo "✓ Файлы скопированы"
echo ""

echo "5. Копирование .env файла..."
scp .env $SERVER_USER@$SERVER_IP:$DEPLOY_DIR/.env
echo "✓ Файл .env скопирован"
echo ""

echo "6. Запуск Docker Compose на сервере..."
ssh $SERVER_USER@$SERVER_IP << ENDSSH
    cd $DEPLOY_DIR
    
    # Остановка старых контейнеров (если есть)
    docker-compose down || true
    
    # Запуск новых контейнеров
    docker-compose up -d --build
    
    echo "✓ Контейнеры запущены"
    
    # Проверка статуса
    echo ""
    echo "Статус контейнеров:"
    docker-compose ps
ENDSSH

echo ""
echo "════════════════════════════════════════════"
echo "РАЗВЕРТЫВАНИЕ ЗАВЕРШЕНО"
echo "════════════════════════════════════════════"
echo ""
echo "Проект развернут на: http://$SERVER_IP"
echo ""
echo "Следующие шаги:"
echo ""
echo "1. НАСТРОЙКА WIREGUARD VPN:"
echo "   cd wireguard"
echo "   bash generate-keys.sh"
echo "   scp wg0-server.conf $SERVER_USER@$SERVER_IP:/etc/wireguard/wg0.conf"
echo "   ssh $SERVER_USER@$SERVER_IP 'systemctl enable wg-quick@wg0 && systemctl start wg-quick@wg0'"
echo ""
echo "2. НАСТРОЙКА KEENETIC ROUTER:"
echo "   - Импортируйте файл wireguard/wg0-client.conf"
echo "   - Проверьте подключение: ping 10.0.0.1"
echo ""
echo "3. НАСТРОЙКА ТЕРМИНАЛА DS-K1T343EFWX:"
echo "   - Event Alarm IP: 10.0.0.1"
echo "   - URL: /events/webhook"
echo "   - Port: 8000"
echo "   - В заголовке X-API-Key укажите значение WEBHOOK_API_KEY из .env"
echo ""
echo "4. ДОБАВЛЕНИЕ УСТРОЙСТВА В ВЕБ-ИНТЕРФЕЙСЕ:"
echo "   - Откройте http://$SERVER_IP/settings"
echo "   - Добавьте устройство с IP 10.0.0.100 (IP терминала в VPN)"
echo ""
echo "Логи: ssh $SERVER_USER@$SERVER_IP 'cd $DEPLOY_DIR && docker-compose logs -f'"
echo ""

