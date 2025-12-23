#!/bin/bash

# Скрипт проверки состояния сервера
# Проверяет установленные компоненты и их версии

echo "=========================================="
echo "Проверка состояния сервера"
echo "=========================================="
echo ""

# Информация о системе
echo "1. Информация о системе:"
echo "   OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)"
echo "   Kernel: $(uname -r)"
echo "   Architecture: $(uname -m)"
echo "   Uptime: $(uptime -p)"
echo "   Load: $(uptime | awk -F'load average:' '{print $2}')"
echo ""

# Проверка Docker
echo "2. Docker:"
if command -v docker &> /dev/null; then
    echo "   ✓ Установлен"
    echo "   Версия: $(docker --version)"
    echo "   Статус: $(systemctl is-active docker 2>/dev/null || echo 'неизвестно')"
    echo "   Контейнеры: $(docker ps -q | wc -l) запущено"
else
    echo "   ✗ Не установлен"
fi
echo ""

# Проверка Docker Compose
echo "3. Docker Compose:"
if command -v docker-compose &> /dev/null; then
    echo "   ✓ Установлен"
    echo "   Версия: $(docker-compose --version)"
elif docker compose version &> /dev/null; then
    echo "   ✓ Установлен (плагин)"
    echo "   Версия: $(docker compose version)"
else
    echo "   ✗ Не установлен"
fi
echo ""

# Проверка WireGuard
echo "4. WireGuard:"
if command -v wg &> /dev/null; then
    echo "   ✓ Установлен"
    echo "   Версия: $(wg --version 2>/dev/null || echo 'установлен')"
    if [ -f /etc/wireguard/wg0.conf ]; then
        echo "   Конфигурация: /etc/wireguard/wg0.conf существует"
        if systemctl is-active --quiet wg-quick@wg0; then
            echo "   Статус: активен"
        else
            echo "   Статус: неактивен"
        fi
    else
        echo "   Конфигурация: не найдена"
    fi
else
    echo "   ✗ Не установлен"
fi
echo ""

# Проверка Git
echo "5. Git:"
if command -v git &> /dev/null; then
    echo "   ✓ Установлен"
    echo "   Версия: $(git --version)"
else
    echo "   ✗ Не установлен"
fi
echo ""

# Проверка директории проекта
echo "6. Директория проекта:"
PROJECT_DIR="/opt/facecontroll"
if [ -d "$PROJECT_DIR" ]; then
    echo "   ✓ Существует: $PROJECT_DIR"
    echo "   Размер: $(du -sh $PROJECT_DIR 2>/dev/null | cut -f1 || echo 'неизвестно')"
    if [ -f "$PROJECT_DIR/docker-compose.yml" ]; then
        echo "   docker-compose.yml: найден"
        if [ -f "$PROJECT_DIR/.env" ]; then
            echo "   .env: найден"
        else
            echo "   .env: не найден"
        fi
    else
        echo "   docker-compose.yml: не найден"
    fi
else
    echo "   ✗ Не существует"
fi
echo ""

# Проверка портов
echo "7. Открытые порты:"
if command -v netstat &> /dev/null; then
    netstat -tuln | grep LISTEN | awk '{print "   " $4}' | sort -u
elif command -v ss &> /dev/null; then
    ss -tuln | grep LISTEN | awk '{print "   " $5}' | sort -u
else
    echo "   Утилиты netstat/ss не найдены"
fi
echo ""

# Проверка firewall
echo "8. Firewall (UFW):"
if command -v ufw &> /dev/null; then
    echo "   ✓ Установлен"
    echo "   Статус: $(ufw status | head -1)"
else
    echo "   ✗ Не установлен"
fi
echo ""

# Проверка Docker контейнеров
echo "9. Docker контейнеры:"
if command -v docker &> /dev/null; then
    if [ -d "$PROJECT_DIR" ] && [ -f "$PROJECT_DIR/docker-compose.yml" ]; then
        cd $PROJECT_DIR 2>/dev/null && docker-compose ps 2>/dev/null || echo "   Контейнеры не запущены"
    else
        echo "   Проект не развернут"
    fi
else
    echo "   Docker не установлен"
fi
echo ""

# Проверка дискового пространства
echo "10. Дисковое пространство:"
df -h / | tail -1 | awk '{print "   Использовано: " $3 " / " $2 " (" $5 ")"}'
echo ""

# Проверка памяти
echo "11. Память:"
free -h | grep Mem | awk '{print "   Использовано: " $3 " / " $2 " (" int($3/$2*100) "%)"}'
if [ -f /swapfile ]; then
    echo "   Swap файл: существует"
    swapon --show | grep swapfile && echo "   Swap: активен" || echo "   Swap: неактивен"
else
    echo "   Swap файл: не найден"
fi
echo ""

# Проверка переменных окружения
echo "12. Переменные окружения:"
if [ -f "$PROJECT_DIR/.env" ]; then
    echo "   .env файл найден"
    echo "   Ключевые переменные:"
    grep -E "^(DATABASE_URL|JWT_SECRET_KEY|ENCRYPTION_KEY|WEBHOOK_API_KEY)=" "$PROJECT_DIR/.env" 2>/dev/null | sed 's/=.*/=***/' | sed 's/^/     /' || echo "     Не найдены"
else
    echo "   .env файл не найден"
fi
echo ""

echo "=========================================="
echo "Проверка завершена"
echo "=========================================="




