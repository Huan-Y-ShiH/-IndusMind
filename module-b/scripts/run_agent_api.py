#!/usr/bin/env python3
"""启动本地 Agent HTTP 服务（默认 0.0.0.0:8002）。"""
from __future__ import annotations

import os

import uvicorn

from indusmind.config import env


def main() -> None:
    host = env("AGENT_HOST", "0.0.0.0") or "0.0.0.0"
    port = int(env("AGENT_PORT", "8002") or "8002")
    if not (env("API_KEY", "") or "").strip():
        raise SystemExit("请先在 .env 中设置 API_KEY，再启动 Agent API")
    uvicorn.run(
        "indusmind.api.app:app",
        host=host,
        port=port,
        reload=os.environ.get("AGENT_RELOAD", "").lower() in {"1", "true", "yes"},
    )


if __name__ == "__main__":
    main()
