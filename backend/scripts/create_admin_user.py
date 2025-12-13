"""
Скрипт для создания администратора системы.
Использование: python scripts/create_admin_user.py
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import database
from app.crud import create_system_user, get_system_user_by_username
from app.schemas import SystemUserCreate


async def main():
    """Создание администратора."""
    async for db in database.get_db():
        try:
            # Проверяем, не существует ли уже пользователь
            existing = await get_system_user_by_username(db, "admin")
            if existing:
                print("✅ Пользователь 'admin' уже существует")
                break
            
            # Создаем пользователя Operations Manager
            admin_user = SystemUserCreate(
                username="admin",
                email="admin@example.com",
                full_name="Administrator",
                role="operations_manager",
                password="admin123",
                is_active=True
            )
            
            user = await create_system_user(db, admin_user)
            print(f"✅ Администратор создан успешно!")
            print(f"   Username: {user.username}")
            print(f"   Role: {user.role}")
            print(f"   Password: admin123")
            break
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            break


if __name__ == "__main__":
    asyncio.run(main())

