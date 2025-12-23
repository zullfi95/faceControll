#!/usr/bin/env python3
"""Скрипт для проверки привязок пользователей к сменам."""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from datetime import datetime, time, timezone
from app.database import DATABASE_URL
from app import models

async def check_shifts():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # Получаем все привязки
            assignments_result = await session.execute(
                select(models.UserShiftAssignment)
                .join(models.WorkShift)
                .join(models.User)
            )
            assignments = assignments_result.scalars().unique().all()
            
            print(f"Total assignments: {len(assignments)}")
            
            for assignment in assignments:
                print(f"\nAssignment ID: {assignment.id}")
                print(f"  User: {assignment.user.full_name} (ID: {assignment.user.id})")
                print(f"  Shift: {assignment.shift.name} (ID: {assignment.shift.id})")
                print(f"  Is Active: {assignment.is_active}")
                print(f"  Shift Is Active: {assignment.shift.is_active}")
                print(f"  Start Date: {assignment.start_date}")
                print(f"  End Date: {assignment.end_date}")
                print(f"  Schedule: {assignment.shift.schedule}")
            
            # Проверяем для сегодняшней даты
            today = datetime.now(timezone.utc)
            today_date = today.date()
            
            print(f"\n\nChecking for date: {today_date}")
            
            for assignment in assignments:
                if assignment.is_active and assignment.shift.is_active:
                    # Проверяем даты
                    start_ok = assignment.start_date is None or assignment.start_date.date() <= today_date
                    end_ok = assignment.end_date is None or assignment.end_date.date() >= today_date
                    
                    if start_ok and end_ok:
                        # Проверяем расписание
                        weekday = str(today.weekday())
                        schedule = assignment.shift.schedule
                        
                        if schedule and weekday in schedule:
                            day_schedule = schedule[weekday]
                            enabled = day_schedule.get("enabled", False)
                            
                            print(f"\n✓ User {assignment.user.full_name} has active shift '{assignment.shift.name}' for {today_date}")
                            print(f"  Day schedule enabled: {enabled}")
                            if enabled:
                                print(f"  Start: {day_schedule.get('start')}")
                                print(f"  End: {day_schedule.get('end')}")
                        else:
                            print(f"\n✗ User {assignment.user.full_name} - shift '{assignment.shift.name}' not enabled for weekday {weekday}")
                    else:
                        print(f"\n✗ User {assignment.user.full_name} - assignment dates don't match")
                        print(f"  Start OK: {start_ok}, End OK: {end_ok}")
            
        finally:
            await session.close()
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_shifts())


