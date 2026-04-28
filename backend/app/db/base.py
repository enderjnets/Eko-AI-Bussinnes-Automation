"""Database base module with lazy engine creation for Celery compatibility."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.config import get_settings

settings = get_settings()
Base = declarative_base()

# Lazy-initialized engine — created on first use so that each asyncio event loop
# (e.g. inside Celery tasks that call asyncio.run()) gets a fresh engine.
_engine = None
_AsyncSessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.is_development,
            pool_size=5,
            max_overflow=10,
            pool_recycle=300,
            pool_pre_ping=True,
        )
    return _engine


def recreate_engine():
    """Dispose existing engine and reset globals so a fresh engine is created.
    Called by Celery worker_process_init to avoid 'Future attached to a different loop'.
    """
    global _engine, _AsyncSessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _AsyncSessionLocal = None


def _get_session_maker():
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _AsyncSessionLocal


# Expose AsyncSessionLocal as a property-like callable for compatibility
class _SessionLocalProxy:
    def __call__(self, *args, **kwargs):
        return _get_session_maker()(*args, **kwargs)

    def __aenter__(self):
        return _get_session_maker().__aenter__()

    def __aexit__(self, *args, **kwargs):
        return _get_session_maker().__aexit__(*args, **kwargs)


AsyncSessionLocal = _SessionLocalProxy()


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all tables on startup. In production, use Alembic migrations."""
    async with _get_engine().begin() as conn:
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
