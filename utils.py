from tikapi import TikAPI
import os
from google import genai
from google.cloud import bigquery
import time


def _count_item_number(item_list):
    return sum([True if 'downloadAddr' in item['video'] or 'playAddr' in item['video'] else False
                for item in item_list])


def query_response_from_tikapi(keyword="NBA", video_number=100, query_upper_limit=10):
    api = TikAPI(os.environ["TIKAPI_KEY"])
    current_query, current_video = 0, 0
    response_list = []
    next_cursor = None
    while current_query < query_upper_limit and current_video < video_number:
        response = api.public.search(
            category="videos",
            query=keyword,
            nextCursor=next_cursor
        )
        item_list = response.json()['item_list']
        current_video += _count_item_number(item_list)
        current_query += 1
        next_cursor = response.json()['nextCursor']
        response_list.append(response)
    return response_list


def download_video_from_response(response, directory="NBA"):
    if directory:
        os.makedirs(directory, exist_ok=True)
    paths = []
    for item in response.json()['item_list']:
        item = item['video']
        if 'playAddr' not in item and 'downloadAddr' not in item:
            # Not downloadable, skip
            continue
        if 'playAddr' in item:
            response.save_video(item['playAddr'], f"{directory}/{item['id']}.mp4")
        elif 'downloadAddr' in item:
            response.save_video(item['downloadAddr'], f"{directory}/{item['id']}.mp4")
        paths.append(f"{directory}/{item['id']}.mp4")
    return paths

            
def describe_video(video_path, prompt, model="gemini-2.0-flash"):
    client = genai.Client(api_key=os.environ["GEMINI_KEY"])
    video_file = client.files.upload(file=video_path)
    time.sleep(2)
    for query_idx in range(3):
        # Retry 3 times to wait finishing file uploading
        try:
            response = client.models.generate_content(
                model=model,
                contents=[video_file, prompt]
            )
            break
        except:
            print(f"{query_idx+1} time failed to query Gemini, wait for 5 more secs.")
            time.sleep(5)
    return response.text


def create_bigquery_table(table_id, project_id='glossy-reserve-450922-p9', dataset_id='video_summary'):
    schema = [
        {"name": "filename", "type": "STRING", "mode": "REQUIRED"},
        {"name": "summary", "type": "STRING", "mode": "NULLABLE"}
    ]
    client = bigquery.Client()
    table_ref = f"{project_id}.{dataset_id}.{table_id}"
    table = bigquery.Table(table_ref, schema=schema)
    client.create_table(table, exists_ok=True)


def write_summary_to_bq(project_id, dataset_id, table_id, filename, summary):
    client = bigquery.Client()
    table_ref = f"{project_id}.{dataset_id}.{table_id}"

    rows_to_insert = [
        {"filename": filename, "summary": summary}
    ]
    client.insert_rows_json(table_ref, rows_to_insert)


def final_summary(project_id, dataset_id, table_id, model="gemini-2.0-flash"):
    bq_client = bigquery.Client(project=project_id)
    
    query = f"""
        SELECT summary
        FROM `{project_id}.{dataset_id}.{table_id}`
    """

    query_job = bq_client.query(query)
    results = query_job.result()

    # Concatenate all summary together
    summary_ls = [row['summary'] for row in results]
    summary_str = "------------\n".join(summary_ls+[''])
    
    # Calculate tokens first to avoid exceeding upper limit
    client = genai.Client(api_key=os.environ["GEMINI_KEY"])
    response = client.models.count_tokens(
        model=model,
        contents=[summary_str],
    )
    token_number = response.total_tokens
    
    batch_num = token_number // 1048576 + 1
    batch_size = max(1, int(len(summary_ls)//batch_num))
    print(batch_num)
    
    summary_ls = []
    
    # Batch Processing each input
    for batch_id in range(batch_num):
        all_summary_batch = [row['summary'] for row in summary_ls[(batch_id*batch_size):(batch_id+1)*batch_size]]
        all_summary_batch_str = '-----------------\n'.join(all_summary_batch + [''])
        # Query GEMINI
        prompt_final_summary = ("All above are a series of descriptions from TikTok videos under keyword {}. "
                                "Please generate a summary for those, generally about what's the hot topics people "
                                "are discussing under {}. Please directly return the result, without any word like okay sure.").format(table_id, table_id)
        prompt = all_summary_batch_str + prompt_final_summary

        # Send text to Gemini
        response = client.models.generate_content(
            model=model,
            contents=[prompt]
        )
        summary_ls.append(response.text)
        
    if batch_num == 1:
        return summary_ls[0]
    else:
        summary_ls = summary_ls + ['']
        summary_all = "------------\n".join(summary_ls)
        prompt_all_summary = ("All above are the summaries of different batches of TikTok videos. Please merge them together in a reasonable way. ")
        prompt = summary_all + prompt_all_summary
        response = client.models.generate_content(
            model=model,
            contents=[prompt]
        )
        return response.text