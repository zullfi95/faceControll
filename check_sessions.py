#!/usr/bin/env python3
import asyncio
from datetime import datetime
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app import models

async def check_sessions():
    async with AsyncSessionLocal() as db:
        # Получаем последние 20 событий
        result = await db.execute(
            select(models.AttendanceEvent)
            .order_by(models.AttendanceEvent.timestamp.desc())
            .limit(20)
        )
        events = result.scalars().all()
        
        print('Последние 20 событий:')
        print('-' * 90)
        print(f'{"Время":<20} | {"Имя":<15} | {"Тип":<7} | {"Терминал IP":<15}')
        print('-' * 90)
        for e in events:
            ts = e.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            name = (e.name or 'N/A')[:15]
            event_type = (e.event_type or 'N/A')[:7]
            term_ip = e.terminal_ip or 'N/A'
            print(f'{ts:<20} | {name:<15} | {event_type:<7} | {term_ip:<15}')
        print('-' * 90)
        
        # Проверяем незакрытые сессии
        print('\nНезакрытые сессии:')
        print('-' * 90)
        result = await db.execute(select(models.User))
        users = result.scalars().all()
        
        unclosed_count = 0
        for user in users:
            result = await db.execute(
                select(models.AttendanceEvent)
                .filter(models.AttendanceEvent.user_id == user.id)
                .order_by(models.AttendanceEvent.timestamp.desc())
                .limit(1)
            )
            last_event = result.scalar_one_or_none()
            
            if last_event and last_event.event_type == 'entry':
                days_ago = (datetime.now() - last_event.timestamp.replace(tzinfo=None)).days
                ts = last_event.timestamp.strftime("%Y-%m-%d %H:%M")
                name = user.full_name or user.hikvision_id or f'User#{user.id}'
                print(f'{name:<20} | Последний вход: {ts} ({days_ago} дн. назад)')
                unclosed_count += 1
        
        if unclosed_count == 0:
            print('✅ Нет незакрытых сессий')
        else:
            print('-' * 90)
            print(f'⚠️  Всего незакрытых сессий: {unclosed_count}')
            print('\n💡 Совет: Добавьте событие выхода для закрытия старых сессий')

asyncio.run(check_sessions())
