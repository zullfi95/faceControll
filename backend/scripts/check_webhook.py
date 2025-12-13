"""
Скрипт для проверки статуса webhook на терминале Hikvision
"""
import asyncio
import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import database, crud
from app.hikvision_client import HikvisionClient
from app.utils.crypto import decrypt_password


async def check_webhook_status():
    """Проверка статуса webhook на терминале."""
    async for db in database.get_db():
        try:
            # Получаем первое активное устройство
            devices = await crud.get_all_devices(db)
            if not devices:
                print("❌ Устройства не найдены в базе данных")
                return
            
            device = devices[0]
            print(f"\n📡 Проверка webhook для устройства: {device.name} ({device.ip_address})")
            
            # Расшифровываем пароль
            try:
                password = decrypt_password(device.password_encrypted)
            except Exception as e:
                print(f"❌ Ошибка расшифровки пароля: {e}")
                print("💡 Убедитесь, что ENCRYPTION_KEY правильно настроен")
                return
            
            # Создаем клиент
            client = HikvisionClient(device.ip_address, device.username, password)
            
            # Проверяем соединение
            print("\n🔌 Проверка соединения с терминалом...")
            connected, error_msg = await client.check_connection()
            if not connected:
                print(f"❌ Терминал недоступен: {error_msg}")
                return
            print("✅ Соединение установлено")
            
            # Получаем текущие настройки HTTP Listening
            print("\n📋 Получение текущих настроек HTTP Listening...")
            result = await client.get_http_hosts()
            
            if result.get("success"):
                http_hosts = result.get("data", {})
                print("\n✅ Настройки HTTP Listening получены:")
                print(f"   Данные: {http_hosts}")
                
                # Проверяем, соответствует ли настройка ожидаемой
                expected_ip = "192.168.1.64"
                expected_url = "/events/webhook"
                expected_port = 80
                expected_protocol = "http"
                
                print(f"\n🔍 Проверка соответствия настройкам:")
                print(f"   Ожидаемый IP: {expected_ip}")
                print(f"   Ожидаемый URL: {expected_url}")
                print(f"   Ожидаемый порт: {expected_port}")
                print(f"   Ожидаемый протокол: {expected_protocol}")
                
                # Парсим ответ для проверки
                if isinstance(http_hosts, dict):
                    # Проверяем структуру XML ответа
                    http_host_notification = http_hosts.get("HttpHostNotificationList", {}).get("HttpHostNotification", {})
                    
                    if http_host_notification and isinstance(http_host_notification, dict):
                        current_ip = http_host_notification.get("ipAddress", "")
                        current_url = http_host_notification.get("url", "")
                        current_port_str = http_host_notification.get("portNo", "0")
                        current_port = int(current_port_str) if current_port_str.isdigit() else 0
                        current_protocol_type = http_host_notification.get("protocolType", "").upper()
                        # Преобразуем HTTP в http для сравнения
                        current_protocol = current_protocol_type.lower() if current_protocol_type else ""
                        
                        print(f"\n📊 Текущие настройки на терминале:")
                        print(f"   ID: {http_host_notification.get('id', 'N/A')}")
                        print(f"   IP: {current_ip}")
                        print(f"   URL: {current_url}")
                        print(f"   Порт: {current_port}")
                        print(f"   Протокол: {current_protocol_type} ({current_protocol})")
                        print(f"   Формат параметров: {http_host_notification.get('parameterFormatType', 'N/A')}")
                        print(f"   Аутентификация: {http_host_notification.get('httpAuthenticationMethod', 'N/A')}")
                        
                        # Сравниваем настройки
                        if (current_ip == expected_ip and 
                            current_url == expected_url and 
                            current_port == expected_port and 
                            current_protocol == expected_protocol):
                            print("\n✅ Настройки соответствуют ожидаемым!")
                            print("\n🎉 Webhook настроен правильно!")
                            print("   Терминал будет отправлять события на:")
                            print(f"   http://{current_ip}:{current_port}{current_url}")
                        else:
                            print("\n⚠️ Настройки не полностью соответствуют ожидаемым!")
                            print("\n💡 Для обновления настроек используйте:")
                            print(f"   POST /api/devices/{device.id}/webhook/configure")
                            print(f"   Body: {{")
                            print(f"     \"server_ip\": \"{expected_ip}\",")
                            print(f"     \"server_port\": {expected_port},")
                            print(f"     \"url_path\": \"{expected_url}\",")
                            print(f"     \"protocol\": \"{expected_protocol}\"")
                            print(f"   }}")
                    else:
                        print("\n⚠️ HTTP Listening не настроен на терминале")
                        print("   Структура данных:", http_hosts)
                else:
                    print(f"\n⚠️ Неожиданный формат ответа: {http_hosts}")
            else:
                error = result.get("error", "Unknown error")
                print(f"\n❌ Ошибка получения настроек: {error}")
                if result.get("requires_manual_setup"):
                    print("\n💡 Требуется ручная настройка через веб-интерфейс терминала")
                    print("   Путь: Configuration → Network → HTTP Listening")
            
            # Проверяем доступность webhook endpoint
            print("\n🌐 Проверка доступности webhook endpoint...")
            print(f"   URL: http://192.168.1.64:80/events/webhook")
            print("   💡 Для проверки отправьте тестовое событие с терминала")
            
            print("\n📝 Для мониторинга входящих событий используйте:")
            print("   GET /api/debug/logs?prefix=WEBHOOK")
            print("   или")
            print("   docker-compose logs -f backend | grep WEBHOOK")
            
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
        finally:
            break


if __name__ == "__main__":
    asyncio.run(check_webhook_status())

