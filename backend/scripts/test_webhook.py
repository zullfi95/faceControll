#!/usr/bin/env python3
"""
Скрипт для тестирования webhook эндпоинта.
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from datetime import datetime, timezone

async def test_webhook():
    """Тестирует webhook эндпоинт."""
    try:
        print("🔄 Тестируем webhook эндпоинт...")

        # Создаем тестовые данные события
        test_event = {
            "AccessControllerEvent": {
                "employeeNoString": "1001",
                "name": "Test User",
                "eventType": "entry",
                "cardReaderNo": "1",
                "eventTime": datetime.now(timezone.utc).isoformat(),
                "deviceID": "test-device"
            }
        }

        print(f"📤 Отправляем тестовое событие: {test_event}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost/api/events/webhook",
                json=test_event,
                headers={"Content-Type": "application/json"},
                timeout=10.0
            )

            print(f"📥 Ответ сервера: {response.status_code}")
            print(f"📄 Тело ответа: {response.text}")

            if response.status_code == 200:
                print("✅ Webhook работает корректно!")
            else:
                print("❌ Webhook вернул ошибку")

    except Exception as e:
        print(f"❌ Ошибка при тестировании webhook: {e}")

if __name__ == "__main__":
    print("🪝 Скрипт тестирования webhook")
    print("=" * 35)

    asyncio.run(test_webhook())
