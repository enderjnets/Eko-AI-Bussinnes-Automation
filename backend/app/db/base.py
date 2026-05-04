"""Database base module with lazy engine creation for Celery compatibility."""

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
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
            # Inject workspace_id for PostgreSQL RLS policies
            from app.services.tenant_context import get_workspace_id
            ws_id = get_workspace_id()
            if ws_id:
                await session.execute(text(f"SET LOCAL app.current_workspace_id = '{ws_id}'"))
            yield session
        finally:
            await session.close()


import logging

async def init_db():
    """Create all tables on startup. In production, use Alembic migrations."""
    logger = logging.getLogger(__name__)

    async with _get_engine().begin() as conn:
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # Create all tables via SQLAlchemy first (new models like Workspace need to exist)
        await conn.run_sync(Base.metadata.create_all)

        # Sync missing columns from models to existing tables
        from app.db.sync_schema import sync_schema
        async with AsyncSessionLocal() as sync_db:
            try:
                await sync_schema(sync_db)
            except Exception:
                logger.exception("Schema sync failed")

        # Add workspace_id columns to existing legacy tables (idempotent fallback)
        import pathlib
        migrate_path = pathlib.Path(__file__).parent / "migrate_add_workspace_columns.sql"
        if migrate_path.exists():
            await conn.execute(text(migrate_path.read_text()))

        # Create metadata engine tables idempotently via raw SQL
        sql_path = pathlib.Path(__file__).parent / "init_metadata.sql"
        if sql_path.exists():
            sql = sql_path.read_text()
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                if stmt:
                    await conn.execute(text(stmt))

        # Apply Row-Level Security policies for workspace isolation
        rls_path = pathlib.Path(__file__).parent / "init_rls.sql"
        if rls_path.exists():
            await conn.execute(text(rls_path.read_text()))

    # Register workspace auto-injection hooks
    from app.db.workspace_hooks import register_workspace_hooks
    register_workspace_hooks()

    # Migrate existing data to default workspace (idempotent)
    from app.db.migrate_to_workspace import migrate_to_default_workspace
    async with AsyncSessionLocal() as db:
        try:
            await migrate_to_default_workspace(db)
        except Exception:
            logger.exception("Failed to migrate to default workspace")

    # Seed default nurture sequence
    from app.db.seed import seed_nurture_sequence
    async with AsyncSessionLocal() as db:
        try:
            await seed_nurture_sequence(db)
        except Exception:
            logger.exception("Failed to seed nurture sequence")

    # Seed metadata engine (idempotent)
    from app.db.seed_metadata import seed_metadata
    async with AsyncSessionLocal() as db:
        try:
            await seed_metadata(db)
        except Exception:
            logger.exception("Failed to seed metadata")
