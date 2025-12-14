#!/usr/bin/env python3
"""
Скрипт для создания рабочей смены.
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.database import DATABASE_URL, Base
from app import crud, schemas

async def create_work_shift():
    """Создает новую рабочую смену."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            print("🔄 Создаем новую рабочую смену...")

            # Создаем смену с рабочим графиком
            shift_data = schemas.WorkShiftCreate(
                name="Дневная смена",
                description="Стандартная дневная смена с 9:00 до 18:00",
                schedule={
                    # Понедельник (0) - Пятница (4): 9:00 - 18:00
                    "0": {"start": "09:00", "end": "18:00", "enabled": True},  # Понедельник
                    "1": {"start": "09:00", "end": "18:00", "enabled": True},  # Вторник
                    "2": {"start": "09:00", "end": "18:00", "enabled": True},  # Среда
                    "3": {"start": "09:00", "end": "18:00", "enabled": True},  # Четверг
                    "4": {"start": "09:00", "end": "18:00", "enabled": True},  # Пятница
                    # Суббота (5) и Воскресенье (6): отключены
                    "5": {"start": "09:00", "end": "18:00", "enabled": False},  # Суббота
                    "6": {"start": "09:00", "end": "18:00", "enabled": False},  # Воскресенье
                },
                is_active=True
            )

            # Создаем смену в БД
            shift = await crud.create_work_shift(session, shift_data)

            if shift:
                print("✅ Смена создана успешно!")
                print(f"   ID: {shift.id}")
                print(f"   Название: {shift.name}")
                print(f"   Описание: {shift.description}")
                print(f"   Активна: {shift.is_active}")
                print("   График работы:")
                for day, schedule in shift.schedule.items():
                    day_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
                    day_name = day_names[int(day)] if int(day) < len(day_names) else f"День {day}"
                    status = "✅" if schedule["enabled"] else "❌"
                    print(f"     {day_name}: {schedule['start']} - {schedule['end']} {status}")
            else:
                print("❌ Не удалось создать смену")

        except Exception as e:
            print(f"❌ Ошибка при создании смены: {e}")
            raise
        finally:
            await session.close()
            await engine.dispose()

if __name__ == "__main__":
    print("🕒 Скрипт создания рабочей смены")
    print("=" * 40)

    # Запуск создания смены
    asyncio.run(create_work_shift())
