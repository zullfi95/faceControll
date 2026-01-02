#!/usr/bin/env python3
import asyncio
import sys
from datetime import datetime
sys.path.insert(0, '/app')
from app.database import get_db
from app import models
from sqlalchemy import select, desc

async def check():
    async for db in get_db():
        # Получаем последнее событие
        result = await db.execute(
            select(models.AttendanceEvent)
            .order_by(desc(models.AttendanceEvent.timestamp))
            .limit(1)
        )
        event = result.scalar_one_or_none()
        
        if event:
            print(f"📅 Последнее событие:")
            print(f"   ID: {event.id}")
            print(f"   Дата и время: {event.timestamp}")
            print(f"   UTC: {event.timestamp}")
            if event.timestamp:
                local_time = event.timestamp.astimezone()
                print(f"   Локальное время: {local_time}")
            print(f"   employee_no: {event.employee_no}")
            print(f"   name: {event.name}")
            print(f"   terminal_ip: {event.terminal_ip}")
        else:
            print("❌ События не найдены")
        break

asyncio.run(check())
