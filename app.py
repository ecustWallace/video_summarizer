from fastapi import FastAPI, Request, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from utils import (query_response_from_tikapi, download_video_from_response, describe_video,
                   create_bigquery_table, write_summary_to_bq, final_summary, grab_summaries_from_bq)
from tqdm import tqdm
from jinja2 import Environment, FileSystemLoader
import asyncio
from google import genai

# Load environment variables
load_dotenv("test.env")

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles

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
          "You do not need to fulfill all of the above but use them as a reference. Return only the summary itself."
          "Please directly return the result, without any redundant word like 'okay sure' or 'here is a summary'.")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the UI for keyword input and display results"""
    template = templates.get_template("index.html")
    return HTMLResponse(content=template.render(summary=None, keyword=None, progress=None, summaries=None), status_code=200)

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


class EvaluationRequest(BaseModel):
    summary: str  # 用户的最终 summary
    small_summaries: list  # 原始的多个 small summaries

def generate_prompt(summary, small_summaries):
    """
    生成 Prompt，提供给 GPT-4 / Claude / Gemini
    """
    prompt = f"""
    You are an expert in summarization evaluation.
    
    Here are multiple source summaries from different videos:
    {'\n------------------------\n'.join([f"{idx+1}. "+ summary for idx, summary in enumerate(small_summaries)])}

    Below is the final summary produced from these sources:
    {summary}

    Please evaluate the final summary:
    1. For each sentence in the final summary, determine if the sources are correct.
       - If the sources are shown as ALL, that means it includes ALL sources, meaning recall will be 100%. 
       - Provide Precision and Recall scores. 
       - Precision 1 means all returned sources are correct, i.e, no incorrect source. 
       - Recall 1 means returned sources covered all correct sources, i.e, no missing source.  
       - If there is a mistake, specify the issue by telling what are the incorrect sources and missing sources.
    
    2. Identify any important content from the source summaries that is missing in the final summary.
       - Provide the missing sentences and their original source(s).
       - Remember, a missing content is considered important when it's frequent and it's hugely different from each sentence of the final summary. 

    Return your response in the following structured JSON format:
    {{
        "precision_recall": [
            {{
                "text": "Final summary sentence",
                "precision": 0.8,
                "recall": 0.9,
                "errors": ["Incorrect source: [1, 2]", "Missing source: [3, 4]"]
            }}
        ],
        "missing_sentences": [
            {{ "text": "Important missing sentence", "source": [2, 5] }}
        ]
    }}
    """

    return prompt

@app.post("/evaluate_summary")
async def evaluate_summary(data: EvaluationRequest):
    """
    调用大模型来评估最终摘要质量
    """
    prompt = generate_prompt(data.summary, data.small_summaries)

    client = genai.Client(api_key=os.environ["GEMINI_KEY"])
    response = client.models.generate_content(
        model='gemini-1.5-pro',
        contents=[prompt]
    )
    evaluation_result = response.text.strip("```json").strip("```")
    try:
        import json
        evaluation_json = json.loads(evaluation_result)
        print("success")
        return evaluation_json
    except json.JSONDecodeError:
        print("error")
        return {"error": "Failed to parse model response"}


@app.post("/", response_class=HTMLResponse)
async def summarize_videos(
    request: Request, 
    keyword: str = Form(...),
    video_number: int = Form(None),
    skip_tikapi: bool = Form(False)
):
    # ✅ 如果跳过 TikAPI，则直接从 BigQuery 读取数据
    print("Summarize Videos")
    if skip_tikapi:
        await send_progress("✅ Skipping TikAPI, retrieving past summaries from BigQuery...")
        await send_progress("📊 Generating the final summary...")
        summaries = grab_summaries_from_bq(
            project_id=os.environ["GCP_PROJECT_ID"],
            dataset_id=os.environ["BQ_DATASET_ID"],
            table_id=keyword
        )
        result = final_summary(summaries, table_id=keyword)
        template = templates.get_template("index.html")
        return HTMLResponse(content=template.render(
            summary=result,
            summaries=summaries,
            keyword=keyword
        ), status_code=200)

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
            try:
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
            except:
                await send_progress(f"TikApi Downloading is currently unavailable, directly generating the final summary. ")

        # 生成 summaries 和最终 summary
        summaries = grab_summaries_from_bq(
            project_id=os.environ["GCP_PROJECT_ID"],
            dataset_id=os.environ["BQ_DATASET_ID"],
            table_id=keyword
        )

        # 生成最终摘要
        await send_progress("📊 Generating the final summary...")
        result = final_summary(summaries, table_id=keyword)

        # 渲染 HTML，传递 `result`（最终总结）和 `summaries`（各个视频摘要）
        template = templates.get_template("index.html")
        return HTMLResponse(content=template.render(summary=result, summaries=summaries, keyword=keyword, progress=None), status_code=200)


    except Exception as e:
        return HTMLResponse(content=f"<h2>Error: {str(e)}</h2>", status_code=500)
