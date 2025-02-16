import argparse
from utils import (query_response_from_tikapi, download_video_from_response, describe_video,
                   create_bigquery_table, write_summary_to_bq, final_summary)
from dotenv import load_dotenv
import os
from tqdm import tqdm


load_dotenv("test.env")
PROMPT = "Summarize this video. "


def main():
    parser = argparse.ArgumentParser(description="Process keyword and cache usage.")
    parser.add_argument("--keyword", type=str, required=True, help="Keyword to process")
    parser.add_argument("--minimal_video_number", type=int, default=40, help="Number of videos to download. ")
    parser.add_argument("--use_bq_cache", action="store_true", 
                        help="Flag to use existing table in BQ. By default, the table will be re-initialized. ")

    args = parser.parse_args()
        
    # Query response from tikapi
    print("Getting response from tikapi...")
    response_ls = query_response_from_tikapi(keyword=args.keyword, video_number=args.minimal_video_number)
    print(f"Take {len(response_ls)} queries to reach more than {args.minimal_video_number} videos. ")
    
    # Before iterate through each response, make sure the bigquery table is created in advance
    create_bigquery_table(table_id=args.keyword)
    
    # Iterate through responses
    for idx, response in enumerate(response_ls):
        print(f"Processing Response {idx}: with {len(response.json()['item_list'])} videos. Now downloading...")
        # Download videos to local from response list
        paths = download_video_from_response(response, directory=args.keyword)
        # Describe each video from paths
        for path in tqdm(paths, desc="Generating description of videos and insert to BQ..."):
            summary = describe_video(path, PROMPT)
            write_summary_to_bq(
                project_id=os.environ["GCP_PROJECT_ID"],
                dataset_id=os.environ["BQ_DATASET_ID"],
                table_id=args.keyword,
                filename=path,
                summary=summary
            )
    print(f"Generating final summary of those videos. ")
    result = final_summary(
        project_id=os.environ["GCP_PROJECT_ID"],
        dataset_id=os.environ["BQ_DATASET_ID"],
        table_id=args.keyword
    )
    print(result)


if __name__ == "__main__":
    main()
