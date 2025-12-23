#!/bin/bash

# Скрипт первоначальной настройки сервера для деплоя FaceControll
# Использование: ssh root@46.62.223.55 'bash -s' < scripts/setup-server.sh
# Или: скопировать на сервер и выполнить локально

set -e

echo "=========================================="
echo "Настройка сервера для FaceControll"
echo "=========================================="
echo ""

# Обновление системы
echo "1. Обновление системы..."
apt-get update
apt-get upgrade -y
echo "✓ Система обновлена"
echo ""

# Установка Docker
echo "2. Установка Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    systemctl enable docker
    systemctl start docker
    echo "✓ Docker установлен"
else
    echo "✓ Docker уже установлен"
fi
echo ""

# Установка Docker Compose
echo "3. Установка Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
    curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "✓ Docker Compose установлен"
else
    echo "✓ Docker Compose уже установлен"
fi
echo ""

# Установка WireGuard
echo "4. Установка WireGuard..."
if ! command -v wg &> /dev/null; then
    apt-get install -y wireguard wireguard-tools
    echo "✓ WireGuard установлен"
else
    echo "✓ WireGuard уже установлен"
fi
echo ""

# Установка Git
echo "5. Установка Git..."
if ! command -v git &> /dev/null; then
    apt-get install -y git
    echo "✓ Git установлен"
else
    echo "✓ Git уже установлен"
fi
echo ""

# Установка дополнительных утилит
echo "6. Установка дополнительных утилит..."
apt-get install -y curl wget vim htop ufw
echo "✓ Утилиты установлены"
echo ""

# Настройка firewall
echo "7. Настройка firewall..."
ufw --force enable
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 51820/udp # WireGuard
echo "✓ Firewall настроен"
echo ""

# Создание директории проекта
echo "8. Создание директории проекта..."
PROJECT_DIR="/opt/facecontroll"
mkdir -p $PROJECT_DIR
chmod 755 $PROJECT_DIR
echo "✓ Директория создана: $PROJECT_DIR"
echo ""

# Настройка swap (если нужно)
echo "9. Проверка swap..."
if [ -z "$(swapon --show)" ]; then
    echo "Создание swap файла 2GB..."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' | tee -a /etc/fstab
    echo "✓ Swap создан"
else
    echo "✓ Swap уже настроен"
fi
echo ""

# Оптимизация системы
echo "10. Оптимизация системы..."
# Увеличение лимитов для Docker
cat >> /etc/sysctl.conf << EOF

# Docker optimizations
vm.max_map_count=262144
fs.file-max=2097152
EOF
sysctl -p
echo "✓ Система оптимизирована"
echo ""

echo "=========================================="
echo "Настройка сервера завершена!"
echo "=========================================="
echo ""
echo "Следующие шаги:"
echo ""
echo "1. Скопируйте проект на сервер:"
echo "   rsync -avz --exclude 'node_modules' --exclude '__pycache__' --exclude '.git' ./ root@46.62.223.55:/opt/facecontroll/"
echo ""
echo "2. Скопируйте .env файл:"
echo "   scp .env root@46.62.223.55:/opt/facecontroll/.env"
echo ""
echo "3. Запустите проект:"
echo "   ssh root@46.62.223.55 'cd /opt/facecontroll && docker-compose up -d'"
echo ""
echo "4. Проверьте статус:"
echo "   ssh root@46.62.223.55 'cd /opt/facecontroll && docker-compose ps'"
echo ""




