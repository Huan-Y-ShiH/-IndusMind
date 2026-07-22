"""API Key 鉴权（Header: X-Api-Key）。"""
from __future__ import annotations

from fastapi import Header, HTTPException

from indusmind.config import env


def configured_api_key() -> str:
    return (env("API_KEY", "") or "").strip()


async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-Api-Key")) -> None:
    expected = configured_api_key()
    if not expected:
        raise HTTPException(
            status_code=500,
            detail={"code": 500, "data": None, "msg": "服务端未配置 API_KEY"},
        )
    if not x_api_key or x_api_key != expected:
        raise HTTPException(
            status_code=401,
            detail={"code": 401, "data": None, "msg": "unauthorized"},
        )
