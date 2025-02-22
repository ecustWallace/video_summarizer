from fastapi import FastAPI, Request, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from utils import (query_response_from_tikapi, download_video_from_response, describe_video,
                   create_bigquery_table, write_summary_to_bq, final_summary)
from tqdm import tqdm
from jinja2 import Environment, FileSystemLoader
import asyncio

# Load environment variables
load_dotenv("test.env")

app = FastAPI()

# Set up Jinja2 template directory
templates = Environment(loader=FileSystemLoader("templates"))

# Store active WebSocket connections
connected_clients = {}

class SummarizeRequest(BaseModel):
    keyword: str
    video_number: int = 40

# Video summarization prompt
PROMPT = ("Summarize this video. I hope to know the following, but it depends on you to decide if those are applicable."
          "1. Describe the objects in the video, their properties, and their relationships."
          "2. Identify events happening in the video."
          "3. Explain the actions performed in the video."
          "4. Describe the overall vibe or atmosphere of the video."
          "You do not need to fulfill all of the above but use them as a reference. Return only the summary itself.")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the UI for keyword input and display results"""
    template = templates.get_template("index.html")
    return HTMLResponse(content=template.render(summary=None, keyword=None, progress=None), status_code=200)

@app.websocket("/progress")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint to send real-time progress updates"""
    await websocket.accept()
    client_id = id(websocket)
    connected_clients[client_id] = websocket
    try:
        while True:
            await asyncio.sleep(30)  # Keep the connection alive
    except WebSocketDisconnect:
        del connected_clients[client_id]

async def send_progress(message: str):
    """Send a progress update to all connected WebSocket clients"""
    disconnected_clients = []
    for client_id, client in connected_clients.items():
        try:
            await client.send_text(message)
        except Exception:
            disconnected_clients.append(client_id)

    # Remove disconnected clients
    for client_id in disconnected_clients:
        del connected_clients[client_id]

@app.post("/", response_class=HTMLResponse)
async def summarize_videos(request: Request, keyword: str = Form(...), video_number: int = Form(...)):
    """Process video summarization, strictly stopping at the requested number of videos"""
    try:
        # 1️⃣ Notify the frontend that analysis has started
        await send_progress(f"🔍 Fetching up to {video_number} videos from TikAPI...")

        # 2️⃣ Query TikAPI for videos
        response_ls = query_response_from_tikapi(keyword=keyword, video_number=video_number)
        total_queries = len(response_ls)  # Count the total number of queries
        await send_progress(f"📊 Total TikAPI queries made: {total_queries}")

        # 3️⃣ Ensure that the BigQuery table exists
        create_bigquery_table(table_id=keyword)

        # 4️⃣ Process videos, ensuring we do not exceed `video_number`
        total_processed_videos = 0  # Track processed videos

        for idx, response in enumerate(response_ls):
            if total_processed_videos >= video_number:
                break  # Stop processing if required number is reached

            await send_progress(f"📥 Downloading batch {idx+1}...")

            # Download videos from the current response batch
            paths = download_video_from_response(response, directory=keyword)
            
            # Only process the required number of videos
            for path in tqdm(paths, desc="Processing videos..."):
                if total_processed_videos >= video_number:
                    break  # Stop processing further videos

                await send_progress(f"📝 Analyzing video {total_processed_videos + 1}/{video_number}...")

                summary = describe_video(path, PROMPT)

                # Write summary to BigQuery
                write_summary_to_bq(
                    project_id=os.environ["GCP_PROJECT_ID"],
                    dataset_id=os.environ["BQ_DATASET_ID"],
                    table_id=keyword,
                    filename=path,
                    summary=summary
                )
                total_processed_videos += 1  # Increment the count

            if total_processed_videos >= video_number:
                break  # Stop further API queries

        # 5️⃣ Generate the final summary
        await send_progress("📊 Generating the final summary...")
        result = final_summary(
            project_id=os.environ["GCP_PROJECT_ID"],
            dataset_id=os.environ["BQ_DATASET_ID"],
            table_id=keyword
        )

        # 6️⃣ Notify frontend that analysis is complete
        await send_progress(f"✅ Analysis complete! Processed {total_processed_videos}/{video_number} videos.")

        # 7️⃣ Render the results in the same UI
        template = templates.get_template("index.html")
        return HTMLResponse(content=template.render(summary=result, keyword=keyword, progress=None), status_code=200)

    except Exception as e:
        return HTMLResponse(content=f"<h2>Error: {str(e)}</h2>", status_code=500)
