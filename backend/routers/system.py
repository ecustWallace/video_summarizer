from fastapi import APIRouter, HTTPException
import os
from typing import Dict, Any
import logging
from core.pubsub import pubsub_enabled, PROJECT_ID, TOPIC_PATH
from core.config import Config
from google.api_core.exceptions import GoogleAPIError
from google.cloud import pubsub_v1
import json

# 配置日志
logger = logging.getLogger('app.system')

router = APIRouter(prefix="/system", tags=["system"])

@router.get("/pubsub-status")
async def get_pubsub_status() -> Dict[str, Any]:
    """
    获取PubSub连接状态和诊断信息
    """
    logger.info("Retrieving PubSub status")
    
    # 收集环境信息
    env_info = {
        "PROJECT_ID": Config.PROJECT_ID,
        "CONFIG_PROJECT_ID": Config.PROJECT_ID,  # 配置中的项目ID
        "ENV_PROJECT_ID": os.getenv("GCP_PROJECT_ID", "Not set"),  # 环境变量中的项目ID
        "PUBSUB_TOPIC_PATH": Config.PUBSUB_TOPIC_PATH,
        "PUBSUB_TOPIC_ID": Config.PUBSUB_TOPIC_ID,
        "PUBSUB_ENABLED_FLAG": pubsub_enabled
    }
    
    # 诊断信息
    diagnostics = {
        "env_info": env_info,
        "config_values": {k: v for k, v in Config.__dict__.items() 
                         if not k.startswith('_') and isinstance(v, (str, int, bool, float))},
    }
    
    # 尝试执行额外的连接测试
    connection_test = {}
    if pubsub_enabled:
        try:
            publisher = pubsub_v1.PublisherClient()
            topic = publisher.get_topic(request={"topic": TOPIC_PATH})
            connection_test["live_connection_test"] = "success"
            connection_test["topic_info"] = {
                "name": topic.name,
                "labels": dict(topic.labels)
            }
        except GoogleAPIError as e:
            connection_test["live_connection_test"] = "failed"
            connection_test["error"] = str(e)
    else:
        connection_test["live_connection_test"] = "skipped"
        connection_test["reason"] = "PubSub is disabled"
    
    result = {
        "enabled": pubsub_enabled,
        "project_id": PROJECT_ID,
        "topic_path": TOPIC_PATH,
        "diagnostics": diagnostics,
        "connection_test": connection_test
    }
    
    logger.info(f"PubSub status: {json.dumps(result, indent=2)}")
    return result
    
@router.get("/config")
async def get_config() -> Dict[str, Any]:
    """
    获取当前应用配置（去除敏感信息）
    """
    logger.info("Retrieving system configuration")
    
    # 使用Config类提供的方法获取安全的配置信息
    safe_config = Config.get_all_config()
    
    # 移除可能的API密钥信息
    if "HAS_TIKAPI_KEY" in safe_config:
        safe_config["HAS_TIKAPI_KEY"] = bool(safe_config["HAS_TIKAPI_KEY"])
    if "HAS_GEMINI_KEY" in safe_config:
        safe_config["HAS_GEMINI_KEY"] = bool(safe_config["HAS_GEMINI_KEY"])
    if "HAS_OPENAI_API_KEY" in safe_config:
        safe_config["HAS_OPENAI_API_KEY"] = bool(safe_config["HAS_OPENAI_API_KEY"])
    
    # 返回配置以及环境信息
    return {
        "config": safe_config,
        "debug_mode": Config.DEBUG
    } 