from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from uuid import UUID
from typing import Generic, TypeVar, Optional

T = TypeVar('T')

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int

class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "0.1.0"
    environment: str

class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None
