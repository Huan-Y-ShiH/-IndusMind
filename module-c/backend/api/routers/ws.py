"""WebSocket management — real-time workflow updates, alerts, and notifications."""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from api.config import settings
from api.services.ws_manager import ConnectionManager

router = APIRouter()

# Singleton — set by main.py during startup
manager: ConnectionManager | None = None


@router.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    """WebSocket endpoint for real-time alert push."""
    if manager is None:
        await websocket.close(code=1011, reason="Service not ready")
        return

    await manager.connect(websocket)

    await websocket.send_json({
        "type": "connection",
        "event_id": None,
        "data": {"message": "Connected to IndusMind alert stream"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_text("ping")
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        manager.disconnect(websocket)


@router.post("/ws/alerts/test")
async def post_test_alert(
    device_id: str = Query(default="WT-001"),
    risk_level: str = Query(default="high"),
    message: str = Query(default="振动幅值超过阈值3倍"),
):
    """手动推送模拟告警，方便前端开发测试。"""
    if not settings.dev_mode:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    if manager is None:
        return {"ok": False, "error": "Service not ready"}
    event_id = f"EVT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    await manager.broadcast_alert({
        "event_id": event_id,
        "device_id": device_id,
        "alert_type": "anomaly",
        "message": message,
        "risk_level": risk_level,
    })
    return {"ok": True, "clients": manager.active_count}


@router.get("/ws/alerts/clients")
async def get_alert_clients():
    """返回当前 WebSocket 连接数。"""
    if not settings.dev_mode:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    if manager is None:
        return {"clients": 0}
    return {"clients": manager.active_count}
