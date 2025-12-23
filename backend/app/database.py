from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

# echo=False to reduce SQL noise in logs
engine = create_async_engine(settings.database_url, echo=False)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def get_db_session():
    """
    Генератор для получения сессий БД в фоновых задачах.
    Используется в event_service и автоматических задачах.
    """
    async with AsyncSessionLocal() as session:
        yield session

