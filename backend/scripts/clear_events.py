#!/usr/bin/env python3
"""
Скрипт для очистки всех событий посещаемости из базы данных.
Удаляет все события (attendance_events), но сохраняет:
- Пользователей (users)
- Смены (work_shifts)
- Привязки пользователей к сменам (user_shift_assignments)
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import delete, select
from app.database import DATABASE_URL
from app import models

async def clear_all_events():
    """Удаляет все события посещаемости."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            print("🔄 Начинаем очистку событий посещаемости...")

            # Подсчитываем количество событий перед удалением
            count_result = await session.execute(select(models.AttendanceEvent))
            total_events = len(count_result.scalars().all())
            print(f"📋 Найдено {total_events} событий посещаемости")

            if total_events == 0:
                print("✅ Событий для удаления не найдено")
                return

            # Удаляем все события
            delete_result = await session.execute(delete(models.AttendanceEvent))
            deleted_count = delete_result.rowcount

            await session.commit()

            print(f"✅ Успешно удалено {deleted_count} событий")
            print("✅ Пользователи и смены сохранены")

        except Exception as e:
            print(f"❌ Ошибка при очистке событий: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()
            await engine.dispose()

if __name__ == "__main__":
    print("🧹 Скрипт очистки событий посещаемости")
    print("=" * 50)
    print("⚠️  ВНИМАНИЕ: Это действие удалит ВСЕ события посещаемости!")
    print("   Пользователи и смены будут сохранены.")
    print("=" * 50)

    # Проверяем аргумент командной строки или переменную окружения
    confirm = None
    if len(sys.argv) > 1:
        confirm = sys.argv[1]
    elif os.getenv("CONFIRM_CLEAR_EVENTS"):
        confirm = os.getenv("CONFIRM_CLEAR_EVENTS")
    else:
        # Интерактивный режим только если запущено не в Docker
        try:
            confirm = input("\nПродолжить? (yes/no): ")
        except (EOFError, KeyboardInterrupt):
            print("\n❌ Операция отменена (нет интерактивного ввода).")
            print("   Используйте: python clear_events.py yes")
            sys.exit(0)

    if confirm and confirm.lower() not in ['yes', 'y', 'да', 'д']:
        print("❌ Операция отменена.")
        sys.exit(0)

    # Запуск очистки
    asyncio.run(clear_all_events())
    print("\n🎉 Очистка завершена успешно!")

