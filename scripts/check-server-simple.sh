#!/bin/bash
echo "=== Информация о системе ==="
uname -a
cat /etc/os-release | grep PRETTY_NAME

echo ""
echo "=== Docker ==="
if command -v docker &> /dev/null; then
    docker --version
    systemctl status docker --no-pager | head -3
else
    echo "Docker не установлен"
fi

echo ""
echo "=== Docker Compose ==="
if command -v docker-compose &> /dev/null; then
    docker-compose --version
elif docker compose version &> /dev/null; then
    docker compose version
else
    echo "Docker Compose не установлен"
fi

echo ""
echo "=== WireGuard ==="
if command -v wg &> /dev/null; then
    wg --version 2>/dev/null || echo "WireGuard установлен"
    if [ -f /etc/wireguard/wg0.conf ]; then
        echo "Конфигурация найдена"
    fi
else
    echo "WireGuard не установлен"
fi

echo ""
echo "=== Git ==="
if command -v git &> /dev/null; then
    git --version
else
    echo "Git не установлен"
fi

echo ""
echo "=== Директория проекта ==="
if [ -d /opt/facecontroll ]; then
    ls -la /opt/facecontroll | head -10
    if [ -f /opt/facecontroll/docker-compose.yml ]; then
        echo "docker-compose.yml найден"
    fi
    if [ -f /opt/facecontroll/.env ]; then
        echo ".env найден"
    fi
else
    echo "Директория /opt/facecontroll не существует"
fi

echo ""
echo "=== Docker контейнеры ==="
if command -v docker &> /dev/null; then
    docker ps
else
    echo "Docker не установлен"
fi

echo ""
echo "=== Дисковое пространство ==="
df -h /

echo ""
echo "=== Память ==="
free -h

echo ""
echo "=== Открытые порты ==="
ss -tuln 2>/dev/null | grep LISTEN | head -10 || netstat -tuln 2>/dev/null | grep LISTEN | head -10









