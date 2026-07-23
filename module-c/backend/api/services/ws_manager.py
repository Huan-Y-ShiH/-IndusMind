"""WebSocket connection manager — tracks clients and broadcasts messages."""

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Track active WebSocket connections and broadcast messages."""

    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self._connections:
            self._connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]):
        """Send a JSON message to all connected clients."""
        dead: list[WebSocket] = []
        payload = json.dumps(message, ensure_ascii=False)
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_workflow_update(self, data: dict):
        """Broadcast a workflow status update to all connected clients."""
        diagnosis = data.get("diagnosis", {}) if isinstance(data.get("diagnosis"), dict) else {}
        message: dict[str, Any] = {
            "type": "workflow_update",
            "event_id": data.get("event_id"),
            "workflow_id": data.get("workflow_id"),
            "device_id": data.get("device_id"),
            "data": {
                "status": data.get("status"),
                "diagnosis_level": diagnosis.get("diagnosis_level"),
                "need_human_review": diagnosis.get("need_human_review", data.get("need_human_review", False)),
                "progress": data.get("progress"),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self.broadcast(message)

    async def broadcast_alert(self, data: dict):
        """Broadcast an alert-type message to all connected clients."""
        message: dict[str, Any] = {
            "type": "alert",
            "event_id": data.get("event_id"),
            "workflow_id": data.get("workflow_id"),
            "device_id": data.get("device_id"),
            "data": {
                "alert_type": data.get("alert_type", "info"),
                "message": data.get("message"),
                "risk_level": data.get("risk_level"),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self.broadcast(message)

    @property
    def active_count(self) -> int:
        return len(self._connections)
