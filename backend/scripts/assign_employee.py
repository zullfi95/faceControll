#!/usr/bin/env python3
"""
Скрипт для привязки сотрудника к рабочей смене.
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.database import DATABASE_URL, Base
from app import crud, schemas
from datetime import datetime, timezone

async def list_users():
    """Показывает список всех пользователей."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            users = await crud.get_users(session, skip=0, limit=100)
            print(f"📋 Найдено {len(users)} пользователей:")
            for user in users:
                print(f"   ID: {user.id}, Hikvision ID: {user.hikvision_id}, Имя: {user.full_name}, Активен: {user.is_active}")
            return users
        finally:
            await session.close()
            await engine.dispose()

async def list_shifts():
    """Показывает список всех смен."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            shifts = await crud.get_all_work_shifts(session)
            print(f"📋 Найдено {len(shifts)} смен:")
            for shift in shifts:
                print(f"   ID: {shift.id}, Название: {shift.name}, Активна: {shift.is_active}")
            return shifts
        finally:
            await session.close()
            await engine.dispose()

async def assign_employee_to_shift(user_id: int, shift_id: int):
    """Привязывает сотрудника к смене."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            print(f"🔄 Привязываем пользователя {user_id} к смене {shift_id}...")

            # Проверяем, существует ли пользователь
            user = await crud.get_user_by_id(session, user_id)
            if not user:
                print(f"❌ Пользователь с ID {user_id} не найден")
                return False

            # Проверяем, существует ли смена
            shift = await crud.get_work_shift_by_id(session, shift_id)
            if not shift:
                print(f"❌ Смена с ID {shift_id} не найдена")
                return False

            # Создаем привязку
            assignment_data = schemas.UserShiftAssignmentCreate(
                user_id=user_id,
                shift_id=shift_id,
                start_date=datetime.now(timezone.utc),  # Начинаем с сегодняшнего дня
                end_date=None,  # Бессрочно
                is_active=True
            )

            assignment = await crud.create_user_shift_assignment(session, assignment_data)

            if assignment:
                print("✅ Привязка создана успешно!")
                print(f"   ID привязки: {assignment.id}")
                print(f"   Пользователь: {user.full_name} (ID: {user.id})")
                print(f"   Смена: {shift.name} (ID: {shift.id})")
                print(f"   Дата начала: {assignment.start_date}")
                print(f"   Активна: {assignment.is_active}")
                return True
            else:
                print("❌ Не удалось создать привязку")
                return False

        except Exception as e:
            print(f"❌ Ошибка при создании привязки: {e}")
            return False
        finally:
            await session.close()
            await engine.dispose()

async def main():
    print("👥 Скрипт привязки сотрудника к смене")
    print("=" * 45)

    # Показываем список пользователей
    print("\n👤 Доступные пользователи:")
    users = await list_users()

    # Показываем список смен
    print("\n🕒 Доступные смены:")
    shifts = await list_shifts()

    if not users:
        print("❌ Нет доступных пользователей. Сначала создайте пользователя.")
        return

    if not shifts:
        print("❌ Нет доступных смен. Сначала создайте смену.")
        return

    # Выбираем первого активного пользователя и первую активную смену
    active_users = [u for u in users if u.is_active]
    active_shifts = [s for s in shifts if s.is_active]

    if not active_users:
        print("❌ Нет активных пользователей.")
        return

    if not active_shifts:
        print("❌ Нет активных смен.")
        return

    # Автоматически выбираем первого пользователя и смену
    selected_user = active_users[0]
    selected_shift = active_shifts[0]

    print(f"\n🎯 Автоматический выбор:")
    print(f"   Пользователь: {selected_user.full_name} (ID: {selected_user.id})")
    print(f"   Смена: {selected_shift.name} (ID: {selected_shift.id})")

    # Создаем привязку
    success = await assign_employee_to_shift(selected_user.id, selected_shift.id)
    if success:
        print("\n🎉 Привязка сотрудника к смене завершена успешно!")
    else:
        print("\n❌ Не удалось привязать сотрудника к смене.")

if __name__ == "__main__":
    asyncio.run(main())
