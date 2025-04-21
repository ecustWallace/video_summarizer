from fastapi import FastAPI
from routers import user, task, trigger, summarize
from fastapi.middleware.cors import CORSMiddleware
from routers import evaluation, ws

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
