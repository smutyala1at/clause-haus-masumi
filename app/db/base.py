"""
Database base configuration and async session management
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from app.core.config import settings

# Base class for models (must be defined first)
Base = declarative_base()

# Engine and session factory - only created when DATABASE_URL is set
# This prevents errors when Alembic imports Base without a database connection
_engine = None
_AsyncSessionLocal = None


def _get_database_url():
    """Get database URL, converting to async format if needed"""
    database_url = settings.DATABASE_URL or "postgresql+asyncpg://localhost/clausehaus"
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


def get_engine():
    """Get or create the async database engine (lazy initialization)"""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            _get_database_url(),
            pool_pre_ping=True,
            echo=settings.DEBUG,
            future=True
        )
    return _engine


def get_session_factory():
    """Get or create the async session factory (lazy initialization)"""
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False
        )
    return _AsyncSessionLocal


# For backward compatibility - create engine only if DATABASE_URL is set
if settings.DATABASE_URL:
    engine = get_engine()
    AsyncSessionLocal = get_session_factory()
else:
    # Create dummy objects that will raise error if used without DATABASE_URL
    engine = None
    AsyncSessionLocal = None


async def get_db():
    """
    Async dependency to get database session.
    Use this in FastAPI route dependencies.
    
    Example:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    if not settings.DATABASE_URL:
        raise ValueError("DATABASE_URL not configured")
    
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
