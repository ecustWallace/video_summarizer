from fastapi import FastAPI, Request, Form, WebSocket, WebSocketDisconnect, HTTPException
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
import json

# Load environment variables
load_dotenv("test.env")  # Or the appropriate path to your .env file

app = FastAPI()

# Set up Jinja2 template directory
templates = Environment(loader=FileSystemLoader("templates"))

# Store active WebSocket connections
connected_clients = {}

class SummarizeRequest(BaseModel):
    keyword: str
    video_number: int = 40  # Default value
    skip_download: bool = False  # Add skip_download field, default to False


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
    You are an AI expert in evaluating text summarization accuracy. Your task is to evaluate the **Final Summary** based on the provided **Source Summaries**. 
    
    Here are multiple source summaries from different videos:
    {'\n------------------------\n'.join([f"{idx+1}. "+ summary for idx, summary in enumerate(small_summaries)])}

    Below is the final summary produced from these sources:
    {summary}

    ### **Evaluation Criteria**
    1. **Sentence-Level Precision & Recall Calculation**
       - Each sentence in the **Final Summary** should be traced back to its **original Source Summaries**.
       - Each Source Summary is separated by a line separator.
       - Your goal is to determine whether the references provided for each sentence in the Final Summary are correct.
       - **Reference Format:** Each sentence should list the index of its original Source Summaries. If the sentence is a generalization that includes information from all sources, mark it as **(ALL)**.

       #### **Precision Calculation**
       - **Precision = Correct References / (Correct References + Incorrect References)**
       - **Precision 1.0:** If all listed references are correct (i.e., no incorrect source is included).
       - **Precision < 1.0:** If any incorrect source is included.
       - Example: If a sentence refers to sources **[1, 3]**, but only **1** is correct and **3** is incorrect, then:
         - Correct References = 1, Incorrect References = 1
         - **Precision = 1 / (1+1) = 0.5**

       #### **Recall Calculation**
       - **Recall = Correct References / (Correct References + Missing References)**
       - **Recall 1.0:** If all correct sources are included.
       - **Recall < 1.0:** If some correct sources are missing.
       - Example: If a sentence should refer to **[1, 2, 3]**, but only lists **[1]**, then:
         - Correct References = 1, Missing References = 2
         - **Recall = 1 / (1+2) = 0.33**

       #### **How to Identify Mistakes**
       - **Incorrect Sources:** If a reference includes sources that do not contain the information in the sentence.
       - **Missing Sources:** If the sentence should include references to sources that it does not list.
       
    2. Missing Content Identification

        Identify important content from the Source Summaries that is missing in the Final Summary.
        A content is considered important if:
        It appears frequently across multiple sources.
        It contains unique or major information that is not covered in any sentence of the Final Summary.
        Provide the missing sentence and list the sources where it appeared.
        
    3. Tell the reason of your judgement, as detailed as possible. 

    Return ALL your response in the following structured JSON format:
    IMPORTANT: Please make sure the output value is able to be parsed by json.loads.
    {{
        "precision_recall": [
            {{
                "text": "Final summary sentence",
                "precision": 0.8,
                "recall": 0.9,
                "errors": ["Incorrect source: [1, 2]", "Missing source: [3, 4]", "Reasons: Source 1 is blablabla, source 2 is blablabla..."]
            }}
        ],
        "missing_sentences": [
            {{ "text": "Important missing sentence", "source": [2, 5]., "reasons": "Source 2 is blablabla."  }}
        ]
    }}
    """

    return prompt

@app.post("/evaluate_summary")
async def evaluate_summary(data: EvaluationRequest):
    """
    Call LLM to evaluate the quality of summaries
    """
    await send_progress("📊 Generating the evaluation of summaries...")
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

  
def process_summaries_from_bq(keyword):
    """Extract Summaries from BigQuery and get the final summary"""
    summaries = grab_summaries_from_bq(
        project_id=os.environ["GCP_PROJECT_ID"],
        dataset_id=os.environ["BQ_DATASET_ID"],
        table_id=keyword
    )
    if not summaries:
        raise HTTPException(status_code=404, detail=f"No summaries found for keyword: {keyword}")
    summaries = [summary.replace('\n', '') for summary in summaries]
    result, prompt = final_summary(summaries, table_id=keyword)
    return result, summaries, prompt


@app.post("/", response_class=HTMLResponse)
async def summarize_videos(
    request: Request,
    keyword: str = Form(...),
    video_number: int = Form(None),  # Allow None
    skip_download: bool = Form(False)
):
    """Process video summarization, handling skip_download and empty video_number."""
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
                    if total_processed_videos >= video_number:
                        break
                except Exception as e:
                    await send_progress(f"❌ Error during download: {e}")
                    download_success = False
                    break

            if not download_success:
                await send_progress("✅ TikAPI download failed, retrieving past summaries from BigQuery...")

        except Exception as e:
            return HTMLResponse(content=f"<h2>Error: {str(e)}</h2>", status_code=500)

    try:        
        await send_progress("📊 Generating the final summary...")
        result, summaries, prompt = process_summaries_from_bq(keyword)
        result = result.strip("```json").strip("```")
        template = templates.get_template("index.html")
        return HTMLResponse(content=template.render(
            summary=result,
            summaries=summaries,
            keyword=keyword,
            prompt=prompt.replace('*', '').replace('#', ''),
            justification=json.loads(result).get('justification', ''),
            exclusion=json.loads(result).get('exclusion', '')
        ), status_code=200)
    except Exception as e:
        return HTMLResponse(content=f"<h2>Error: {str(e)}</h2>", status_code=500)