import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

# 加载 .env 文件内容
load_dotenv('test.env')

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# SQLAlchemy 引擎
engine = create_engine(DATABASE_URL, echo=True, future=True)
