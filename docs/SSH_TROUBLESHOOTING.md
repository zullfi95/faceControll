# Решение проблем с SSH подключением

Если вы не можете подключиться к серверу по SSH с локальной машины, но можете заходить через консоль Hetzner, выполните следующие шаги:

## Локальная диагностика (Windows)

На Windows машине выполните PowerShell скрипт:

```powershell
.\scripts\diagnose-ssh-local.ps1
```

Или с указанием IP адреса:

```powershell
.\scripts\diagnose-ssh-local.ps1 -ServerIP 46.63.223.55
```

Этот скрипт проверит:
- Доступность сервера (ping)
- Доступность порта 22
- Наличие SSH клиента
- Попытку подключения

## Быстрая диагностика

На сервере (через консоль Hetzner) выполните:

```bash
# Если проект на сервере
cd /opt/facecontroll
bash scripts/diagnose-ssh.sh
```

**Если получаете ошибку "no such directory":**

1. Убедитесь, что вы в правильной директории проекта
2. Или скопируйте скрипт на сервер (см. [SSH_QUICK_FIX.md](SSH_QUICK_FIX.md))
3. Или выполните команды вручную (см. ниже)

Или вручную:

```bash
# Проверка SSH сервиса
systemctl status sshd

# Проверка порта 22
ss -tuln | grep ":22 "

# Проверка firewall
ufw status
```

## Решение проблем

### 1. SSH сервис не запущен

```bash
# Запустить SSH сервис
systemctl start sshd

# Включить автозапуск
systemctl enable sshd

# Проверить статус
systemctl status sshd
```

### 2. Firewall блокирует порт 22

#### UFW (если установлен):

```bash
# Разрешить SSH
ufw allow 22/tcp

# Или разрешить SSH по имени
ufw allow ssh

# Применить изменения
ufw reload

# Проверить статус
ufw status
```

#### iptables (если используется):

```bash
# Разрешить SSH
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Сохранить правила
iptables-save > /etc/iptables/rules.v4
```

### 3. Firewall в панели Hetzner

**ВАЖНО:** Проверьте настройки firewall в панели управления Hetzner:

1. Зайдите в панель Hetzner Cloud Console
2. Выберите ваш сервер
3. Перейдите в раздел **"Firewall"** или **"Networking"**
4. Убедитесь, что порт **22 (SSH)** разрешен для входящих подключений
5. Если firewall активен, добавьте правило:
   - **Protocol:** TCP
   - **Port:** 22
   - **Source IP:** 0.0.0.0/0 (или ваш IP для безопасности)

### 4. SSH слушает не на том интерфейсе

```bash
# Проверить на каком интерфейсе слушает SSH
ss -tuln | grep ":22 "

# Проверить конфигурацию SSH
grep -E "^ListenAddress|^#ListenAddress" /etc/ssh/sshd_config

# Если нужно изменить, отредактируйте:
sudo nano /etc/ssh/sshd_config
# Раскомментируйте или добавьте: ListenAddress 0.0.0.0
# Перезапустите SSH:
sudo systemctl restart sshd
```

### 5. Проверка сетевых интерфейсов

```bash
# Показать все сетевые интерфейсы
ip addr show

# Показать публичный IP
curl -4 ifconfig.me
# или
hostname -I
```

### 6. Проверка логов SSH

```bash
# Последние записи в логах
tail -50 /var/log/auth.log | grep ssh
# или на некоторых системах:
tail -50 /var/log/secure | grep ssh

# Проверить попытки подключения
journalctl -u sshd -n 50
```

## Полная диагностика

Выполните на сервере полную диагностику:

```bash
bash scripts/check-server.sh
```

Этот скрипт проверит:
- Статус SSH сервиса
- Открытые порты
- Настройки firewall
- Сетевые интерфейсы
- И другие параметры системы

## Рекомендации по безопасности

После восстановления SSH доступа:

1. **Измените порт SSH** (опционально, для безопасности):
   ```bash
   sudo nano /etc/ssh/sshd_config
   # Измените: Port 22 на Port 2222 (или другой)
   sudo systemctl restart sshd
   ```

2. **Настройте ключи SSH** вместо паролей:
   ```bash
   # На локальной машине:
   ssh-keygen -t ed25519
   ssh-copy-id user@server_ip
   ```

3. **Отключите вход root по паролю**:
   ```bash
   sudo nano /etc/ssh/sshd_config
   # Установите: PermitRootLogin no
   sudo systemctl restart sshd
   ```

4. **Ограничьте доступ по IP** (в firewall Hetzner):
   - Разрешите SSH только с вашего IP адреса
   - Или используйте VPN для доступа

## Проверка подключения с локальной машины

После исправления проблем на сервере, проверьте подключение:

```bash
# С локальной машины
ssh -v user@46.63.223.55

# Если используете другой порт:
ssh -p 2222 user@46.63.223.55
```

Флаг `-v` покажет подробную информацию о процессе подключения.

## Если ничего не помогает

1. Проверьте, что ваш IP не заблокирован в `/etc/hosts.deny`
2. Проверьте настройки в панели Hetzner (Firewall, Networking)
3. Попробуйте подключиться с другого IP адреса
4. Свяжитесь с поддержкой Hetzner, если проблема в их инфраструктуре

