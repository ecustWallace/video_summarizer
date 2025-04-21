import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from database import engine

router = APIRouter()

class TaskTriggerRequest(BaseModel):
    email: str
    keyword: str
    number: int | None = None
    skip_download: bool = False

@router.post("/api/tasks/trigger")
async def trigger_task(req: TaskTriggerRequest):
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO test (user_email, keyword, number)
                    VALUES (:email, :keyword, :number)
                    RETURNING id
                """),
                {
                    "email": req.email,
                    "keyword": req.keyword,
                    "number": req.number or 0
                }
            )
            conn.commit()
            task_id = result.fetchone().id

        # ✅ 使用 Cloud Run 公网地址调用 summarize_videos
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://backend-468274160217.us-central1.run.app/api/tasks/summarize",
                json={
                    "keyword": req.keyword,
                    "video_number": req.number,
                    "skip_download": req.skip_download,
                    "email": req.email,
                    "task_id": task_id,
                },
                timeout=180
            )

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)

        return {
            "message": "Task triggered",
            "task_id": task_id,
            "summary_result": response.json()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
