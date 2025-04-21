from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio

router = APIRouter()
connected_clients = {}

@router.websocket("/ws/progress")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = id(websocket)
    connected_clients[client_id] = websocket
    try:
        while True:
            await asyncio.sleep(30)  # keep-alive ping
    except WebSocketDisconnect:
        del connected_clients[client_id]


async def send_progress(message: str):
    disconnected_clients = []
    for client_id, client in connected_clients.items():
        try:
            await client.send_text(message)
        except Exception:
            disconnected_clients.append(client_id)

    for client_id in disconnected_clients:
        del connected_clients[client_id]
