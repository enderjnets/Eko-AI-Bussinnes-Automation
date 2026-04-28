from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SettingBase(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    value: str = Field(...)
    category: str = Field(default="general", max_length=50)
    description: Optional[str] = None
    is_encrypted: bool = False


class SettingCreate(SettingBase):
    pass


class SettingUpdate(BaseModel):
    value: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = None
    is_encrypted: Optional[bool] = None


class SettingResponse(BaseModel):
    id: int
    key: str
    value: str
    category: str
    description: Optional[str]
    is_encrypted: bool
    updated_at: datetime
    updated_by: Optional[str]

    class Config:
        from_attributes = True


class SettingsBulkUpdateRequest(BaseModel):
    settings: dict[str, str] = Field(..., description="Dict of key -> value to upsert")
    category: Optional[str] = "general"
