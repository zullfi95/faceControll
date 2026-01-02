# Настройка VPN

## Обзор

Система использует WireGuard VPN для безопасного соединения между облачным сервером и офисной сетью. Это позволяет терминалам Hikvision в офисе безопасно общаться с сервером через зашифрованный туннель.

## Архитектура

```
[Офис]                          [Облако]
┌─────────────────────┐        ┌──────────────────────┐
│ Терминал            │        │  Backend (FastAPI)   │
│ DS-K1T343EFWX  ────┼────────┼─► PostgreSQL         │
│ 10.0.0.100 (VPN)    │  VPN   │  10.0.0.1 (VPN)      │
└──────────┬──────────┘        └──────────┬───────────┘
           │                              │
      ┌────┴────┐                    ┌────┴────┐
      │ Keenetic│                    │ Nginx   │
      │ Router  │                    │ (Proxy) │
      │ + VPN   │                    └─────────┘
      └─────────┘
```

## Настройка сервера (Hetzner)

### 1. Установка WireGuard

```bash
# На Ubuntu/Debian
sudo apt update
sudo apt install wireguard

# На CentOS/RHEL
sudo yum install wireguard-tools
```

### 2. Генерация ключей

```bash
cd wireguard
bash generate-keys.sh
```

Скрипт создаст:
- `server-private.key` - приватный ключ сервера
- `server-public.key` - публичный ключ сервера
- `client-private.key` - приватный ключ клиента
- `client-public.key` - публичный ключ клиента

### 3. Конфигурация сервера

Создайте файл `/etc/wireguard/wg0.conf`:

```ini
[Interface]
Address = 10.0.0.1/24
PrivateKey = <server-private-key>
ListenPort = 51820

# Включить forwarding
PreUp = sysctl -w net.ipv4.ip_forward=1
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PreDown = iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE; iptables -D FORWARD -i wg0 -j ACCEPT
PostDown = sysctl -w net.ipv4.ip_forward=0

[Peer]
PublicKey = <client-public-key>
AllowedIPs = 10.0.0.2/32
```

### 4. Запуск VPN

```bash
# Включение и запуск
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0

# Проверка статуса
sudo wg show

# Проверка логов
sudo journalctl -u wg-quick@wg0
```

## Настройка роутера (Keenetic)

### Требования
- Keenetic Runner 4G (KN-2210) или совместимый роутер
- Поддержка WireGuard

### 1. Импорт конфигурации

1. Откройте веб-интерфейс роутера
2. Перейдите в **Интернет → Другие подключения → WireGuard**
3. Нажмите **Добавить туннель**
4. Импортируйте файл `wg0-client.conf` или введите настройки вручную:

```ini
[Interface]
PrivateKey = <client-private-key>
Address = 10.0.0.2/24

[Peer]
PublicKey = <server-public-key>
Endpoint = <server-ip>:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
```

### 2. Настройка маршрутизации

Убедитесь, что:
- VPN туннель активен
- Терминал Hikvision доступен по IP 10.0.0.100
- Роутер маршрутизирует трафик в VPN

### 3. Проверка соединения

```bash
# С роутера (через SSH или веб-интерфейс)
ping 10.0.0.1

# С сервера
ping 10.0.0.2
```

## Безопасность

### Важные правила

1. **Никогда не коммитьте приватные ключи** в Git
2. Регулярно ротируйте ключи (каждые 6-12 месяцев)
3. Используйте strong pre-shared keys для дополнительной защиты
4. Мониторьте логи VPN соединений

### Firewall правила

На сервере убедитесь, что:
- Порт 51820 UDP открыт
- WireGuard интерфейс правильно настроен
- Только необходимые порты доступны из VPN

```bash
# Проверка открытых портов
sudo ufw status
sudo ufw allow 51820/udp
```

## Диагностика

### Проверка соединения

```bash
# Статус интерфейса
sudo wg show

# Логи роутера
# В веб-интерфейсе Keenetic: Система → Диагностика → Логи

# Пинг через VPN
ping 10.0.0.2  # с сервера на роутер
ping 10.0.0.1  # с роутера на сервер
```

### Распространенные проблемы

#### "No handshake"
- Проверьте публичные ключи
- Убедитесь, что порты открыты
- Проверьте firewall настройки

#### "Unable to connect"
- Проверьте IP адреса и порты
- Убедитесь, что WireGuard запущен на сервере
- Проверьте DNS (если используется домен)

#### "Traffic not routing"
- Проверьте `AllowedIPs` настройки
- Убедитесь в правильности маршрутизации
- Проверьте MTU (установите 1420 если возникают проблемы)

## Мониторинг

### Метрики для отслеживания
- Статус VPN туннеля
- Количество переданных байт
- Время последней handshake
- Логи подключений/отключений

### Автоматизация
Создайте скрипт мониторинга:

```bash
#!/bin/bash
# check_vpn.sh
if ! sudo wg show | grep -q "latest handshake"; then
    echo "VPN down - sending alert"
    # Отправка уведомления
fi
```
