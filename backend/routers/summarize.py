from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import os, json
from core.utils import query_response_from_tikapi, download_video_from_response
from core.bigquery import write_summary_to_bq, grab_summaries_from_bq
from core.gemini import *
from sqlalchemy import text
from database import engine


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

@router.post("/api/tasks/summarize")
async def summarize_videos(req: SummaryRequest):
    keyword = req.keyword
    video_number = req.video_number
    skip_download = req.skip_download
    task_id = req.task_id

    try:
        await update_task_status(task_id, "In Progress")
        
        if skip_download:
            await send_progress("✅ Skipping download, retrieving past summaries from BigQuery...")
        elif video_number is None:
            raise HTTPException(status_code=400, detail="video_number is required when skip_download is false")
        else:
            try:
                await send_progress(f"🔍 Fetching up to {video_number} videos from TikAPI...")
                response_ls = query_response_from_tikapi(keyword=keyword, video_number=video_number)
                total_queries = len(response_ls)
                await send_progress(f"📊 Total TikAPI queries made: {total_queries}")

                create_bigquery_table(table_id=keyword)
                total_processed_videos = 0
                download_success = True

                for idx, response in enumerate(response_ls):
                    if total_processed_videos >= video_number:
                        break
                    await send_progress(f"📥 Downloading batch {idx+1}...")
                    try:
                        paths = download_video_from_response(response, directory=keyword)
                        for path in paths:
                            if total_processed_videos >= video_number:
                                break
                            await send_progress(f"📝 Analyzing video {total_processed_videos + 1}/{video_number}...")
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
                        await send_progress(f"❌ Error during download: {e}")
                        download_success = False
                        break

                if not download_success:
                    await send_progress("✅ TikAPI download failed, retrieving past summaries from BigQuery...")

            except Exception as e:
                await update_task_status(task_id, "Failed", str(e))
                raise HTTPException(status_code=500, detail=str(e))

        try:
            await send_progress("📊 Generating the final summary...")
            await send_progress(f"📊 Generate embeddings narrow down to 10...")
            result, summaries, prompt = process_summaries_from_bq(keyword)
            result = result.strip("```json").strip("```")
            result_json = json.loads(result)
            final_summary = result_json.get("summary", "")

            # Update task status and summary
            await update_task_status(task_id, "Done", final_summary)

            return {
                "summary": final_summary,
                "summaries": summaries,
                "keyword": keyword,
                "prompt": prompt.replace("*", "").replace("#", ""),
                "justification": result_json.get("justification", ""),
                "exclusion": result_json.get("exclusion", "")
            }
        except Exception as e:
            await update_task_status(task_id, "Failed", str(e))
            raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        await update_task_status(task_id, "Failed", str(e))
        raise HTTPException(status_code=500, detail=str(e))
