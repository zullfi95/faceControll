#!/bin/bash

# Скрипт развертывания проекта на сервере
# ВАЖНО: Этот скрипт требует ручного развертывания
# Все SSH команды удалены из-за проблем с подключением

set -e

# Переменные
PROJECT_NAME="face-access-control"
DEPLOY_DIR="/opt/$PROJECT_NAME"

echo "=== Инструкции по развертыванию Face Access Control ==="
echo ""
echo "ВНИМАНИЕ: Автоматическое развертывание через SSH отключено."
echo "Выполните следующие шаги вручную на сервере:"
echo ""

echo "1. ПОДГОТОВКА СЕРВЕРА:"
echo "   - Убедитесь, что на сервере установлены:"
echo "     * Docker и Docker Compose"
echo "     * Git"
echo "     * WireGuard (опционально)"
echo ""

echo "2. КОПИРОВАНИЕ ПРОЕКТА:"
echo "   - Скопируйте проект на сервер в директорию: $DEPLOY_DIR"
echo "   - Убедитесь, что файл .env создан и настроен"
echo ""

echo "3. ЗАПУСК ПРОЕКТА:"
echo "   - На сервере выполните:"
echo "     cd $DEPLOY_DIR"
echo "     docker-compose down || true"
echo "     docker-compose up -d --build"
echo ""

echo "4. ПРОВЕРКА СТАТУСА:"
echo "   - Проверьте контейнеры: docker-compose ps"
echo "   - Проверьте логи: docker-compose logs -f"
echo ""

echo "5. НАСТРОЙКА WIREGUARD VPN:"
echo "   - Сгенерируйте ключи: cd wireguard && bash generate-keys.sh"
echo "   - Скопируйте wg0-server.conf на сервер в /etc/wireguard/wg0.conf"
echo "   - Запустите WireGuard: systemctl enable wg-quick@wg0 && systemctl start wg-quick@wg0"
echo ""

echo "6. НАСТРОЙКА KEENETIC ROUTER:"
echo "   - Импортируйте файл wireguard/wg0-client.conf"
echo "   - Проверьте подключение: ping 10.0.0.1"
echo ""

echo "7. НАСТРОЙКА ТЕРМИНАЛА DS-K1T343EFWX:"
echo "   - Event Alarm IP: 10.0.0.1"
echo "   - URL: /events/webhook"
echo "   - Port: 8000"
echo "   - В заголовке X-API-Key укажите значение WEBHOOK_API_KEY из .env"
echo ""

echo "8. ДОБАВЛЕНИЕ УСТРОЙСТВА В ВЕБ-ИНТЕРФЕЙСЕ:"
echo "   - Откройте веб-интерфейс проекта"
echo "   - Добавьте устройство с IP 10.0.0.100 (IP терминала в VPN)"
echo ""

echo "════════════════════════════════════════════"
echo "ИНСТРУКЦИИ ПОКАЗАНЫ"
echo "════════════════════════════════════════════"
echo ""

