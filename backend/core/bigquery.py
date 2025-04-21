from google.cloud import bigquery
import os


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
    rows_to_insert = [{"filename": filename, "summary": summary}]
    client.insert_rows_json(table_ref, rows_to_insert)


def grab_summaries_from_bq(project_id, dataset_id, table_id):
    bq_client = bigquery.Client(project=project_id)
    query = f"SELECT summary FROM `{project_id}.{dataset_id}.{table_id}`"
    query_job = bq_client.query(query)
    results = query_job.result()
    return [row['summary'] for idx, row in enumerate(results)]