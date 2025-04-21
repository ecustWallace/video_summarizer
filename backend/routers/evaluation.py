from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import json
from google import genai
from core.gemini import generate_prompt
from core.utils import send_progress

router = APIRouter()

class EvaluationRequest(BaseModel):
    summary: str
    small_summaries: list[str]

@router.post("/api/evaluate")
async def evaluate_summary(data: EvaluationRequest):
    await send_progress("📊 Generating the evaluation of summaries...")
    prompt = generate_prompt(data.summary, data.small_summaries)

    client = genai.Client(api_key=os.environ["GEMINI_KEY"])
    response = client.models.generate_content(
        model='gemini-1.5-pro',
        contents=[prompt]
    )
    evaluation_result = response.text.strip("```json").strip("```")

    try:
        evaluation_json = json.loads(evaluation_result)
        return evaluation_json
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse model response")
