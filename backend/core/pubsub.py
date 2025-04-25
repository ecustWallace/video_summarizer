from google.cloud import pubsub_v1
import json
import os
import asyncio
from typing import Dict, Any, Optional
import threading

# 从环境变量获取 Google Cloud Pub/Sub 配置
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "glossy-reserve-450922-p9")
TOPIC_ID = "task"
TOPIC_PATH = f"projects/{PROJECT_ID}/topics/{TOPIC_ID}"

# 状态标志
pubsub_enabled = True

try:
    # 创建发布者客户端
    publisher = pubsub_v1.PublisherClient()
    
    # 创建订阅者客户端
    subscriber = pubsub_v1.SubscriberClient()
    
    # 确认 topic 存在
    try:
        publisher.get_topic(request={"topic": TOPIC_PATH})
        print(f"[PubSub] Successfully connected to topic: {TOPIC_PATH}")
    except Exception as e:
        print(f"[PubSub] Error checking topic: {e}")
        # 尝试创建 topic
        try:
            publisher.create_topic(request={"name": TOPIC_PATH})
            print(f"[PubSub] Created new topic: {TOPIC_PATH}")
        except Exception as create_e:
            print(f"[PubSub] Error creating topic: {create_e}")
            pubsub_enabled = False
except Exception as e:
    print(f"[PubSub] Error initializing Pub/Sub clients: {e}")
    print("[PubSub] Running in fallback mode without Pub/Sub")
    pubsub_enabled = False
    # 创建占位符对象，以便代码在没有 Pub/Sub 的情况下仍能运行
    class DummyClient:
        def __getattr__(self, name):
            def dummy_method(*args, **kwargs):
                print(f"[PubSub] Dummy method called: {name}")
                return None
            return dummy_method
    
    publisher = DummyClient()
    subscriber = DummyClient()

# 创建一个字典来存储任务ID到回调函数的映射
task_callbacks: Dict[int, Any] = {}


def publish_message(task_id: int, message_type: str, data: Any) -> str:
    """
    发布消息到Google Cloud Pub/Sub
    
    Args:
        task_id: 任务ID
        message_type: 消息类型 (progress, summary, error)
        data: 消息数据
    
    Returns:
        str: 发布的消息ID
    """
    if not pubsub_enabled:
        print(f"[PubSub] Pub/Sub is disabled, skipping message publish for task {task_id}")
        return ""
        
    try:
        # 准备消息
        message = {
            "task_id": task_id,
            "type": message_type,
            "message": data if message_type == 'progress' else None,
            "data": data if message_type == 'summary' else None,
            "error": data if message_type == 'error' else None
        }
        
        # 移除None值
        message = {k: v for k, v in message.items() if v is not None}
        
        # 转换为JSON并编码为bytes
        message_json = json.dumps(message).encode("utf-8")
        
        # 发布消息
        future = publisher.publish(TOPIC_PATH, message_json)
        message_id = future.result()
        
        print(f"[PubSub] Published message {message_id} for task {task_id}")
        print(f"[PubSub] Message: {message}")
        
        return message_id
    except Exception as e:
        print(f"[PubSub] Error publishing message for task {task_id}: {e}")
        return ""


def _callback(message):
    """
    处理收到的Pub/Sub消息的回调函数
    """
    try:
        # 解码消息
        data = json.loads(message.data.decode("utf-8"))
        task_id = data.get("task_id")
        
        print(f"[PubSub] Received message for task {task_id}")
        print(f"[PubSub] Message data: {data}")
        
        # 查找对应任务ID的回调函数
        if task_id in task_callbacks:
            # 执行回调
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            callback_func = task_callbacks[task_id]
            loop.run_until_complete(callback_func(data))
            loop.close()
            
            # 确认消息
            message.ack()
        else:
            print(f"[PubSub] No callback registered for task {task_id}")
            # 仍然确认消息
            message.ack()
    except Exception as e:
        print(f"[PubSub] Error processing message: {e}")
        # 出错时也确认消息，防止反复处理
        message.ack()


def create_subscription(task_id: int, callback_func) -> Optional[str]:
    """
    为特定任务创建一个订阅，并设置回调函数
    
    Args:
        task_id: 任务ID
        callback_func: 当收到该任务的消息时要调用的异步函数
    
    Returns:
        str: 订阅名称，或者None（如果创建失败）
    """
    if not pubsub_enabled:
        print(f"[PubSub] Pub/Sub is disabled, skipping subscription creation for task {task_id}")
        return None
        
    try:
        # 注册回调函数
        task_callbacks[task_id] = callback_func
        
        # 创建订阅
        subscription_id = f"task-{task_id}-subscription"
        subscription_path = subscriber.subscription_path(PROJECT_ID, subscription_id)
        
        # 检查订阅是否已存在
        try:
            subscriber.get_subscription(subscription=subscription_path)
            print(f"[PubSub] Subscription {subscription_id} already exists")
        except Exception:
            # 如果不存在，创建新订阅
            subscription = subscriber.create_subscription(
                request={"name": subscription_path, "topic": TOPIC_PATH}
            )
            print(f"[PubSub] Created subscription: {subscription_id}")
        
        # 开始监听订阅
        subscriber.subscribe(subscription_path, callback=_callback)
        print(f"[PubSub] Listening for messages on {subscription_id}")
        
        return subscription_id
    except Exception as e:
        print(f"[PubSub] Error creating subscription for task {task_id}: {e}")
        return None


def delete_subscription(task_id: int) -> bool:
    """
    删除特定任务的订阅
    
    Args:
        task_id: 任务ID
    
    Returns:
        bool: 是否成功删除
    """
    if not pubsub_enabled:
        print(f"[PubSub] Pub/Sub is disabled, skipping subscription deletion for task {task_id}")
        return True
        
    try:
        # 删除回调函数注册
        if task_id in task_callbacks:
            del task_callbacks[task_id]
        
        # 删除订阅
        subscription_id = f"task-{task_id}-subscription"
        subscription_path = subscriber.subscription_path(PROJECT_ID, subscription_id)
        
        subscriber.delete_subscription(request={"subscription": subscription_path})
        print(f"[PubSub] Deleted subscription: {subscription_id}")
        
        return True
    except Exception as e:
        print(f"[PubSub] Error deleting subscription for task {task_id}: {e}")
        return False 