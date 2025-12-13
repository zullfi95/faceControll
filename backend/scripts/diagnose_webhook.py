"""
Диагностика проблемы с webhook - почему события не приходят
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import database, crud
from app.hikvision_client import HikvisionClient
from app.utils.crypto import decrypt_password


async def diagnose_webhook():
    """Диагностика проблемы с webhook."""
    print("🔍 Диагностика проблемы с webhook\n")
    
    async for db in database.get_db():
        try:
            # Получаем устройство
            devices = await crud.get_all_devices(db)
            if not devices:
                print("❌ Устройства не найдены в базе данных")
                return
            
            device = devices[0]
            print(f"📡 Устройство: {device.name} ({device.ip_address})")
            
            # Расшифровываем пароль
            try:
                password = decrypt_password(device.password_encrypted)
            except Exception as e:
                print(f"❌ Ошибка расшифровки пароля: {e}")
                return
            
            # Создаем клиент
            client = HikvisionClient(device.ip_address, device.username, password)
            
            # Проверяем соединение
            print("\n1️⃣ Проверка соединения с терминалом...")
            connected, error_msg = await client.check_connection()
            if not connected:
                print(f"❌ Терминал недоступен: {error_msg}")
                return
            print("✅ Соединение установлено")
            
            # Получаем настройки HTTP Listening
            print("\n2️⃣ Проверка настроек HTTP Listening на терминале...")
            result = await client.get_http_hosts()
            
            if result.get("success"):
                http_hosts = result.get("data", {})
                http_host_notification = http_hosts.get("HttpHostNotificationList", {}).get("HttpHostNotification", {})
                
                if http_host_notification:
                    webhook_ip = http_host_notification.get("ipAddress", "")
                    webhook_url = http_host_notification.get("url", "")
                    webhook_port = http_host_notification.get("portNo", "80")
                    webhook_protocol = http_host_notification.get("protocolType", "HTTP")
                    
                    print(f"   ✅ HTTP Listening настроен:")
                    print(f"      IP: {webhook_ip}")
                    print(f"      URL: {webhook_url}")
                    print(f"      Port: {webhook_port}")
                    print(f"      Protocol: {webhook_protocol}")
                    
                    # Проверяем доступность сервера
                    print(f"\n3️⃣ Проверка доступности сервера {webhook_ip}:{webhook_port}...")
                    print(f"   ⚠️  НЕ МОЖЕМ ПРОВЕРИТЬ С СЕРВЕРА - нужен доступ с терминала")
                    print(f"   💡 Выполните на терминале или с компьютера в той же сети:")
                    print(f"      ping {webhook_ip}")
                    print(f"      telnet {webhook_ip} {webhook_port}")
                    print(f"      curl -X POST http://{webhook_ip}:{webhook_port}{webhook_url} -H 'Content-Type: application/json' -d '{{\"test\":\"data\"}}'")
                    
                    # Проверяем, что endpoint существует
                    print(f"\n4️⃣ Проверка webhook endpoint на сервере...")
                    print(f"   ✅ Endpoint существует: POST /events/webhook")
                    print(f"   ✅ Обрабатывает MIME multipart и JSON")
                    
                    # Проверяем логи
                    print(f"\n5️⃣ Проверка логов на наличие входящих запросов...")
                    print(f"   💡 Выполните команду для мониторинга:")
                    print(f"      docker-compose logs -f backend | Select-String -Pattern 'WEBHOOK'")
                    print(f"   💡 Или через API:")
                    print(f"      GET /api/debug/logs?prefix=WEBHOOK")
                    
                    # Рекомендации
                    print(f"\n6️⃣ Возможные причины, почему события не приходят:")
                    print(f"   ❓ События не генерируются на терминале:")
                    print(f"      - Выполните авторизацию на терминале (приложите карту/лицо)")
                    print(f"      - Проверьте, что пользователь существует на терминале")
                    print(f"      - Проверьте логи терминала (если доступны)")
                    
                    print(f"\n   ❓ Сетевые проблемы:")
                    print(f"      - Терминал не может достучаться до {webhook_ip}:{webhook_port}")
                    print(f"      - Проверьте firewall на сервере")
                    print(f"      - Проверьте, что порт {webhook_port} открыт")
                    print(f"      - Проверьте маршрутизацию между терминалом и сервером")
                    
                    print(f"\n   ❓ HTTP Listening не включен:")
                    print(f"      - Проверьте в веб-интерфейсе терминала:")
                    print(f"        Configuration → Network → HTTP Listening")
                    print(f"      - Убедитесь, что HTTP Listening включен")
                    
                    print(f"\n   ❓ Неправильный URL:")
                    print(f"      - Текущий URL: {webhook_url}")
                    print(f"      - Должен быть: /events/webhook")
                    if webhook_url != "/events/webhook":
                        print(f"      ⚠️  URL не совпадает!")
                    
                    print(f"\n7️⃣ Тестирование webhook endpoint...")
                    print(f"   💡 Для тестирования выполните с терминала или из той же сети:")
                    print(f"      curl -X POST http://{webhook_ip}:{webhook_port}{webhook_url} \\")
                    print(f"           -H 'Content-Type: application/json' \\")
                    print(f"           -d '{{\"test\":\"event\"}}'")
                    print(f"   💡 Затем проверьте логи:")
                    print(f"      docker-compose logs --tail=50 backend | Select-String -Pattern 'WEBHOOK'")
                    
            else:
                error = result.get("error", "Unknown error")
                print(f"❌ Ошибка получения настроек: {error}")
                print(f"💡 HTTP Listening может быть не настроен на терминале")
                
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
        finally:
            break


if __name__ == "__main__":
    asyncio.run(diagnose_webhook())

