from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import os, json
from core.utils import query_response_from_tikapi, download_video_from_response
from core.bigquery import write_summary_to_bq, grab_summaries_from_bq
from core.gemini import *
from sqlalchemy import text
from database import engine
from routers.ws import send_progress


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
            print(f"[DB] Updated task {task_id} status to {status}")
            return True
    except Exception as e:
        print(f"[DB] Error updating task status: {e}")
        return False

async def summarize_videos(
    task_id: int,
    user_email: str,
    keyword: str,
    video_number: int | None = None,
    skip_download: bool = False
):
    """Main function to summarize videos. Can be called directly or via API endpoint."""
    try:
        print(f"[Summarize] Starting summarization for task {task_id}")
        await update_task_status(task_id, "In Progress")
        
        # 发送初始进度消息
        try:
            await send_progress(task_id, "progress", "✅ Task started...")
        except Exception as e:
            print(f"[Summarize] Error sending initial progress: {e}")
        
        if skip_download:
            print(f"[Summarize] Skipping download for task {task_id}")
            try:
                await send_progress(task_id, "progress", "✅ Skipping download, retrieving past summaries from BigQuery...")
            except Exception as e:
                print(f"[Summarize] Error sending skip download progress: {e}")
        elif video_number is None:
            raise HTTPException(status_code=400, detail="video_number is required when skip_download is false")
        else:
            try:
                print(f"[Summarize] Fetching videos for task {task_id}")
                try:
                    await send_progress(task_id, "progress", f"🔍 Fetching up to {video_number} videos from TikAPI...")
                except Exception as e:
                    print(f"[Summarize] Error sending fetch progress: {e}")
                
                response_ls = query_response_from_tikapi(keyword=keyword, video_number=video_number)
                total_queries = len(response_ls)
                print(f"[Summarize] Made {total_queries} TikAPI queries for task {task_id}")
                
                try:
                    await send_progress(task_id, "progress", f"📊 Total TikAPI queries made: {total_queries}")
                except Exception as e:
                    print(f"[Summarize] Error sending TikAPI query count: {e}")

                create_bigquery_table(table_id=keyword)
                total_processed_videos = 0
                download_success = True

                for idx, response in enumerate(response_ls):
                    if total_processed_videos >= video_number:
                        break
                    print(f"[Summarize] Processing batch {idx+1} for task {task_id}")
                    
                    try:
                        await send_progress(task_id, "progress", f"📥 Downloading batch {idx+1}...")
                    except Exception as e:
                        print(f"[Summarize] Error sending batch download progress: {e}")
                    
                    try:
                        paths = download_video_from_response(response, directory=keyword)
                        for path in paths:
                            if total_processed_videos >= video_number:
                                break
                            print(f"[Summarize] Analyzing video {total_processed_videos + 1}/{video_number} for task {task_id}")
                            
                            try:
                                await send_progress(task_id, "progress", f"📝 Analyzing video {total_processed_videos + 1}/{video_number}...")
                            except Exception as e:
                                print(f"[Summarize] Error sending video analysis progress: {e}")
                            
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
                        print(f"[Summarize] Error during download for task {task_id}: {e}")
                        
                        try:
                            await send_progress(task_id, "progress", f"❌ Error during download: {e}")
                        except Exception as ws_e:
                            print(f"[Summarize] Error sending download error message: {ws_e}")
                        
                        download_success = False
                        break

                if not download_success:
                    print(f"[Summarize] Download failed for task {task_id}, retrieving from BigQuery")
                    
                    try:
                        await send_progress(task_id, "progress", "✅ TikAPI download failed, retrieving past summaries from BigQuery...")
                    except Exception as e:
                        print(f"[Summarize] Error sending BigQuery fallback message: {e}")

            except Exception as e:
                print(f"[Summarize] Error in video processing for task {task_id}: {e}")
                await update_task_status(task_id, "Failed", str(e))
                
                try:
                    await send_progress(task_id, "error", str(e))
                except Exception as ws_e:
                    print(f"[Summarize] Error sending processing error message: {ws_e}")
                
                raise HTTPException(status_code=500, detail=str(e))

        try:
            print(f"[Summarize] Generating final summary for task {task_id}")
            
            try:
                await send_progress(task_id, "progress", "📊 Generating the final summary...")
                await send_progress(task_id, "progress", "📊 Generate embeddings narrow down to 10...")
            except Exception as e:
                print(f"[Summarize] Error sending final summary progress: {e}")
            
            result, summaries, prompt = process_summaries_from_bq(keyword)
            
            # 处理 result，它可能是一个列表
            if isinstance(result, list):
                result = result[0]
            
            # 清理 JSON 字符串
            result = result.replace("```json", "").replace("```", "").strip()
            result_json = json.loads(result)
            if isinstance(result_json, list):
                result_json = result_json[0]
            final_summary = result_json.get("summary", "")

            print(f"[Summarize] Final summary generated for task {task_id}")
            
            # 先更新数据库
            update_success = await update_task_status(task_id, "Done", final_summary)
            print(f"[Summarize] Database update {'successful' if update_success else 'failed'} for task {task_id}")
            
            # 再发送WebSocket消息
            try:
                await send_progress(task_id, "summary", final_summary)
                print(f"[Summarize] WebSocket summary message sent for task {task_id}")
            except Exception as e:
                print(f"[Summarize] Error sending summary message: {e}")
                # 即使发送WebSocket消息失败，我们已经更新了数据库，所以可以继续返回结果

            return {
                "summary": final_summary,
                "summaries": summaries,
                "keyword": keyword,
                "prompt": prompt.replace("*", "").replace("#", ""),
                "justification": result_json.get("justification", "") if isinstance(result_json, dict) else "",
                "exclusion": result_json.get("exclusion", "") if isinstance(result_json, dict) else ""
            }
        except Exception as e:
            print(f"[Summarize] Error in final summary generation for task {task_id}: {e}")
            await update_task_status(task_id, "Failed", str(e))
            
            try:
                await send_progress(task_id, "error", str(e))
            except Exception as ws_e:
                print(f"[Summarize] Error sending summary generation error message: {ws_e}")
            
            raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print(f"[Summarize] Error in summarize_videos for task {task_id}: {e}")
        await update_task_status(task_id, "Failed", str(e))
        
        try:
            await send_progress(task_id, "error", str(e))
        except Exception as ws_e:
            print(f"[Summarize] Error sending overall error message: {ws_e}")
        
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