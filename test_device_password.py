#!/usr/bin/env python3
"""
Скрипт для тестирования подключения к терминалу Hikvision
"""
import requests
from requests.auth import HTTPDigestAuth
import sys

def test_connection(ip, username, password):
    """Проверка подключения к терминалу"""
    url = f"https://{ip}/ISAPI/System/deviceInfo"
    
    print(f"Тестирование подключения к {ip}...")
    print(f"Username: {username}")
    print(f"Password: {'*' * len(password)}")
    print()
    
    try:
        # Пробуем HTTPS с игнорированием SSL
        response = requests.get(
            url,
            auth=HTTPDigestAuth(username, password),
            verify=False,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ УСПЕХ! Подключение установлено!")
            print(f"Статус: {response.status_code}")
            print(f"Ответ (первые 200 символов):")
            print(response.text[:200])
            return True
        elif response.status_code == 401:
            print("❌ ОШИБКА: Неверные учетные данные (401 Unauthorized)")
            print("Проверьте username и password!")
            return False
        else:
            print(f"⚠️  ВНИМАНИЕ: Получен статус {response.status_code}")
            print(f"Ответ: {response.text[:200]}")
            return False
            
    except requests.exceptions.SSLError:
        print("⚠️  SSL ошибка, пробую HTTP...")
        # Пробуем HTTP
        url = f"http://{ip}/ISAPI/System/deviceInfo"
        try:
            response = requests.get(
                url,
                auth=HTTPDigestAuth(username, password),
                timeout=10
            )
            
            if response.status_code == 200:
                print("✅ УСПЕХ! Подключение установлено через HTTP!")
                return True
            else:
                print(f"❌ HTTP также не работает: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ HTTP ошибка: {e}")
            return False
            
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        return False

if __name__ == "__main__":
    # Параметры устройства
    IP = "192.168.1.65"
    USERNAME = "admin"
    
    print("="*60)
    print("ТЕСТ ПОДКЛЮЧЕНИЯ К ТЕРМИНАЛУ HIKVISION")
    print("="*60)
    print()
    
    # Запрашиваем пароль
    if len(sys.argv) > 1:
        PASSWORD = sys.argv[1]
    else:
        PASSWORD = input("Введите пароль для терминала: ")
    
    print()
    test_connection(IP, USERNAME, PASSWORD)
    print()
    print("="*60)

