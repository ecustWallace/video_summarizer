from fastapi import FastAPI
from routers import user, task, trigger, summarize
from fastapi.middleware.cors import CORSMiddleware
from routers import evaluation, ws, system
import asyncio
from core import pubsub
from fastapi import BackgroundTasks

app = FastAPI()

# 必须有 CORS 以允许前端调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 或限制为你的前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user.router)
app.include_router(task.router)
app.include_router(trigger.router)
app.include_router(summarize.router)
app.include_router(evaluation.router)
app.include_router(ws.router)
app.include_router(system.router)

# 定义处理 Pub/Sub 消息的回调函数
async def handle_pubsub_message(data):
    """
    处理从 Pub/Sub 接收到的消息
    将消息转发到对应任务的 WebSocket 连接
    """
    try:
        task_id = data.get("task_id")
        message_type = data.get("type")
        message = data.get("message")
        summary_data = data.get("data")
        error = data.get("error")
        
        # 根据消息类型确定要发送的数据
        content = message if message_type == "progress" else (
            summary_data if message_type == "summary" else 
            error if message_type == "error" else None
        )
        
        # 只尝试通过 WebSocket 发送，不再发布到 Pub/Sub (避免循环)
        if task_id in ws.task_connections:
            await ws.send_ws_direct(task_id, message_type, content)
    except Exception as e:
        print(f"[PubSub Handler] Error processing Pub/Sub message: {e}")

# 添加一个函数到 ws 模块，用于直接通过 WebSocket 发送消息（不发布到 Pub/Sub）
async def send_ws_direct(task_id, message_type, data):
    if task_id in ws.task_connections:
        message = {
            "type": message_type,
            "message": data if message_type == 'progress' else None,
            "data": data if message_type == 'summary' else None
        }
        
        # 移除 None 值
        message = {k: v for k, v in message.items() if v is not None}
        
        disconnected_clients = []
        for client in list(ws.task_connections[task_id]):
            try:
                await client.send_json(message)
            except Exception:
                disconnected_clients.append(client)
        
        # 清理断开连接的客户端
        for client in disconnected_clients:
            if client in ws.task_connections.get(task_id, []):
                ws.task_connections[task_id].remove(client)
                
        # 检查是否还有客户端，如果没有则清理
        if task_id in ws.task_connections and not ws.task_connections[task_id]:
            del ws.task_connections[task_id]

# 添加 send_ws_direct 到 ws 模块
ws.send_ws_direct = send_ws_direct

@app.on_event("startup")
async def startup_pubsub_handlers():
    """
    应用启动时设置订阅，以处理可能被其他实例发布的消息
    """
    print("[App] Starting up PubSub handlers")
    
    # 这是一个通用订阅，用于处理所有任务的消息
    try:
        subscription_id = pubsub.create_subscription(0, handle_pubsub_message)
        print(f"[App] Created PubSub subscription: {subscription_id}")
    except Exception as e:
        print(f"[App] Error setting up PubSub subscription: {e}")
