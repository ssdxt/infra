from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ActivityLogCreate(BaseModel):
    space_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[UUID] = None
    detail: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class ActivityLogResponse(BaseModel):
    uuid: UUID
    space_id: Optional[UUID]
    user_id: Optional[UUID]
    action: str
    target_type: Optional[str]
    target_id: Optional[UUID]
    detail: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActivityLogFilter(BaseModel):
    space_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    action: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[UUID] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
