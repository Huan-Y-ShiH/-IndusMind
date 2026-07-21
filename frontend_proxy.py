"""
Tiny reverse proxy for a frontend server that cannot reach Bitahub:8000 directly.

On the frontend server:
  1) Keep an SSH tunnel open:
     ssh -N -L 127.0.0.1:18000:127.0.0.1:8000 \
       -i ~/.ssh/id_ed25519 -p 42514 root@xj-member.bitahub.com
  2) Run this proxy:
     pip install fastapi uvicorn httpx
     uvicorn frontend_proxy:app --host 0.0.0.0 --port 9000

Browser then calls:
  POST http://前端服务器:9000/api/v1/monitor/analyze
"""
import os

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

UPSTREAM = os.getenv("MONITOR_UPSTREAM", "http://127.0.0.1:18000")

app = FastAPI(title="Monitor Frontend Proxy")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.api_route("/{path:path}", methods=["GET", "POST", "OPTIONS"])
async def proxy(path: str, request: Request) -> Response:
    url = f"{UPSTREAM.rstrip('/')}/{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"
    body = await request.body()
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"host", "content-length"}
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        upstream = await client.request(
            request.method, url, content=body, headers=headers
        )
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
    )
