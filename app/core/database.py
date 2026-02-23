"""
Database session management with SQLAlchemy async support
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings
from app.models.database import Base
from app.core.logging import get_logger

logger = get_logger("database")

# Create async engine with asyncpg driver
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,  # Recycle connections after 1 hour
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db():
    """
    Dependency for getting async database session

    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}", exc_info=True)
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    Initialize database tables (for development only)
    In production, use Alembic migrations instead
    """
    logger.info("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized successfully")


async def close_db():
    """Close database engine and cleanup connections"""
    logger.info("Closing database connections...")
    await engine.dispose()
    logger.info("Database connections closed")
