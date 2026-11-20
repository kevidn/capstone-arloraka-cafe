"""Database connection plumbing (scaffolding only).

This module only prepares the SQLAlchemy async engine and session factory.
It does **not** define any models, run any migrations, or open a connection
until it is actually used. Full database work happens in a later step.

Driver: psycopg 3 (async)  ->  DSN scheme `postgresql+psycopg://`
"""

import sys
from collections.abc import AsyncGenerator

if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# `create_async_engine` is lazy: it does not connect on import.
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session.

    Usage (later, when endpoints are built):

        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        yield session
