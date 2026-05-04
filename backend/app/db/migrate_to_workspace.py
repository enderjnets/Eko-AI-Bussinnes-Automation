"""Idempotent migration: assigns all existing data to a default workspace."""

import uuid
import logging
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace, WorkspaceMember
from app.models.user import User
from app.models.lead import Lead
from app.models.deal import Deal
from app.models.campaign import Campaign
from app.models.booking import Booking
from app.models.phone_call import PhoneCall
from app.models.proposal import Proposal
from app.models.payment import Payment
from app.models.sequence import EmailSequence
from app.models.setting import AppSetting
from app.models.object_metadata import ObjectMetadata
from app.models.field_metadata import FieldMetadata
from app.models.dynamic_record import DynamicRecord
from app.models.view import View, ViewField, ViewFilter, ViewSort

logger = logging.getLogger(__name__)

_LEGACY_MODELS = [
    Lead, Deal, Campaign, Booking, PhoneCall,
    Proposal, Payment, EmailSequence, AppSetting,
]

_METADATA_MODELS = [
    ObjectMetadata, FieldMetadata, DynamicRecord,
    View, ViewField, ViewFilter, ViewSort,
]


async def migrate_to_default_workspace(db: AsyncSession):
    """Create default workspace and assign all existing data to it."""

    # Check if default workspace already exists
    result = await db.execute(select(Workspace).where(Workspace.slug == "default"))
    default_ws = result.scalar_one_or_none()

    if not default_ws:
        default_ws = Workspace(
            id=str(uuid.uuid4()),
            name="Default Workspace",
            slug="default",
            plan="pro",
            is_active=True,
        )
        db.add(default_ws)
        await db.commit()
        await db.refresh(default_ws)
        logger.info(f"Created default workspace: {default_ws.id}")
    else:
        logger.info(f"Default workspace already exists: {default_ws.id}")

    # Assign all existing users as owners of the default workspace
    result = await db.execute(select(User))
    users = result.scalars().all()

    for user in users:
        result = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == default_ws.id,
                WorkspaceMember.user_id == user.id,
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            member = WorkspaceMember(
                workspace_id=default_ws.id,
                user_id=user.id,
                role="owner",
                is_active=True,
            )
            db.add(member)
    await db.commit()
    logger.info(f"Assigned {len(users)} users to default workspace")

    # Assign all legacy data to default workspace
    for model in _LEGACY_MODELS:
        table_name = model.__tablename__
        # Check if column exists
        result = await db.execute(
            text(f"""
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = '{table_name}' AND column_name = 'workspace_id'
            """)
        )
        if not result.scalar_one_or_none():
            logger.warning(f"Table {table_name} has no workspace_id column, skipping")
            continue

        await db.execute(
            update(model)
            .where(model.workspace_id.is_(None))
            .values(workspace_id=default_ws.id)
        )
        logger.info(f"Migrated {table_name} to default workspace")

    # Assign metadata objects/fields/views to default workspace OR mark as system
    # Strategy: objects with workspace_id=NULL and is_system=False -> assign to default
    for model in _METADATA_MODELS:
        table_name = model.__tablename__
        result = await db.execute(
            text(f"""
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = '{table_name}' AND column_name = 'workspace_id'
            """)
        )
        if not result.scalar_one_or_none():
            continue

        await db.execute(
            update(model)
            .where(model.workspace_id.is_(None))
            .values(workspace_id=default_ws.id)
        )
        logger.info(f"Migrated {table_name} to default workspace")

    await db.commit()
    logger.info("Migration to default workspace completed successfully")
    return default_ws.id
