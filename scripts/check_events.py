#!/usr/bin/env python3
"""
Простой скрипт для проверки последних событий в базе данных
"""
import asyncio
import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, '/app')

from app.database import get_db
from app import crud

async def check_events():
    """Проверяем последние события."""
    async for db in get_db():
        try:
            # Получаем последние 10 событий
            events, total_count = await crud.get_events(db, limit=10)
            print(f"\n📊 Найдено {len(events)} последних событий в базе данных:")

            if events:
                for i, event in enumerate(events, 1):
                    print(f"{i}. {event.timestamp} | {event.employee_no or 'N/A'} | {event.event_type} | {event.terminal_ip}")
            else:
                print("❌ События не найдены в базе данных")

            # Проверяем общее количество событий
            print(f"\n📈 Всего событий в базе: {total_count}")

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
        finally:
            break

if __name__ == "__main__":
    asyncio.run(check_events())
