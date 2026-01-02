import pytest
import asyncio
import sys
import os
from unittest.mock import patch, MagicMock

# Добавляем путь к приложению
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock для settings до импорта любых модулей приложения
mock_settings = MagicMock()
mock_settings.database_url = "sqlite+aiosqlite:///./test.db"
mock_settings.encryption_key = "test-encryption-key-for-testing-only"
mock_settings.jwt_secret_key = "test-jwt-secret-key-for-testing-only"
mock_settings.webhook_api_key = "test-webhook-api-key"
mock_settings.environment = "testing"
mock_settings.terminal_in_ip = "10.0.0.100"
mock_settings.is_production.return_value = False
mock_settings.is_development.return_value = True

# Патчим settings
with patch('app.config.settings', mock_settings):
    # Теперь можно безопасно импортировать
    from app.database import Base
    from app.main import app


@pytest.fixture(scope="session")
async def test_engine():
    """Создание тестовой базы данных."""
    engine = create_async_engine(test_settings.database_url, echo=False)

    # Создаем все таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Очистка после тестов
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def db_session(test_engine):
    """Фикстура для сессии базы данных."""
    async_session = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session
        await session.rollback()  # Откатываем изменения после каждого теста


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_app() -> FastAPI:
    """Фикстура для FastAPI приложения."""
    return app


@pytest.fixture(scope="session")
async def client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Фикстура для HTTP клиента."""
    async with AsyncClient(app=test_app, base_url="http://testserver") as client:
        yield client


@pytest.fixture(scope="session")
async def db_session():
    """Фикстура для сессии базы данных."""
    async for session in get_db_session():
        yield session
        break
