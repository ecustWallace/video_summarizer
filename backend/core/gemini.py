from google import genai
import os
import time
import numpy as np
import faiss
import json
from fastapi import HTTPException
from core.bigquery import grab_summaries_from_bq

PROMPT = "You are an AI assistant analyzing TikTok videos. Describe the content..."


def describe_video(video_path, prompt, model="gemini-2.0-flash"):
    client = genai.Client(api_key=os.environ["GEMINI_KEY"])
    video_file = client.files.upload(file=video_path)
    time.sleep(2)
    for query_idx in range(3):
        try:
            response = client.models.generate_content(
                model=model,
                contents=[video_file, prompt]
            )
            return response.text
        except:
            print(f"{query_idx+1} time failed to query Gemini, wait for 5 more secs.")
            time.sleep(5)


def narrow_down_summaries_by_rags(summaries, keyword, project_id, k=10):
    LOCATION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
    client = genai.Client(vertexai=True, project=project_id, location=LOCATION)
    TEXT_EMBEDDING_MODEL_ID = "text-embedding-005"

    def get_embeddings_wrapper(texts: list[str]) -> list[list[float]]:
        embeddings = []
        for i in range(0, len(texts), 5):
            time.sleep(1)
            response = client.models.embed_content(
                model=TEXT_EMBEDDING_MODEL_ID, contents=texts[i: i + 5]
            )
            embeddings.extend([e.values for e in response.embeddings])
        return embeddings

    embeddings = get_embeddings_wrapper(summaries)
    index = faiss.IndexFlatL2(768)
    index.add(np.array(embeddings))
    query_emb = get_embeddings_wrapper([keyword])
    D, I = index.search(np.array(query_emb, dtype='float32'), k=k)
    return [summaries[idx] for idx in I[0]]


def final_summary(summary_ls, table_id, model="gemini-2.0-flash"):
    client = genai.Client(api_key=os.environ["GEMINI_KEY"])
    summary_str = "\n------------\n".join(summary_ls + [''])
    response = client.models.count_tokens(model=model, contents=[summary_str])
    token_number = response.total_tokens

    batch_num = token_number // 1048576 + 1
    batch_size = max(1, int(len(summary_ls) // batch_num))
    final_summary_ls = []

    for batch_id in range(batch_num):
        all_summary_batch = [f"{idx+1}. "+row.replace('#', '') for idx, row in enumerate(summary_ls[batch_id * batch_size:(batch_id + 1) * batch_size])]
        all_summary_batch_str = '\n-----------------\n'.join(all_summary_batch + [''])

        prompt = (f"You are an AI analyzing TikTok video summaries under the keyword '{table_id}'."
                  f" Summarize them, justify the source for each sentence, explain exclusions,"
                  f" and return in JSON format with keys 'summary', 'justification', 'exclusion'.")
        prompt += "{'summary': '...', 'justification': '...', 'exclusion': '...'}"

        response = client.models.generate_content(
            model=model,
            contents=[all_summary_batch_str + prompt]
        )
        final_summary_ls.append(response.text)

    if batch_num == 1:
        return final_summary_ls[0], prompt
    else:
        merged = "\n------------\n".join(final_summary_ls)
        merge_prompt = "Merge the summaries above into one."
        response = client.models.generate_content(
            model=model,
            contents=[merged + merge_prompt]
        )
        return response.text, merge_prompt


def process_summaries_from_bq(keyword, rag=True):
    summaries = grab_summaries_from_bq(
        project_id=os.environ["GCP_PROJECT_ID"],
        dataset_id=os.environ["BQ_DATASET_ID"],
        table_id=keyword
    )
    if not summaries:
        raise HTTPException(status_code=404, detail=f"No summaries found for keyword: {keyword}")
    if rag:
        summaries = narrow_down_summaries_by_rags(summaries, keyword, os.environ["GCP_PROJECT_ID"])
    summaries = [summary.replace('\n', '') for summary in summaries]
    result, prompt = final_summary(summaries, table_id=keyword)
    return result, summaries, prompt


def generate_prompt(summary, small_summaries):
    sources = '\n------------------------\n'.join([f"{idx+1}. "+ s for idx, s in enumerate(small_summaries)])
    return f"""
You are an AI expert in evaluating text summarization accuracy. Your task is to evaluate the **Final Summary** based on the provided **Source Summaries**.

Here are multiple source summaries from different videos:
{sources}

Below is the final summary produced from these sources:
{summary}

### Evaluation Criteria
1. Sentence-Level Precision & Recall Calculation
2. Missing Content Identification
3. Justify all decisions

Return ALL your response in the following JSON format. IMPORTANT: It must be parseable with json.loads.
{{
    "precision_recall": [{{
        "text": "Final summary sentence",
        "precision": 0.8,
        "recall": 0.9,
        "errors": ["Incorrect source: [1, 2]", "Missing source: [3, 4]", "Reasons: explanation"]
    }}],
    "missing_sentences": [{{ "text": "Missing sentence", "source": [2, 5], "reasons": "Explanation" }}]
}}
"""
