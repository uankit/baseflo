"""WebSocket routes for real-time insight streaming."""

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

    async def push_insight(self, project_id: str, payload: dict) -> None:
        ws = self.active.get(project_id)
        if ws:
            await ws.send_json(payload)


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
