"""Sync SQLAlchemy models with existing database schema.

Generates and executes ALTER TABLE statements for missing columns.
Safe to run multiple times (idempotent).
"""

import logging
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _get_missing_columns(sync_conn):
    """Run synchronously inside async connection."""
    from app.db.base import Base
    inspector = inspect(sync_conn)
    missing = []

    for table_name, table in Base.metadata.tables.items():
        if not inspector.has_table(table_name):
            continue
        existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
        for column in table.columns:
            if column.name not in existing_columns:
                col_spec = str(column.compile(dialect=sync_conn.dialect))
                sql = f'ALTER TABLE "{table_name}" ADD COLUMN IF NOT EXISTS {col_spec}'
                missing.append(sql)
                logger.info(f"Missing column detected: {table_name}.{column.name}")
    return missing


async def sync_schema(db: AsyncSession):
    """Add missing columns from SQLAlchemy models to existing tables."""
    conn = await db.connection()
    missing_columns_sql = await conn.run_sync(_get_missing_columns)

    for sql in missing_columns_sql:
        try:
            await db.execute(text(sql))
            logger.info(f"Added column via: {sql}")
        except Exception as e:
            logger.warning(f"Failed to execute '{sql}': {e}")

    await db.commit()
    logger.info(f"Schema sync complete. {len(missing_columns_sql)} columns added.")
