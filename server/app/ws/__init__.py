"""WebSocket routes for real-time insight streaming."""

from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# In-memory connection manager for MVP; swap for Redis pub/sub later.
class ConnectionManager:
    def __init__(self) -> None:
        self.active: dict[str, WebSocket] = {}

    async def connect(self, project_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active[project_id] = websocket

    def disconnect(self, project_id: str) -> None:
        self.active.pop(project_id, None)

    async def push_insight(self, project_id: str, payload: dict[str, Any]) -> None:
        ws = self.active.get(project_id)
        if ws is None:
            return
        try:
            await ws.send_json({"type": "insight", "payload": payload})
        except Exception:
            # Client likely disconnected; clean up
            self.disconnect(project_id)


manager = ConnectionManager()


@router.websocket("/insights/{project_id}")
async def insight_stream(websocket: WebSocket, project_id: str) -> None:
    await manager.connect(project_id, websocket)
    try:
        while True:
            # Client can send acks or drill-down requests
            data = await websocket.receive_json()
            # TODO: handle client messages (mark read, request refresh, etc.)
            _ = data
    except WebSocketDisconnect:
        manager.disconnect(project_id)
    except Exception:
        manager.disconnect(project_id)
