#!/usr/bin/env python3
"""
Скрипт для очистки данных смен и привязок из базы данных.
Удаляет все рабочие смены и привязки пользователей к сменам.
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.database import DATABASE_URL, Base
from app import crud

async def clear_all_shifts_and_assignments():
    """Удаляет все смены и привязки пользователей к сменам."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            print("🔄 Начинаем очистку данных смен...")

            # Получаем все привязки пользователей к сменам
            assignments = await crud.get_user_shift_assignments(session)
            print(f"📋 Найдено {len(assignments)} привязок пользователей к сменам")

            # Удаляем все привязки
            for assignment in assignments:
                success = await crud.delete_user_shift_assignment(session, assignment.id)
                if success:
                    print(f"✅ Удалена привязка ID {assignment.id} (пользователь {assignment.user_id} -> смена {assignment.shift_id})")
                else:
                    print(f"❌ Не удалось удалить привязку ID {assignment.id}")

            # Получаем все смены
            shifts = await crud.get_all_work_shifts(session)
            print(f"📋 Найдено {len(shifts)} рабочих смен")

            # Удаляем все смены
            for shift in shifts:
                success = await crud.delete_work_shift(session, shift.id)
                if success:
                    print(f"✅ Удалена смена '{shift.name}' (ID {shift.id})")
                else:
                    print(f"❌ Не удалось удалить смену '{shift.name}' (ID {shift.id})")

            print("🎉 Очистка завершена успешно!")

        except Exception as e:
            print(f"❌ Ошибка при очистке данных: {e}")
            raise
        finally:
            await session.close()
            await engine.dispose()

if __name__ == "__main__":
    print("🧹 Скрипт очистки данных смен")
    print("=" * 40)

    # Подтверждение действия
    confirm = input("⚠️  ВНИМАНИЕ: Это действие удалит ВСЕ смены и привязки пользователей к сменам!\nПродолжить? (yes/no): ")

    if confirm.lower() not in ['yes', 'y', 'да', 'д']:
        print("❌ Операция отменена.")
        sys.exit(0)

    # Запуск очистки
    asyncio.run(clear_all_shifts_and_assignments())
