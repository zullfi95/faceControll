#!/usr/bin/env python3
"""
Скрипт для закрытия старых незакрытых сессий
"""
import asyncio
import sys
from datetime import datetime, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, 'E:/FaceControll/backend')

from app.database import SessionLocal, engine
from app import models

async def close_old_unclosed_sessions():
    """Закрываем старые незакрытые сессии"""
    async with SessionLocal() as db:
        print("=" * 60)
        print("ЗАКРЫТИЕ СТАРЫХ НЕЗАКРЫТЫХ СЕССИЙ")
        print("=" * 60)
        print()
        
        # Получаем все события
        result = await db.execute(
            select(models.AttendanceEvent)
            .order_by(models.AttendanceEvent.timestamp.desc())
        )
        events = result.scalars().all()
        
        if not events:
            print("❌ Нет событий в системе")
            return
        
        print(f"📊 Всего событий: {len(events)}")
        print()
        
        # Группируем по пользователям
        users_events = {}
        for event in events:
            if event.user_id:
                if event.user_id not in users_events:
                    users_events[event.user_id] = []
                users_events[event.user_id].append(event)
        
        # Проверяем каждого пользователя
        for user_id, user_events in users_events.items():
            user_events.sort(key=lambda e: e.timestamp)
            
            # Получаем имя пользователя
            user_result = await db.execute(
                select(models.User).filter(models.User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            user_name = user.full_name if user and user.full_name else f"User #{user_id}"
            
            # Ищем последнее событие
            last_event = user_events[-1]
            
            # Проверяем, есть ли незакрытая сессия
            if last_event.event_type == "entry":
                entry_date = last_event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                days_ago = (datetime.now() - last_event.timestamp.replace(tzinfo=None)).days
                
                print(f"⚠️  {user_name}")
                print(f"   Последний вход: {entry_date} ({days_ago} дней назад)")
                print(f"   Статус: НЕЗАКРЫТАЯ СЕССИЯ")
                
                # Если сессия старше 1 дня - предлагаем закрыть
                if days_ago >= 1:
                    print(f"   🔨 Создаем событие выхода...")
                    
                    # Закрываем концом рабочего дня (18:00)
                    exit_time = last_event.timestamp.replace(hour=18, minute=0, second=0)
                    
                    # Создаем событие выхода
                    exit_event = models.AttendanceEvent(
                        user_id=user_id,
                        employee_no=last_event.employee_no,
                        name=last_event.name,
                        event_type="exit",
                        event_type_description="Auto-closed by system",
                        timestamp=exit_time,
                        device_id=last_event.device_id,
                        device_name=last_event.device_name,
                        card_no=last_event.card_no
                    )
                    
                    db.add(exit_event)
                    print(f"   ✅ Добавлено событие выхода: {exit_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                print()
            else:
                print(f"✅ {user_name}")
                print(f"   Последнее событие: выход {last_event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"   Статус: OK")
                print()
        
        # Сохраняем изменения
        await db.commit()
        
        print("=" * 60)
        print("✅ ГОТОВО!")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(close_old_unclosed_sessions())

