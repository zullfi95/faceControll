#!/usr/bin/env python3
import socket
import subprocess
import sys

def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), 1

print("=== Проверка VPN подключения ===")
print()

# Проверяем сетевые интерфейсы
print("1. Сетевые интерфейсы:")
stdout, stderr, code = run_cmd("ip addr show")
if code == 0:
    # Ищем wg0 интерфейс
    if "wg0" in stdout:
        print("✅ VPN интерфейс wg0 найден")
        for line in stdout.split('\n'):
            if 'inet ' in line and 'wg0' in line:
                ip = line.split()[1].split('/')[0]
                print(f"✅ VPN IP адрес: {ip}")
                if ip == "10.0.0.1":
                    print("✅ Корректный VPN IP адрес сервера")
                else:
                    print(f"⚠️  Неправильный VPN IP: {ip} (ожидался 10.0.0.1)")
    else:
        print("❌ VPN интерфейс wg0 не найден")
else:
    print(f"❌ Ошибка проверки интерфейсов: {stderr}")

print()

# Проверяем маршрутизацию
print("2. Маршрутизация:")
stdout, stderr, code = run_cmd("ip route")
if code == 0:
    if "10.0.0.0/24" in stdout:
        print("✅ Маршрут к VPN сети 10.0.0.0/24 найден")
    else:
        print("❌ Маршрут к VPN сети 10.0.0.0/24 не найден")
else:
    print(f"❌ Ошибка проверки маршрутизации: {stderr}")

print()

# Проверяем подключение к терминалу
print("3. Проверка подключения к терминалу (10.0.0.100):")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex(('10.0.0.100', 80))
    sock.close()

    if result == 0:
        print("✅ Терминал доступен по HTTP (порт 80)")
    else:
        print("❌ Терминал не доступен по HTTP (порт 80)")
        print("   Возможные причины:")
        print("   - Терминал не подключен к VPN")
        print("   - Терминал выключен")
        print("   - Неправильный IP адрес терминала")
except Exception as e:
    print(f"❌ Ошибка проверки терминала: {e}")

print()

# Проверяем DNS разрешение
print("4. DNS разрешение:")
try:
    ip = socket.gethostbyname('10.0.0.100')
    print(f"✅ DNS разрешение работает: 10.0.0.100 -> {ip}")
except Exception as e:
    print(f"ℹ️  DNS разрешение: {e} (нормально для IP адресов)")

print()
print("=== Рекомендации ===")
print("Если терминал не доступен:")
print("1. Проверьте, что Keenetic роутер подключен к VPN")
print("2. Убедитесь, что терминал имеет IP 10.0.0.100 в VPN сети")
print("3. Проверьте питание и сеть терминала")
print("4. На терминале настройте webhook на IP 10.0.0.1:8000")

