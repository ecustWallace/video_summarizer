from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import asyncio
from typing import Dict, List

router = APIRouter()

# 使用字典来存储每个 task_id 对应的 WebSocket 连接列表
# { task_id: [websocket1, websocket2, ...], ... }
task_connections: Dict[int, List[WebSocket]] = {}


@router.websocket("/ws/progress/{task_id}")  # <--- 修改这里，添加路径参数
async def websocket_endpoint(websocket: WebSocket, task_id: int):  # <--- 接收 task_id
    await websocket.accept()
    if task_id not in task_connections:
        task_connections[task_id] = []
    task_connections[task_id].append(websocket)
    print(f"Client connected for task {task_id}. Total clients for this task: {len(task_connections[task_id])}")

    try:
        while True:
            # 你可以接收来自客户端的消息，如果需要的话
            # data = await websocket.receive_text()
            # print(f"Received from client for task {task_id}: {data}")

            # 保持连接活动，或者根据需要处理客户端消息
            # 短暂的 sleep 通常比长的 sleep 更好，以更快地检测断开连接
            await asyncio.sleep(10)
            # 可以选择发送一个 ping 消息
            # await websocket.send_text("ping")
    except WebSocketDisconnect:
        # 客户端断开连接时，将其从列表中移除
        task_connections[task_id].remove(websocket)
        print(f"Client disconnected for task {task_id}. Remaining clients: {len(task_connections[task_id])}")
        # 如果该 task_id 没有更多连接，可以清理字典条目（可选）
        if not task_connections[task_id]:
            del task_connections[task_id]
            print(f"No more clients for task {task_id}, removed entry.")
    except Exception as e:
        # 处理其他可能的异常
        print(f"Error for task {task_id}: {e}")
        if websocket in task_connections.get(task_id, []):
            task_connections[task_id].remove(websocket)
            if not task_connections[task_id]:
                del task_connections[task_id]


# 修改发送函数，使其能够向特定 task_id 的所有客户端发送消息
async def send_progress(task_id: int, message_type: str, data: any):
    """
    Sends a structured message (progress, summary, error) to all clients
    connected for a specific task_id.
    """
    if task_id in task_connections:
        message_str = {"type": message_type, "message": data if message_type != 'summary' else None,
                       "data": data if message_type == 'summary' else None}
        import json  # Make sure to import json
        message_json = json.dumps(
            {k: v for k, v in message_str.items() if v is not None})  # Remove None values before sending

        disconnected_clients = []
        # 使用 list(task_connections[task_id]) 创建副本进行迭代，以防在迭代期间列表被修改
        for client in list(task_connections[task_id]):
            try:
                await client.send_json(message_json)  # 使用 send_json 发送 JSON 格式
                # 或者如果你确定前端总是能处理字符串:
                # await client.send_text(message_json)
            except Exception as e:
                print(f"Failed to send to client for task {task_id}: {e}. Marking for removal.")
                # 标记稍后移除，直接在循环中移除可能导致问题
                disconnected_clients.append(client)

        # 清理断开连接的客户端
        for client in disconnected_clients:
            if client in task_connections.get(task_id, []):
                task_connections[task_id].remove(client)
                print(f"Removed disconnected client for task {task_id} during send.")

        # 检查是否还有客户端，如果没有则清理
        if task_id in task_connections and not task_connections[task_id]:
            del task_connections[task_id]
            print(f"No more clients for task {task_id} after send, removed entry.")

    else:
        print(f"No clients connected for task_id {task_id} to send progress.")

# --- 如何在你的其他路由（例如处理任务的路由）中使用 send_progress ---
# 假设你在 routers/task.py 中有一个处理任务的函数

# Example in routers/task.py (or wherever your task processing happens)
# from .ws import send_progress # Import the send function

# async def process_long_task(task_id: int, ...):
#     try:
#         await send_progress(task_id, "progress", "Task started...")
#         await asyncio.sleep(5) # Simulate work
#         await send_progress(task_id, "progress", "Processing step 1...")
#         await asyncio.sleep(5) # Simulate work
#         await send_progress(task_id, "progress", "Processing step 2...")
#         # ... more steps ...
#         summary_result = "This is the final summary."
#         await send_progress(task_id, "summary", summary_result)
#     except Exception as e:
#         error_message = f"Task failed: {str(e)}"
#         await send_progress(task_id, "error", error_message)