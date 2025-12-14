#!/usr/bin/env python3
"""
Скрипт для тестирования WebSocket соединений.
"""

import asyncio
import websockets
import json
import sys

async def test_websocket(url):
    """Тестирует WebSocket соединение."""
    try:
        print(f"🔌 Подключаюсь к WebSocket: {url}")

        async with websockets.connect(url) as websocket:
            print("✅ Соединение установлено!")

            # Отправляем начальное сообщение
            await websocket.send(json.dumps({"type": "connected"}))
            print("📤 Отправлено начальное сообщение")

            # Ждем ответа
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📥 Получен ответ: {response}")
            except asyncio.TimeoutError:
                print("⏰ Таймаут ожидания ответа")

            # Ждем немного и закрываем
            await asyncio.sleep(2)
            print("🔌 Закрываем соединение")

    except Exception as e:
        print(f"❌ Ошибка WebSocket: {e}")

async def main():
    print("🧪 Тестирование WebSocket соединений")
    print("=" * 40)

    # Тестируем events WebSocket
    events_url = "ws://localhost/api/ws/events"
    await test_websocket(events_url)

    print()

    # Тестируем reports WebSocket
    reports_url = "ws://localhost/api/ws/reports"
    await test_websocket(reports_url)

if __name__ == "__main__":
    asyncio.run(main())

