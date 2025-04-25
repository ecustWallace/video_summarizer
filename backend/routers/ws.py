from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
import asyncio
from typing import Dict, List, Any
from core.pubsub import publish_message

router = APIRouter()

# 使用字典来存储每个 task_id 对应的 WebSocket 连接列表
# { task_id: [websocket1, websocket2, ...], ... }
task_connections: Dict[int, List[WebSocket]] = {}


@router.websocket("/ws/progress/{task_id}")  # <--- 修改这里，添加路径参数
async def websocket_endpoint(websocket: WebSocket, task_id: int):  # <--- 接收 task_id
    try:
        # 打印详细的连接信息
        client_host = websocket.client.host if hasattr(websocket, 'client') and hasattr(websocket.client, 'host') else "unknown"
        print(f"[WebSocket] Client {client_host} attempting to connect for task {task_id}")
        
        # 接受连接
        await websocket.accept()
        print(f"[WebSocket] Connection accepted for task {task_id} from {client_host}")
        
        # 存储连接
        if task_id not in task_connections:
            task_connections[task_id] = []
        task_connections[task_id].append(websocket)
        print(f"[WebSocket] Client connected for task {task_id}. Total clients for this task: {len(task_connections[task_id])}")
        print(f"[WebSocket] Current active connections: {list(task_connections.keys())}")
        
        # 发送一个初始消息确认连接成功
        try:
            await websocket.send_json({"type": "connection", "message": "WebSocket connection established"})
            print(f"[WebSocket] Sent connection confirmation to client for task {task_id}")
        except Exception as e:
            print(f"[WebSocket] Error sending connection confirmation: {e}")

        # 保持连接活跃的循环
        try:
            while True:
                # 可以接收客户端消息
                try:
                    data = await websocket.receive_text()
                    print(f"[WebSocket] Received from client for task {task_id}: {data}")
                    # 处理ping消息
                    if "ping" in data.lower():
                        await websocket.send_json({"type": "ping", "message": "pong"})
                except WebSocketDisconnect:
                    print(f"[WebSocket] Client disconnected during receive for task {task_id}")
                    break
                except Exception as e:
                    print(f"[WebSocket] Error during receive for task {task_id}: {e}")
                    # 如果接收出错，发送ping检查连接是否仍然有效
                    try:
                        await websocket.send_json({"type": "ping", "message": "ping"})
                    except:
                        print(f"[WebSocket] Connection lost during error recovery for task {task_id}")
                        break
                
                # 短暂休眠，保持连接活跃但不占用太多资源
                await asyncio.sleep(10)
                
                # 发送一个ping消息以保持连接活跃
                try:
                    await websocket.send_json({"type": "ping", "message": "ping"})
                    print(f"[WebSocket] Sent ping to client for task {task_id}")
                except Exception as e:
                    print(f"[WebSocket] Error sending ping, connection may be lost: {e}")
                    break
        except WebSocketDisconnect:
            print(f"[WebSocket] WebSocketDisconnect exception for task {task_id}")
        except Exception as e:
            print(f"[WebSocket] Unexpected error in connection loop for task {task_id}: {e}")
        
        # 无论什么原因导致循环结束，都清理连接
        print(f"[WebSocket] Connection loop ended for task {task_id}")
    except Exception as e:
        print(f"[WebSocket] Error during WebSocket setup for task {task_id}: {e}")
    finally:
        # 清理连接
        try:
            if task_id in task_connections and websocket in task_connections[task_id]:
                task_connections[task_id].remove(websocket)
                print(f"[WebSocket] Client removed for task {task_id}. Remaining clients: {len(task_connections[task_id])}")
                
                # 如果该 task_id 没有更多连接，清理字典条目
                if not task_connections[task_id]:
                    del task_connections[task_id]
                    print(f"[WebSocket] No more clients for task {task_id}, removed entry.")
                
                print(f"[WebSocket] Remaining active connections: {list(task_connections.keys())}")
        except Exception as cleanup_error:
            print(f"[WebSocket] Error during connection cleanup for task {task_id}: {cleanup_error}")


# 修改发送函数，使其能够向特定 task_id 的所有客户端发送消息
async def send_progress(task_id: int, message_type: str, data: Any):
    """
    Sends a structured message (progress, summary, error) to all clients
    connected for a specific task_id.
    
    首先尝试通过WebSocket直接发送消息到连接的客户端，然后无论成功与否，
    都通过Pub/Sub发送消息，以确保消息能够被其他实例接收和处理。
    """
    print(f"[WebSocket] Attempting to send message to task {task_id}")
    print(f"[WebSocket] Message type: {message_type}")
    print(f"[WebSocket] Message data: {data}")
    print(f"[WebSocket] Available connections: {list(task_connections.keys())}")
    
    # 1. 首先尝试直接通过WebSocket发送
    websocket_sent = False
    
    if task_id in task_connections:
        print(f"[WebSocket] Found {len(task_connections[task_id])} connected clients for task {task_id}")
        message = {
            "type": message_type,
            "message": data if message_type == 'progress' else None,
            "data": data if message_type == 'summary' else None
        }
        
        # 移除 None 值
        message = {k: v for k, v in message.items() if v is not None}
        print(f"[WebSocket] Sending message: {message}")
        
        disconnected_clients = []
        for client in list(task_connections[task_id]):
            try:
                await client.send_json(message)
                print(f"[WebSocket] Successfully sent message to client")
                websocket_sent = True
            except Exception as e:
                print(f"[WebSocket] Failed to send to client for task {task_id}: {e}")
                disconnected_clients.append(client)

        # 清理断开连接的客户端
        for client in disconnected_clients:
            if client in task_connections.get(task_id, []):
                task_connections[task_id].remove(client)
                print(f"[WebSocket] Removed disconnected client for task {task_id}")

        # 检查是否还有客户端，如果没有则清理
        if task_id in task_connections and not task_connections[task_id]:
            del task_connections[task_id]
            print(f"[WebSocket] No more clients for task {task_id}, removed entry")
    else:
        print(f"[WebSocket] No clients connected for task_id {task_id}")
    
    # 2. 无论WebSocket发送是否成功，都通过Pub/Sub发送消息
    try:
        publish_message(task_id, message_type, data)
        print(f"[WebSocket] Published message to Pub/Sub for task {task_id}")
    except Exception as e:
        print(f"[WebSocket] Error publishing message to Pub/Sub: {e}")
    
    # 3. 对于重要消息（summary或error），确保它们被保存
    if message_type in ['summary', 'error'] and not websocket_sent:
        print(f"[WebSocket] Important {message_type} message for task {task_id} couldn't be delivered via WebSocket")
        # 这里可以考虑将消息保存到数据库或缓存中

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