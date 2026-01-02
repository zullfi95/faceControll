#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, '/app')
from app.database import get_db
from app import models
from sqlalchemy import select

async def check():
    async for db in get_db():
        # Проверяем события с правильным IP
        result = await db.execute(
            select(models.AttendanceEvent)
            .filter(models.AttendanceEvent.terminal_ip == '192.168.1.122')
            .limit(5)
        )
        events = result.scalars().all()
        print(f'✅ Найдено событий с terminal_ip=192.168.1.122: {len(events)}')
        
        # Проверяем события со старым IP
        result_old = await db.execute(
            select(models.AttendanceEvent)
            .filter(models.AttendanceEvent.terminal_ip == '172.18.0.1')
            .limit(1)
        )
        old_events = result_old.scalars().all()
        print(f'⚠️  Событий со старым IP (172.18.0.1): {len(old_events)}')
        
        if events:
            e = events[0]
            print(f'\n📊 Пример события:')
            print(f'   ID: {e.id}')
            print(f'   terminal_ip: {e.terminal_ip}')
            print(f'   remote_host_ip: {e.remote_host_ip}')
            print(f'   employee_no: {e.employee_no}')
            print(f'   name: {e.name}')
        break

asyncio.run(check())
