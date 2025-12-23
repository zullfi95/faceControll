#!/usr/bin/env python3
"""
Скрипт для подключения к серверу по SSH с паролем и проверки состояния
Требует: pip install paramiko
"""

import sys
import subprocess

def install_paramiko():
    """Установка paramiko если не установлен"""
    try:
        import paramiko
        return True
    except ImportError:
        print("Установка paramiko...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "-q"])
        try:
            import paramiko
            return True
        except ImportError:
            print("Ошибка: не удалось установить paramiko")
            return False

def check_server():
    """Подключение к серверу и проверка состояния"""
    if not install_paramiko():
        return
    
    import paramiko
    
    # Параметры подключения
    hostname = "46.62.223.55"
    username = "root"
    password = "WmbTnncE9qme"
    port = 22
    
    # Команды для проверки
    commands = """
echo "=========================================="
echo "ПРОВЕРКА СОСТОЯНИЯ СЕРВЕРА"
echo "=========================================="
echo ""
echo "1. ВРЕМЯ РАБОТЫ И НАГРУЗКА:"
uptime
echo ""
echo "2. ИСПОЛЬЗОВАНИЕ ПАМЯТИ:"
free -h
echo ""
echo "3. ИСПОЛЬЗОВАНИЕ ДИСКОВ:"
df -h
echo ""
echo "4. СОСТОЯНИЕ DOCKER КОНТЕЙНЕРОВ:"
docker ps -a 2>/dev/null || echo "Docker не установлен/не запущен"
echo ""
echo "5. АКТИВНЫЕ СЕТЕВЫЕ ПОДКЛЮЧЕНИЯ:"
ss -tuln | head -20
echo ""
echo "6. ПРОЦЕССЫ С ВЫСОКИМ ИСПОЛЬЗОВАНИЕМ CPU:"
ps aux --sort=-%cpu | head -10
echo ""
echo "7. ПРОЦЕССЫ С ВЫСОКИМ ИСПОЛЬЗОВАНИЕМ ПАМЯТИ:"
ps aux --sort=-%mem | head -10
echo ""
echo "8. ПРОВЕРКА SSH КЛЮЧЕЙ:"
cat ~/.ssh/authorized_keys 2>/dev/null | head -5 || echo "Файл не найден"
echo ""
echo "9. ПРАВА ДОСТУПА .ssh:"
ls -la ~/.ssh/ 2>/dev/null || echo "Директория не найдена"
echo ""
echo "10. ПОСЛЕДНИЕ ОШИБКИ В ЛОГАХ:"
journalctl -p err -n 10 --no-pager 2>/dev/null || tail -10 /var/log/syslog 2>/dev/null || echo "Не удалось получить логи"
"""
    
    try:
        print(f"Подключение к {username}@{hostname}...")
        
        # Создаем SSH клиент
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Подключаемся
        ssh.connect(hostname, port=port, username=username, password=password, timeout=10)
        print("✓ Подключение установлено\n")
        
        # Выполняем команды
        stdin, stdout, stderr = ssh.exec_command(commands)
        
        # Выводим результаты
        output = stdout.read().decode('utf-8')
        errors = stderr.read().decode('utf-8')
        
        if output:
            print(output)
        
        if errors and "Docker" not in errors and "journalctl" not in errors:
            print("Ошибки:", errors, file=sys.stderr)
        
        # Закрываем соединение
        ssh.close()
        print("\n✓ Проверка завершена")
        
    except paramiko.AuthenticationException as e:
        print(f"Ошибка аутентификации: {e}")
        print("\nВозможные причины:")
        print("1. Неверный пароль")
        print("2. Ограничение доступа по IP")
    except paramiko.SSHException as e:
        print(f"Ошибка SSH: {e}")
    except Exception as e:
        print(f"Ошибка подключения: {type(e).__name__}: {e}")

if __name__ == "__main__":
    check_server()



