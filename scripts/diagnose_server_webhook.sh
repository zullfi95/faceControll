#!/bin/bash
# Скрипт диагностики webhook и загрузки фото на сервере

echo "=== Диагностика Webhook и загрузки фото ==="
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Проверка статуса контейнеров
echo -e "${YELLOW}1. Проверка статуса контейнеров:${NC}"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'face|backend|frontend'
echo ""

# 2. Проверка портов
echo -e "${YELLOW}2. Проверка открытых портов:${NC}"
netstat -tuln | grep -E ':(80|8000|443)' || ss -tuln | grep -E ':(80|8000|443)'
echo ""

# 3. Проверка firewall
echo -e "${YELLOW}3. Проверка firewall:${NC}"
ufw status | grep -E '80|443' || echo "Firewall не настроен или использует iptables"
echo ""

# 4. Проверка IP адресов сервера
echo -e "${YELLOW}4. IP адреса сервера:${NC}"
echo "Внешний IP (eth0):"
ip addr show eth0 | grep -oP 'inet \K[\d.]+' || echo "Не найден"
echo "WireGuard IP (wg0):"
ip addr show wg0 2>/dev/null | grep -oP 'inet \K[\d.]+' || echo "WireGuard не настроен"
echo ""

# 5. Проверка webhook endpoint
echo -e "${YELLOW}5. Тест webhook endpoint:${NC}"
WEBHOOK_KEY=$(docker exec facecontroll-backend-1 env | grep WEBHOOK_API_KEY | cut -d'=' -f2)
if [ -z "$WEBHOOK_KEY" ]; then
    echo -e "${RED}WEBHOOK_API_KEY не установлен!${NC}"
else
    echo "Webhook API Key: ${WEBHOOK_KEY:0:10}..."
    echo "Тест локального webhook:"
    curl -s -X POST http://localhost/events/webhook \
        -H 'Content-Type: application/json' \
        -H "X-API-Key: $WEBHOOK_KEY" \
        -d '{"test":"diagnostic"}' | jq . 2>/dev/null || curl -s -X POST http://localhost/events/webhook \
        -H 'Content-Type: application/json' \
        -H "X-API-Key: $WEBHOOK_KEY" \
        -d '{"test":"diagnostic"}'
    echo ""
fi
echo ""

# 6. Проверка последних запросов к webhook
echo -e "${YELLOW}6. Последние запросы к webhook (из логов nginx):${NC}"
docker exec facecontroll-frontend-1 tail -100 /var/log/nginx/access.log 2>/dev/null | grep '/events/webhook' | tail -5 || echo "Нет запросов к webhook"
echo ""

# 7. Проверка логов backend на webhook
echo -e "${YELLOW}7. Последние записи webhook в логах backend:${NC}"
docker logs facecontroll-backend-1 --tail 200 2>&1 | grep -iE '\[WEBHOOK\]|webhook' | tail -10 || echo "Нет записей о webhook в логах"
echo ""

# 8. Проверка директории uploads
echo -e "${YELLOW}8. Проверка директории uploads:${NC}"
echo "Количество файлов:"
docker exec facecontroll-backend-1 ls -la /app/uploads/ 2>/dev/null | wc -l
echo "Размер директории:"
docker exec facecontroll-backend-1 du -sh /app/uploads/ 2>/dev/null || echo "Директория не найдена"
echo "Права доступа:"
docker exec facecontroll-backend-1 ls -ld /app/uploads/ 2>/dev/null || echo "Директория не найдена"
echo ""

# 9. Проверка конфигурации nginx для webhook
echo -e "${YELLOW}9. Проверка конфигурации nginx для /events/webhook:${NC}"
docker exec facecontroll-frontend-1 grep -A 5 'location.*webhook' /etc/nginx/nginx.conf 2>/dev/null || \
docker exec facecontroll-frontend-1 grep -A 5 'location.*webhook' /etc/nginx/conf.d/*.conf 2>/dev/null || \
echo "Конфигурация не найдена"
echo ""

# 10. Проверка переменных окружения
echo -e "${YELLOW}10. Переменные окружения backend:${NC}"
docker exec facecontroll-backend-1 env | grep -E 'WEBHOOK|TERMINAL|SERVER' | sed 's/=.*/=***/' 
echo ""

# 11. Рекомендации
echo -e "${YELLOW}=== РЕКОМЕНДАЦИИ ===${NC}"
echo ""
echo "1. Проверьте настройки webhook на терминале:"
echo "   - Event Alarm IP должен быть: 46.62.223.55 (внешний IP сервера)"
echo "   - URL должен быть: /events/webhook"
echo "   - Port: 80"
echo "   - Protocol: HTTP"
echo "   - HTTP Listening должен быть ВКЛЮЧЕН"
echo ""
echo "2. Проверьте доступность сервера с терминала:"
echo "   ping 46.62.223.55"
echo "   telnet 46.62.223.55 80"
echo ""
echo "3. Если терминал в VPN сети (192.168.78.0/24), используйте IP: 192.168.78.1"
echo ""
echo "4. Проверьте логи в реальном времени:"
echo "   docker logs -f facecontroll-backend-1 | grep -i webhook"
echo ""

