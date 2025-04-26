"""
集中管理所有GCP和应用程序配置的模块
"""
import os
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('app.config')

# 确保所有必需的环境变量都存在，如果不存在则使用默认值
class Config:
    """
    应用程序配置类
    """
    # Google Cloud配置
    PROJECT_ID = os.getenv("GCP_PROJECT_ID")
    if not PROJECT_ID:
        logger.warning("GCP_PROJECT_ID 环境变量未设置，使用默认值")
        PROJECT_ID = "glossy-reserve-450922-p9"

    # BigQuery配置
    BQ_DATASET_ID = os.getenv("BQ_DATASET_ID")
    if not BQ_DATASET_ID:
        logger.warning("BQ_DATASET_ID 环境变量未设置，使用默认值")
        BQ_DATASET_ID = "video_summary"

    # PubSub配置
    PUBSUB_TOPIC_ID = "task"
    PUBSUB_TOPIC_PATH = f"projects/{PROJECT_ID}/topics/{PUBSUB_TOPIC_ID}"

    # API密钥
    TIKAPI_KEY = os.getenv("TIKAPI_KEY", "")
    GEMINI_KEY = os.getenv("GEMINI_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # 应用配置
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    PORT = int(os.getenv("PORT", "8080"))

    @classmethod
    def get_all_config(cls):
        """
        返回所有配置项，用于调试
        """
        return {
            "PROJECT_ID": cls.PROJECT_ID,
            "BQ_DATASET_ID": cls.BQ_DATASET_ID,
            "PUBSUB_TOPIC_PATH": cls.PUBSUB_TOPIC_PATH,
            "DEBUG": cls.DEBUG,
            "PORT": cls.PORT,
            "HAS_TIKAPI_KEY": bool(cls.TIKAPI_KEY),
            "HAS_GEMINI_KEY": bool(cls.GEMINI_KEY),
            "HAS_OPENAI_API_KEY": bool(cls.OPENAI_API_KEY),
        }

    @classmethod
    def log_config(cls):
        """
        记录所有配置项
        """
        logger.info("应用程序配置:")
        for key, value in cls.get_all_config().items():
            logger.info(f"  {key}: {value}")

# 在导入时记录配置
Config.log_config() 