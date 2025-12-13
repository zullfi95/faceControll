"""
Скрипт для выполнения миграции базы данных - добавление новых полей в attendance_events.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database import engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_migration():
    """Выполнение миграции для добавления новых полей в attendance_events."""
    
    migration_sql = """
    -- Добавление новых полей в таблицу attendance_events
    
    -- Делаем user_id nullable
    ALTER TABLE attendance_events 
        ALTER COLUMN user_id DROP NOT NULL;
    
    -- Добавляем новые поля
    ALTER TABLE attendance_events 
        ADD COLUMN IF NOT EXISTS employee_no VARCHAR,
        ADD COLUMN IF NOT EXISTS name VARCHAR,
        ADD COLUMN IF NOT EXISTS card_no VARCHAR,
        ADD COLUMN IF NOT EXISTS card_reader_id VARCHAR,
        ADD COLUMN IF NOT EXISTS event_type_code VARCHAR,
        ADD COLUMN IF NOT EXISTS event_type_description VARCHAR,
        ADD COLUMN IF NOT EXISTS remote_host_ip VARCHAR;
    
    -- Создание индекса для employee_no
    CREATE INDEX IF NOT EXISTS ix_attendance_events_employee_no ON attendance_events(employee_no);
    """
    
    try:
        logger.info("Подключение к базе данных...")
        async with engine.begin() as conn:
            logger.info("Выполнение миграции...")
            
            # Выполняем SQL команды по отдельности для лучшей обработки ошибок
            commands = [
                "ALTER TABLE attendance_events ALTER COLUMN user_id DROP NOT NULL",
                """ALTER TABLE attendance_events 
                   ADD COLUMN IF NOT EXISTS employee_no VARCHAR,
                   ADD COLUMN IF NOT EXISTS name VARCHAR,
                   ADD COLUMN IF NOT EXISTS card_no VARCHAR,
                   ADD COLUMN IF NOT EXISTS card_reader_id VARCHAR,
                   ADD COLUMN IF NOT EXISTS event_type_code VARCHAR,
                   ADD COLUMN IF NOT EXISTS event_type_description VARCHAR,
                   ADD COLUMN IF NOT EXISTS remote_host_ip VARCHAR""",
                "CREATE INDEX IF NOT EXISTS ix_attendance_events_employee_no ON attendance_events(employee_no)"
            ]
            
            for i, command in enumerate(commands, 1):
                try:
                    logger.info(f"Выполнение команды {i}/{len(commands)}...")
                    await conn.execute(text(command))
                    logger.info(f"✓ Команда {i} выполнена успешно")
                except Exception as e:
                    # Если колонка уже существует или индекс уже есть - это нормально
                    if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                        logger.warning(f"⚠ Команда {i}: {e}")
                    else:
                        logger.error(f"✗ Ошибка в команде {i}: {e}")
                        raise
            
            logger.info("✓ Миграция выполнена успешно!")
            
            # Проверяем, что поля добавлены
            logger.info("\nПроверка структуры таблицы...")
            result = await conn.execute(text("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'attendance_events'
                ORDER BY ordinal_position
            """))
            
            columns = result.fetchall()
            logger.info(f"Найдено колонок: {len(columns)}")
            
            new_fields = ['employee_no', 'name', 'card_no', 'card_reader_id', 
                         'event_type_code', 'event_type_description', 'remote_host_ip']
            existing_fields = [col[0] for col in columns]
            
            logger.info("\nНовые поля:")
            for field in new_fields:
                if field in existing_fields:
                    logger.info(f"  ✓ {field}")
                else:
                    logger.warning(f"  ✗ {field} - не найдено!")
            
    except Exception as e:
        logger.error(f"Ошибка при выполнении миграции: {e}", exc_info=True)
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(run_migration())
    if success:
        print("\n" + "="*80)
        print("✅ Миграция выполнена успешно!")
        print("="*80)
        sys.exit(0)
    else:
        print("\n" + "="*80)
        print("❌ Ошибка при выполнении миграции")
        print("="*80)
        sys.exit(1)

