# Руководство по развертыванию

Пошаговая инструкция по развертыванию Face Access Control System на сервере Hetzner.

## Предварительные требования

- Сервер на Hetzner с Ubuntu 22.04 (IP: 46.62.223.55)
- SSH доступ под root
- Домен (опционально, можно работать по IP)

## Быстрый старт

### Шаг 1: Подготовка на локальной машине

```bash
# Клонирование проекта
git clone <repo-url>
cd face-access-control

# Инициализация проекта (генерация ключей)
bash scripts/init-local.sh
```

Скрипт создаст файл `.env` с сгенерированными ключами безопасности.

### Шаг 2: Проверка SSH подключения

```bash
# Проверьте, что SSH ключ настроен
ssh root@46.62.223.55

# Если ключ не настроен, добавьте его:
ssh-copy-id root@46.62.223.55
```

### Шаг 3: Автоматическое развертывание

```bash
bash scripts/deploy.sh
```

Скрипт автоматически:
1. Установит Docker, Docker Compose, WireGuard
2. Создаст директорию `/opt/face-access-control`
3. Скопирует файлы проекта
4. Запустит контейнеры

### Шаг 4: Проверка развертывания

```bash
# Проверка статуса контейнеров
ssh root@46.62.223.55
cd /opt/face-access-control
docker-compose ps

# Все 3 контейнера должны быть в состоянии "Up"
# - db
# - backend
# - frontend
```

Откройте в браузере: http://46.62.223.55

> **Следующие шаги:** После развертывания настройте VPN и терминал согласно [VPN_SETUP.md](VPN_SETUP.md) и [TERMINAL_SETUP.md](TERMINAL_SETUP.md)

---

## Ручное развертывание

### Шаг 1: Подключение к серверу

```bash
ssh root@46.62.223.55
```

### Шаг 2: Установка зависимостей

```bash
# Обновление системы
apt update && apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh

# Установка Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Проверка установки
docker --version
docker-compose --version

# Установка WireGuard
apt install -y wireguard

# Установка Git (если планируете использовать git clone)
apt install -y git
```

### Шаг 3: Подготовка проекта

```bash
# Создание директории
mkdir -p /opt/face-access-control
cd /opt/face-access-control

# Клонирование (или копирование файлов)
git clone <repo-url> .
# ИЛИ скопируйте файлы через scp/rsync
```

### Шаг 4: Создание .env файла

```bash
# Создание из шаблона
cp env.template .env

# Редактирование
nano .env
```

Заполните следующие переменные:

```env
POSTGRES_PASSWORD=ваш_безопасный_пароль
WEBHOOK_API_KEY=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
TERMINAL_IN_IP=10.0.0.100
```

### Шаг 5: Запуск приложения

```bash
cd /opt/face-access-control

# Запуск контейнеров
docker-compose up -d

# Проверка логов
docker-compose logs -f

# Проверка статуса
docker-compose ps
```

### Шаг 6: Настройка автозапуска

```bash
# Создание systemd сервиса (опционально)
cat > /etc/systemd/system/face-access.service << 'EOF'
[Unit]
Description=Face Access Control System
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/face-access-control
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

# Включение сервиса
systemctl enable face-access
systemctl start face-access
```

---

## Настройка Firewall

### UFW (Ubuntu Firewall)

```bash
# Включение UFW
ufw enable

# Разрешение SSH
ufw allow 22/tcp

# Разрешение HTTP
ufw allow 80/tcp

# Разрешение HTTPS (если планируете использовать SSL)
ufw allow 443/tcp

# Разрешение WireGuard
ufw allow 51820/udp

# Проверка правил
ufw status
```

### IPTables (альтернатива)

```bash
# Базовые правила
iptables -A INPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
iptables -A INPUT -p udp --dport 51820 -j ACCEPT

# Сохранение правил
apt install -y iptables-persistent
netfilter-persistent save
```

---

## Настройка SSL (опционально)

Если у вас есть домен:

### С использованием Certbot

```bash
# Установка Certbot
apt install -y certbot python3-certbot-nginx

# Получение сертификата
certbot --nginx -d yourdomain.com

# Автоматическое обновление
certbot renew --dry-run
```

### Обновление docker-compose.yml

```yaml
services:
  frontend:
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /etc/letsencrypt:/etc/letsencrypt:ro
```

Обновите `frontend/nginx.conf` для HTTPS.

---

## Мониторинг и обслуживание

### Просмотр логов

```bash
# Все сервисы
docker-compose logs -f

# Только backend
docker-compose logs -f backend

# Последние 100 строк
docker-compose logs --tail=100
```

### Обновление приложения

```bash
cd /opt/face-access-control

# Получение обновлений
git pull
# ИЛИ копирование новых файлов

# Перезапуск контейнеров
docker-compose down
docker-compose up -d --build
```

### Backup базы данных

```bash
# Создание backup
docker-compose exec db pg_dump -U postgres facerecog > backup_$(date +%Y%m%d).sql

# Восстановление
docker-compose exec -T db psql -U postgres facerecog < backup_20240101.sql
```

### Очистка старых данных

```bash
# Удаление неиспользуемых образов
docker system prune -a

# Удаление volumes (ОСТОРОЖНО! Удаляет данные)
docker-compose down -v
```

---

## Troubleshooting

### Контейнеры не запускаются

```bash
# Проверка логов
docker-compose logs

# Проверка портов
netstat -tulpn | grep -E '(80|5432|8000)'

# Перезапуск
docker-compose restart
```

### База данных недоступна

```bash
# Проверка healthcheck
docker-compose ps

# Вход в контейнер БД
docker-compose exec db psql -U postgres

# Пересоздание БД (ОСТОРОЖНО!)
docker-compose down
docker volume rm face-access-control_postgres_data
docker-compose up -d
```

### Недостаточно памяти

```bash
# Проверка использования
docker stats

# Добавление swap
fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

---

## Следующие шаги

После успешного развертывания:

1. [Настройка VPN](VPN_SETUP.md)
2. [Настройка терминала](TERMINAL_SETUP.md)
3. [Руководство пользователя](USER_GUIDE.md)
4. [API Документация](API_DOCUMENTATION.md)
5. [Технические детали](TECHNICAL_DETAILS.md)

---

## Контакты поддержки

При возникновении проблем создайте Issue в репозитории проекта.

