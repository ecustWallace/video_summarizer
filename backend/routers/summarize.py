from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import os, json
from core.utils import query_response_from_tikapi, download_video_from_response
from core.bigquery import write_summary_to_bq, grab_summaries_from_bq
from core.gemini import *
from sqlalchemy import text
from database import engine
from .ws import send_progress as send_ws_progress


router = APIRouter()


class SummaryRequest(BaseModel):
    keyword: str
    video_number: int | None = None
    skip_download: bool = False
    email: str
    task_id: int

async def update_task_status(task_id: int, status: str, summary: str | None = None):
    """Update task status and optionally summary in the database."""
    update_query = text("""
        UPDATE test
        SET status = :status, summary = :summary
        WHERE id = :task_id
    """)
    try:
        with engine.connect() as conn:
            conn.execute(
                update_query,
                {
                    "task_id": task_id,
                    "status": status,
                    "summary": summary
                }
            )
            conn.commit()
    except Exception as e:
        print(f"Error updating task status: {e}")

async def summarize_videos(
    task_id: int,
    user_email: str,
    keyword: str,
    video_number: int | None = None,
    skip_download: bool = False
):
    """Main function to summarize videos. Can be called directly or via API endpoint."""
    try:
        await update_task_status(task_id, "In Progress")
        
        if skip_download:
            await send_ws_progress(task_id, "progress", "✅ Skipping download, retrieving past summaries from BigQuery...")
        elif video_number is None:
            raise HTTPException(status_code=400, detail="video_number is required when skip_download is false")
        else:
            try:
                await send_ws_progress(task_id, "progress", f"🔍 Fetching up to {video_number} videos from TikAPI...")
                response_ls = query_response_from_tikapi(keyword=keyword, video_number=video_number)
                total_queries = len(response_ls)
                await send_ws_progress(task_id, "progress", f"📊 Total TikAPI queries made: {total_queries}")

                create_bigquery_table(table_id=keyword)
                total_processed_videos = 0
                download_success = True

                for idx, response in enumerate(response_ls):
                    if total_processed_videos >= video_number:
                        break
                    await send_ws_progress(task_id, "progress", f"📥 Downloading batch {idx+1}...")
                    try:
                        paths = download_video_from_response(response, directory=keyword)
                        for path in paths:
                            if total_processed_videos >= video_number:
                                break
                            await send_ws_progress(task_id, "progress", f"📝 Analyzing video {total_processed_videos + 1}/{video_number}...")
                            summary = describe_video(path, PROMPT)
                            write_summary_to_bq(
                                project_id=os.environ["GCP_PROJECT_ID"],
                                dataset_id=os.environ["BQ_DATASET_ID"],
                                table_id=keyword,
                                filename=path,
                                summary=summary
                            )
                            total_processed_videos += 1
                    except Exception as e:
                        await send_ws_progress(task_id, "progress", f"❌ Error during download: {e}")
                        download_success = False
                        break

                if not download_success:
                    await send_ws_progress(task_id, "progress", "✅ TikAPI download failed, retrieving past summaries from BigQuery...")

            except Exception as e:
                await update_task_status(task_id, "Failed", str(e))
                raise HTTPException(status_code=500, detail=str(e))

        try:
            await send_ws_progress(task_id, "progress", "📊 Generating the final summary...")
            await send_ws_progress(task_id, "progress", "📊 Generate embeddings narrow down to 10...")
            result, summaries, prompt = process_summaries_from_bq(keyword)
            
            # 处理 result，它可能是一个列表
            if isinstance(result, list):
                # 如果是列表，取第一个元素
                result = result[0]
            
            # 清理 JSON 字符串
            # 移除所有 ```json 和 ``` 标记
            result = result.replace("```json", "").replace("```", "").strip()
            result_json = json.loads(result)
            if isinstance(result_json, list):
                result_json = result_json[0]
            final_summary = result_json.get("summary", "")

            # Update task status and summary
            await update_task_status(task_id, "Done", final_summary)
            await send_ws_progress(task_id, "summary", final_summary)

            return {
                "summary": final_summary,
                "summaries": summaries,
                "keyword": keyword,
                "prompt": prompt.replace("*", "").replace("#", ""),
                "justification": result_json.get("justification", "") if isinstance(result_json, dict) else "",
                "exclusion": result_json.get("exclusion", "") if isinstance(result_json, dict) else ""
            }
        except Exception as e:
            await update_task_status(task_id, "Failed", str(e))
            await send_ws_progress(task_id, "error", str(e))
            raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        await update_task_status(task_id, "Failed", str(e))
        await send_ws_progress(task_id, "error", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/tasks/summarize")
async def summarize_videos_endpoint(req: SummaryRequest):
    """API endpoint that wraps the main summarize_videos function."""
    return await summarize_videos(
        task_id=req.task_id,
        user_email=req.email,
        keyword=req.keyword,
        video_number=req.video_number,
        skip_download=req.skip_download
    )