# router/task.py
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import text, exc # Import exc for exception handling
from database import engine
import logging # Optional: Add logging for better debugging
from .summarize import summarize_videos

router = APIRouter()
logger = logging.getLogger(__name__) # Optional: Logger setup

# --- Model for creating a task ---
class TaskCreateRequest(BaseModel):
    email: str
    keyword: str
    number: int # This is the number of videos specified during creation
    skip_download: bool

# --- Model for the object returned by GET /api/tasks ---
# Define this explicitly for clarity and potential reuse
class TaskInfo(BaseModel):
    id: int
    keyword: str
    video_number: int # Let's call it video_number consistently in the response
    status: str
    summary: str | None = None
    created_at: str | None = None

# --- Endpoint to create a new task ---
@router.post("/api/tasks/create", status_code=201) # Use 201 Created status code
async def create_task(task: TaskCreateRequest, background_tasks: BackgroundTasks):
    """Creates a new task in the database."""
    print(f"[Task] Creating task with skip_download: {task.skip_download}")
    insert_query = text("""
        INSERT INTO test (user_email, keyword, number)
        VALUES (:email, :keyword, :number)
        RETURNING id, keyword, number, user_email, status, summary, created_at
    """)
    try:
        with engine.connect() as conn:
            result = conn.execute(
                insert_query,
                {
                    "email": task.email,
                    "keyword": task.keyword,
                    "number": task.number
                }
            )
            conn.commit()
            new_task_row = result.fetchone()
            if new_task_row is None:
                raise HTTPException(status_code=500, detail="Failed to create task.")
                
            print(f"[Task] Task created with ID: {new_task_row.id}")
            # --- Schedule the summarize_videos function ---
            background_tasks.add_task(
                summarize_videos,
                task_id=new_task_row.id,
                user_email=task.email,
                keyword=task.keyword,
                video_number=task.number,
                skip_download=task.skip_download
            )
            print(f"[Task] Background task scheduled for task {new_task_row.id}")

            return {
                "task": TaskInfo(
                    id=new_task_row.id,
                    keyword=task.keyword,
                    video_number=task.number,
                    status=new_task_row.status,
                    summary=new_task_row.summary,
                    created_at=str(new_task_row.created_at) if new_task_row.created_at else None
                )
            }
    except exc.SQLAlchemyError as e:
        logger.error(f"Database error creating task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error occurred.")
    except Exception as e:
        logger.error(f"Unexpected error creating task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


# --- Endpoint to get tasks for a user ---
@router.get("/api/tasks", response_model=dict[str, list[TaskInfo]]) # Use response_model for validation/docs
async def get_tasks(email: str = Query(..., description="Email of the user whose tasks to retrieve")):
    """Retrieves a list of tasks for the specified user."""
    select_query = text("""
        SELECT id, keyword, number, status, summary, created_at
        FROM test
        WHERE user_email = :email
        ORDER BY created_at DESC
    """)
    try:
        with engine.connect() as conn:
            result = conn.execute(select_query, {"email": email})
            # Map database rows to TaskInfo model
            tasks = [
                TaskInfo(
                    id=row.id,
                    keyword=row.keyword,
                    video_number=row.number,
                    status=row.status,
                    summary=row.summary,
                    created_at=str(row.created_at) if row.created_at else None
                )
                for row in result
            ]
        return {"tasks": tasks}
    except exc.SQLAlchemyError as e:
        logger.error(f"Database error fetching tasks for {email}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error occurred.")
    except Exception as e:
        logger.error(f"Unexpected error fetching tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

# --- Endpoint to delete a task ---
@router.delete("/api/tasks/delete/{task_id}", status_code=204) # Use 204 No Content for successful deletion
async def delete_task(task_id: int):
    """Deletes a task by its ID."""
    delete_query = text("DELETE FROM test WHERE id = :task_id RETURNING id") # RETURNING helps confirm deletion
    try:
        with engine.connect() as conn:
            result = conn.execute(delete_query, {"task_id": task_id})
            conn.commit()
            if result.fetchone() is None:
                 # Optional: Return 404 if the task didn't exist
                 raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
            # No need to return a message body for 204
            return None
    except exc.SQLAlchemyError as e:
        logger.error(f"Database error deleting task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error occurred.")
    except Exception as e:
        logger.error(f"Unexpected error deleting task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

# Note: The /api/tasks/summarize endpoint and its dependencies
# (SummaryRequest model, etc.) are assumed to be in a different file
# (like your original 'summarize.py' or similar) and remain unchanged.
# Make sure the SummaryRequest model in that file still expects:
# keyword: str
# video_number: int | None = None
# skip_download: bool = False
# email: str
# task_id: int