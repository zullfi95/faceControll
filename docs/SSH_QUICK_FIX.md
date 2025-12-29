# Быстрое решение проблемы SSH

Если вы на сервере и получаете ошибку "no such directory", выполните следующие шаги:

## Вариант 1: Если проект уже на сервере

```bash
# Перейдите в директорию проекта
cd /opt/facecontroll

# Или если проект в другом месте, найдите его:
find / -name "diagnose-ssh.sh" 2>/dev/null

# Затем выполните скрипт
bash scripts/diagnose-ssh.sh
```

## Вариант 2: Скопируйте скрипт на сервер

### Через консоль Hetzner (вручную):

1. Откройте скрипт `scripts/diagnose-ssh.sh` на локальной машине
2. Скопируйте его содержимое
3. На сервере создайте файл:
   ```bash
   nano /tmp/diagnose-ssh.sh
   ```
4. Вставьте содержимое скрипта
5. Сохраните (Ctrl+O, Enter, Ctrl+X)
6. Сделайте исполняемым:
   ```bash
   chmod +x /tmp/diagnose-ssh.sh
   bash /tmp/diagnose-ssh.sh
   ```

## Вариант 3: Выполните команды вручную

Если скрипт недоступен, выполните команды напрямую:

```bash
# 1. Проверка SSH сервиса
systemctl status sshd

# 2. Проверка порта 22
ss -tuln | grep ":22 "

# 3. Проверка firewall (UFW)
ufw status

# 4. Если UFW активен, разрешите SSH
ufw allow 22/tcp
ufw reload

# 5. Запустите SSH сервис
systemctl start sshd
systemctl enable sshd

# 6. Проверьте статус
systemctl status sshd
```

## Вариант 4: Проверка через панель Hetzner

1. Зайдите в [Hetzner Cloud Console](https://console.hetzner.cloud/)
2. Выберите ваш сервер
3. Перейдите в **"Firewall"** или **"Networking"**
4. Проверьте, что порт **22 (SSH)** разрешен
5. Если нет - добавьте правило для порта 22

## Быстрая проверка всех компонентов

```bash
# Проверка SSH
systemctl status sshd

# Проверка порта
ss -tuln | grep ":22 "

# Проверка firewall
ufw status | grep 22

# Проверка сетевых интерфейсов
ip addr show

# Проверка публичного IP
curl -4 ifconfig.me
```

## Если ничего не помогает

Выполните минимальный набор команд для восстановления SSH:

```bash
# Запустить SSH
systemctl start sshd
systemctl enable sshd

# Разрешить в firewall
ufw allow 22/tcp
ufw reload

# Проверить
systemctl status sshd
ss -tuln | grep ":22 "
```

После этого проверьте подключение с локальной машины.

