#!/usr/bin/env python3
"""
Скрипт для закрытия старых незакрытых сессий
Закрывает концом рабочего дня (18:00)
"""
import asyncio
from datetime import datetime, time, timedelta
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app import models

async def close_old_sessions():
    async with AsyncSessionLocal() as db:
        print('=' * 90)
        print('ЗАКРЫТИЕ СТАРЫХ НЕЗАКРЫТЫХ СЕССИЙ')
        print('=' * 90)
        print()
        
        # Получаем всех пользователей
        result = await db.execute(select(models.User))
        users = result.scalars().all()
        
        closed_count = 0
        
        for user in users:
            # Получаем последнее событие пользователя
            result = await db.execute(
                select(models.AttendanceEvent)
                .filter(models.AttendanceEvent.user_id == user.id)
                .order_by(models.AttendanceEvent.timestamp.desc())
                .limit(1)
            )
            last_event = result.scalar_one_or_none()
            
            if last_event and last_event.event_type == 'entry':
                days_ago = (datetime.now() - last_event.timestamp.replace(tzinfo=None)).days
                
                # Закрываем только если сессия старше 1 дня
                if days_ago >= 1:
                    name = user.full_name or user.hikvision_id or f'User#{user.id}'
                    entry_ts = last_event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    
                    print(f'🔍 Найдена незакрытая сессия:')
                    print(f'   Пользователь: {name}')
                    print(f'   Вход: {entry_ts} ({days_ago} дн. назад)')
                    
                    # Закрываем концом рабочего дня (18:00)
                    exit_time = last_event.timestamp.replace(
                        hour=18, minute=0, second=0, microsecond=0
                    )
                    
                    # Создаем событие выхода
                    exit_event = models.AttendanceEvent(
                        user_id=user.id,
                        employee_no=last_event.employee_no,
                        name=last_event.name,
                        event_type='exit',
                        event_type_description='Auto-closed by system',
                        timestamp=exit_time,
                        terminal_ip=last_event.terminal_ip,
                        card_no=last_event.card_no
                    )
                    
                    db.add(exit_event)
                    closed_count += 1
                    
                    exit_ts = exit_time.strftime("%Y-%m-%d %H:%M:%S")
                    print(f'   ✅ Создано событие выхода: {exit_ts}')
                    print()
        
        if closed_count > 0:
            await db.commit()
            print('=' * 90)
            print(f'✅ Закрыто сессий: {closed_count}')
            print('=' * 90)
        else:
            print('✅ Нет старых незакрытых сессий для закрытия')
            print('=' * 90)

asyncio.run(close_old_sessions())

