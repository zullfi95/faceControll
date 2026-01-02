#!/usr/bin/env python3
"""
Скрипт для выполнения Alembic миграций базы данных.

Использование:
    python run_migration.py          # Применить все ожидающие миграции
    python run_migration.py --check  # Проверить статус миграций
    python run_migration.py --init   # Инициализировать базу данных (для новых установок)
"""

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

# Путь к директории backend
backend_dir = Path(__file__).parent
alembic_dir = backend_dir / "alembic"


def run_alembic_command(command_args):
    """Выполнение команды Alembic."""
    cmd = [sys.executable, "-m", "alembic"] + command_args
    try:
        result = subprocess.run(cmd, cwd=backend_dir, check=True, capture_output=True, text=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Ошибка выполнения команды: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False


def check_migration_status():
    """Проверка статуса миграций."""
    print("Проверка статуса миграций...")
    return run_alembic_command(["current"])


def run_migrations():
    """Применение всех ожидающих миграций."""
    print("Применение миграций...")
    return run_alembic_command(["upgrade", "head"])


def init_database():
    """Инициализация базы данных для новых установок."""
    print("Инициализация базы данных...")
    success = run_alembic_command(["upgrade", "head"])
    if success:
        print("✅ База данных инициализирована успешно!")
    return success


def main():
    parser = argparse.ArgumentParser(description="Управление миграциями базы данных")
    parser.add_argument("--check", action="store_true",
                       help="Проверить статус миграций без применения")
    parser.add_argument("--init", action="store_true",
                       help="Инициализировать базу данных (для новых установок)")

    args = parser.parse_args()

    if args.check:
        success = check_migration_status()
    elif args.init:
        success = init_database()
    else:
        success = run_migrations()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

