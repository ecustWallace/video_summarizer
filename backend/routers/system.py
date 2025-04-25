from fastapi import APIRouter, HTTPException
from core import pubsub
from pydantic import BaseModel
import os

router = APIRouter(
    prefix="/api/system",
    tags=["system"],
)

class PubSubStatus(BaseModel):
    enabled: bool
    project_id: str = ""
    topic_path: str = ""
    error_info: str = ""

@router.get("/pubsub-status", response_model=PubSubStatus)
async def get_pubsub_status():
    """
    获取PubSub服务的当前状态
    
    Returns:
        PubSubStatus: 一个包含PubSub启用状态的对象
    """
    try:
        # 从core.pubsub模块获取pubsub_enabled标志
        status = pubsub.pubsub_enabled
        project_id = os.getenv("GCP_PROJECT_ID", "未设置")
        
        response = {
            "enabled": status,
            "project_id": project_id,
            "topic_path": pubsub.TOPIC_PATH,
            "error_info": "" if status else "PubSub初始化失败，请检查日志"
        }
        
        # 尝试测试PubSub连接
        if status:
            try:
                # 发送一个测试消息到系统通知主题
                test_result = pubsub.publish_message(0, "system", "PubSub status check")
                if not test_result:
                    response["error_info"] = "PubSub发布测试消息失败"
            except Exception as e:
                response["error_info"] = f"PubSub测试失败: {str(e)}"
        
        return response
    except Exception as e:
        print(f"[API] Error checking PubSub status: {e}")
        # 出错时返回详细信息
        return {
            "enabled": False,
            "project_id": os.getenv("GCP_PROJECT_ID", "未设置"),
            "topic_path": getattr(pubsub, "TOPIC_PATH", "未知"),
            "error_info": f"检查PubSub状态时出错: {str(e)}"
        } 