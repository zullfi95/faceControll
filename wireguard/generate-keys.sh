#!/bin/bash

# Скрипт генерации ключей WireGuard для сервера и клиента
# Использование: bash generate-keys.sh

set -e

echo "=== Генерация ключей WireGuard ==="
echo ""

# Проверка установки WireGuard
if ! command -v wg &> /dev/null; then
    echo "Ошибка: WireGuard не установлен!"
    echo "Установите WireGuard:"
    echo "  Ubuntu/Debian: sudo apt install wireguard"
    echo "  CentOS/RHEL: sudo yum install wireguard-tools"
    exit 1
fi

# Создание директории для ключей
mkdir -p keys

# Генерация ключей сервера
echo "Генерация ключей сервера..."
wg genkey | tee keys/server.key | wg pubkey > keys/server.pub
chmod 600 keys/server.key

# Генерация ключей клиента
echo "Генерация ключей клиента (Keenetic Router)..."
wg genkey | tee keys/client.key | wg pubkey > keys/client.pub
chmod 600 keys/client.key

# Чтение ключей
SERVER_PRIVATE_KEY=$(cat keys/server.key)
SERVER_PUBLIC_KEY=$(cat keys/server.pub)
CLIENT_PRIVATE_KEY=$(cat keys/client.key)
CLIENT_PUBLIC_KEY=$(cat keys/client.pub)

echo ""
echo "✓ Ключи сгенерированы успешно!"
echo ""

# Создание конфигурации сервера
echo "Создание конфигурации сервера..."
sed "s|SERVER_PRIVATE_KEY|$SERVER_PRIVATE_KEY|g" wg0-server.conf.template | \
sed "s|CLIENT_PUBLIC_KEY|$CLIENT_PUBLIC_KEY|g" > wg0-server.conf

echo "✓ Конфигурация сервера создана: wg0-server.conf"

# Создание конфигурации клиента
echo "Создание конфигурации клиента..."
sed "s|CLIENT_PRIVATE_KEY|$CLIENT_PRIVATE_KEY|g" wg0-client.conf.template | \
sed "s|SERVER_PUBLIC_KEY|$SERVER_PUBLIC_KEY|g" > wg0-client.conf

echo "✓ Конфигурация клиента создана: wg0-client.conf"
echo ""

# Вывод информации
echo "════════════════════════════════════════════"
echo "СГЕНЕРИРОВАННЫЕ КЛЮЧИ"
echo "════════════════════════════════════════════"
echo ""
echo "Сервер (Hetzner 46.62.223.55):"
echo "  Приватный ключ: $SERVER_PRIVATE_KEY"
echo "  Публичный ключ: $SERVER_PUBLIC_KEY"
echo ""
echo "Клиент (Keenetic Router):"
echo "  Приватный ключ: $CLIENT_PRIVATE_KEY"
echo "  Публичный ключ: $CLIENT_PUBLIC_KEY"
echo ""
echo "════════════════════════════════════════════"
echo "СЛЕДУЮЩИЕ ШАГИ"
echo "════════════════════════════════════════════"
echo ""
echo "1. НА СЕРВЕРЕ HETZNER:"
echo "   sudo cp wg0-server.conf /etc/wireguard/wg0.conf"
echo "   sudo chmod 600 /etc/wireguard/wg0.conf"
echo "   sudo systemctl enable wg-quick@wg0"
echo "   sudo systemctl start wg-quick@wg0"
echo ""
echo "2. НА KEENETIC ROUTER:"
echo "   - Зайдите в веб-интерфейс роутера"
echo "   - Перейдите в: Интернет → Другие подключения → WireGuard"
echo "   - Импортируйте файл wg0-client.conf"
echo "   - Или скопируйте содержимое вручную"
echo ""
echo "3. ПРОВЕРКА СОЕДИНЕНИЯ:"
echo "   На сервере: sudo wg show"
echo "   Ping тест: ping 10.0.0.2"
echo ""
echo "4. НАСТРОЙКА ТЕРМИНАЛА DS-K1T343EFWX:"
echo "   - HTTP Listening IP: 10.0.0.1"
echo "   - URL: /events/webhook"
echo ""
echo "⚠️  ВАЖНО: Сохраните ключи в безопасном месте!"
echo "    Файлы ключей находятся в директории: keys/"
echo ""

