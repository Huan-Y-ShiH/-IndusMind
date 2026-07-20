"""
Shared Pydantic schemas used across modules.
Keep this file minimal — only truly shared types go here.
"""
from pydantic import BaseModel, Field
from typing import Optional, Any


class APIResponse(BaseModel):
    """
    Unified API response wrapper.
    Iron Rule #1: ALL APIs must use this format.
    """
    code: int = 0
    data: Optional[Any] = None
    msg: str = "success"


class HealthResponse(BaseModel):
    """Standard health check response."""
    status: str = "healthy"
    version: str = "0.1.0"
    service: str = ""
