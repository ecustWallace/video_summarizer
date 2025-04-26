from google.cloud import bigquery
import os

# 获取项目ID
def get_project_id():
    project_id = os.getenv("GCP_PROJECT_ID")
    if not project_id:
        print("[BigQuery WARNING] GCP_PROJECT_ID environment variable is not set!")
        project_id = "glossy-reserve-450922-p9"  # 使用硬编码的默认值
        print(f"[BigQuery] Using default PROJECT_ID: {project_id}")
    return project_id

# 获取数据集ID
def get_dataset_id():
    dataset_id = os.getenv("BQ_DATASET_ID")
    if not dataset_id:
        print("[BigQuery WARNING] BQ_DATASET_ID environment variable is not set!")
        dataset_id = "video_summary"  # 使用硬编码的默认值
        print(f"[BigQuery] Using default DATASET_ID: {dataset_id}")
    return dataset_id

def create_bigquery_table(table_id, project_id=None, dataset_id=None):
    if project_id is None:
        project_id = get_project_id()
    if dataset_id is None:
        dataset_id = get_dataset_id()
    
    try:
        schema = [
            {"name": "filename", "type": "STRING", "mode": "REQUIRED"},
            {"name": "summary", "type": "STRING", "mode": "NULLABLE"}
        ]
        client = bigquery.Client(project=project_id)
        table_ref = f"{project_id}.{dataset_id}.{table_id}"
        table = bigquery.Table(table_ref, schema=schema)
        client.create_table(table, exists_ok=True)
        print(f"[BigQuery] Successfully created or verified table: {table_ref}")
    except Exception as e:
        print(f"[BigQuery ERROR] Failed to create table: {e}")
        raise


def write_summary_to_bq(project_id=None, dataset_id=None, table_id=None, filename=None, summary=None):
    if project_id is None:
        project_id = get_project_id()
    if dataset_id is None:
        dataset_id = get_dataset_id()
    if not table_id or not filename or not summary:
        print("[BigQuery ERROR] Missing required parameters for write_summary_to_bq")
        return
    
    try:
        client = bigquery.Client(project=project_id)
        table_ref = f"{project_id}.{dataset_id}.{table_id}"
        rows_to_insert = [{"filename": filename, "summary": summary}]
        client.insert_rows_json(table_ref, rows_to_insert)
        print(f"[BigQuery] Successfully inserted row into {table_ref}")
    except Exception as e:
        print(f"[BigQuery ERROR] Failed to insert row: {e}")
        raise


def grab_summaries_from_bq(project_id=None, dataset_id=None, table_id=None):
    if project_id is None:
        project_id = get_project_id()
    if dataset_id is None:
        dataset_id = get_dataset_id()
    if not table_id:
        print("[BigQuery ERROR] Missing table_id parameter for grab_summaries_from_bq")
        return []
    
    try:
        bq_client = bigquery.Client(project=project_id)
        query = f"SELECT summary FROM `{project_id}.{dataset_id}.{table_id}`"
        print(f"[BigQuery] Executing query: {query}")
        query_job = bq_client.query(query)
        results = query_job.result()
        summaries = [row['summary'] for idx, row in enumerate(results)]
        print(f"[BigQuery] Retrieved {len(summaries)} summaries from {table_id}")
        return summaries
    except Exception as e:
        print(f"[BigQuery ERROR] Failed to grab summaries: {e}")
        return []