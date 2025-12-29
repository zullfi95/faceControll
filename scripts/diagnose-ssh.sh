#!/bin/bash

# Скрипт диагностики SSH подключения
# Выполните этот скрипт НА СЕРВЕРЕ через консоль Hetzner

echo "=========================================="
echo "ДИАГНОСТИКА SSH ПОДКЛЮЧЕНИЯ"
echo "=========================================="
echo ""

echo "1. ПРОВЕРКА SSH СЕРВИСА:"
if systemctl is-active --quiet sshd || systemctl is-active --quiet ssh; then
    echo "   ✓ SSH сервис запущен"
    systemctl status sshd --no-pager | head -5 || systemctl status ssh --no-pager | head -5
else
    echo "   ✗ SSH сервис НЕ запущен!"
    echo "   Запустите: systemctl start sshd"
fi
echo ""

echo "2. ПРОВЕРКА ПОРТА 22:"
if ss -tuln | grep -q ":22 "; then
    echo "   ✓ Порт 22 слушается"
    ss -tuln | grep ":22 "
else
    echo "   ✗ Порт 22 НЕ слушается!"
fi
echo ""

echo "3. ПРОВЕРКА FIREWALL (UFW):"
if command -v ufw &> /dev/null; then
    echo "   Статус UFW:"
    ufw status | head -10
    echo ""
    if ufw status | grep -q "22/tcp"; then
        echo "   ✓ Порт 22 разрешен в UFW"
    else
        echo "   ✗ Порт 22 НЕ разрешен в UFW!"
        echo "   Разрешите: ufw allow 22/tcp"
    fi
else
    echo "   UFW не установлен"
fi
echo ""

echo "4. ПРОВЕРКА FIREWALL (iptables):"
if command -v iptables &> /dev/null; then
    echo "   Правила для порта 22:"
    iptables -L INPUT -n | grep -E "(22|ssh)" || echo "   Нет специальных правил для SSH"
else
    echo "   iptables не установлен"
fi
echo ""

echo "5. ПРОВЕРКА SSH КОНФИГУРАЦИИ:"
if [ -f /etc/ssh/sshd_config ]; then
    echo "   Файл конфигурации существует"
    echo "   Порт SSH:"
    grep -E "^Port|^#Port" /etc/ssh/sshd_config | head -1 || echo "   Используется порт по умолчанию (22)"
    echo "   Разрешен вход root:"
    grep -E "^PermitRootLogin|^#PermitRootLogin" /etc/ssh/sshd_config | head -1 || echo "   Настройка не найдена"
    echo "   Парольная аутентификация:"
    grep -E "^PasswordAuthentication|^#PasswordAuthentication" /etc/ssh/sshd_config | head -1 || echo "   Настройка не найдена"
else
    echo "   ✗ Файл /etc/ssh/sshd_config не найден!"
fi
echo ""

echo "6. ПРОВЕРКА СЕТЕВЫХ ИНТЕРФЕЙСОВ:"
echo "   Публичный IP адрес:"
ip addr show | grep -E "inet.*scope global" | awk '{print "   " $2}' || hostname -I | awk '{print "   " $1}'
echo ""

echo "7. ПРОВЕРКА ACTIVE CONNECTIONS:"
echo "   Текущие SSH подключения:"
ss -tn | grep ":22 " | head -5 || echo "   Нет активных подключений"
echo ""

echo "8. ПРОВЕРКА ЛОГОВ SSH:"
echo "   Последние записи в логах SSH:"
if [ -f /var/log/auth.log ]; then
    tail -5 /var/log/auth.log | grep -i ssh || echo "   Нет записей"
elif [ -f /var/log/secure ]; then
    tail -5 /var/log/secure | grep -i ssh || echo "   Нет записей"
else
    echo "   Логи не найдены"
fi
echo ""

echo "9. РЕКОМЕНДАЦИИ:"
echo "   Если SSH не работает, выполните:"
echo "   1. systemctl start sshd"
echo "   2. systemctl enable sshd"
echo "   3. ufw allow 22/tcp"
echo "   4. systemctl restart sshd"
echo "   5. Проверьте настройки firewall в панели Hetzner"
echo ""

echo "=========================================="
echo "ДИАГНОСТИКА ЗАВЕРШЕНА"
echo "=========================================="

