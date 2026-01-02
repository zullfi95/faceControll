"""
Скрипт для исправления terminal_ip в существующих событиях.
Использует remote_host_ip, если terminal_ip = 172.18.0.1 (Docker network IP).
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import get_db
from app import models
from sqlalchemy import select, update

async def fix_terminal_ip():
    """Исправляем terminal_ip в существующих событиях."""
    async for db in get_db():
        try:
            # Находим события с неправильным terminal_ip (Docker network IP)
            query = select(models.AttendanceEvent).filter(
                models.AttendanceEvent.terminal_ip == "172.18.0.1"
            )
            result = await db.execute(query)
            events = result.scalars().all()
            
            print(f"📊 Найдено {len(events)} событий с terminal_ip = 172.18.0.1")
            
            fixed_count = 0
            for event in events:
                if event.remote_host_ip and event.remote_host_ip != "172.18.0.1":
                    # Обновляем terminal_ip на remote_host_ip
                    await db.execute(
                        update(models.AttendanceEvent)
                        .where(models.AttendanceEvent.id == event.id)
                        .values(terminal_ip=event.remote_host_ip)
                    )
                    fixed_count += 1
                    print(f"✅ Событие {event.id}: {event.terminal_ip} -> {event.remote_host_ip}")
            
            await db.commit()
            print(f"\n✅ Исправлено {fixed_count} событий")
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            await db.rollback()
        finally:
            break

if __name__ == "__main__":
    asyncio.run(fix_terminal_ip())
