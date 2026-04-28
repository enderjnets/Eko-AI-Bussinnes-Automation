from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, insert, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.setting import AppSetting
from app.models.user import User
from app.schemas.setting import SettingCreate, SettingUpdate, SettingResponse, SettingsBulkUpdateRequest
from app.core.security import get_current_user

router = APIRouter()


@router.get("", response_model=list[SettingResponse])
async def list_settings(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all settings, optionally filtered by category."""
    query = select(AppSetting)
    if category:
        query = query.where(AppSetting.category == category)
    query = query.order_by(AppSetting.category, AppSetting.key)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{key}", response_model=SettingResponse)
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single setting by key."""
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return setting


@router.post("", response_model=SettingResponse)
async def create_setting(
    data: SettingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new setting."""
    # Check for duplicate key
    existing = await db.execute(select(AppSetting).where(AppSetting.key == data.key))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Setting '{data.key}' already exists")

    setting = AppSetting(
        key=data.key,
        value=data.value,
        category=data.category,
        description=data.description,
        is_encrypted=data.is_encrypted,
        updated_by=current_user.email,
    )
    db.add(setting)
    await db.commit()
    await db.refresh(setting)
    return setting


@router.patch("/{key}", response_model=SettingResponse)
async def update_setting(
    key: str,
    data: SettingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing setting."""
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(setting, field, val)
    setting.updated_by = current_user.email

    await db.commit()
    await db.refresh(setting)
    return setting


@router.post("/bulk", response_model=list[SettingResponse])
async def bulk_update_settings(
    data: SettingsBulkUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upsert multiple settings at once."""
    settings = []
    for k, v in data.settings.items():
        stmt = pg_insert(AppSetting).values(
            key=k,
            value=v,
            category=data.category or "general",
            updated_by=current_user.email,
        ).on_conflict_do_update(
            index_elements=[AppSetting.key],
            set_={
                "value": v,
                "category": data.category or "general",
                "updated_by": current_user.email,
            },
        )
        await db.execute(stmt)

        result = await db.execute(select(AppSetting).where(AppSetting.key == k))
        settings.append(result.scalar_one())

    await db.commit()
    return settings


@router.delete("/{key}")
async def delete_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a setting."""
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    await db.delete(setting)
    await db.commit()
    return {"status": "deleted", "key": key}


@router.get("/public/defaults")
async def get_public_defaults():
    """Get default settings that don't require auth (read-only)."""
    return {
        "app_name": "Eko AI Business Automation",
        "app_version": "0.5.1",
        "cal_com_username": "eko-ai",
    }
