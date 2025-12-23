#!/usr/bin/env python3
"""Скрипт для проверки данных в базе."""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.database import DATABASE_URL
from app import models

async def check_data():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            users_result = await session.execute(select(models.User))
            users = users_result.scalars().all()
            
            shifts_result = await session.execute(select(models.WorkShift))
            shifts = shifts_result.scalars().all()
            
            events_result = await session.execute(select(models.AttendanceEvent))
            events = events_result.scalars().all()
            
            print(f"Users: {len(users)}")
            print(f"Shifts: {len(shifts)}")
            print(f"Events: {len(events)}")
            
        finally:
            await session.close()
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_data())

