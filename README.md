# TikTok Video Summarizer

## Overview

This project automates the process of fetching TikTok videos based on a given keyword, downloading them, generating textual descriptions, storing the descriptions in Google BigQuery, and finally summarizing the key discussion topics using Gemini AI.

## Features

- Fetch TikTok videos based on a specific keyword via TikAPI
- Download the videos locally
- Generate descriptions for each video using Gemini AI
- Store descriptions in Google BigQuery
- Summarize the hot topics discussed in the videos

## Requirements

Before running the script, ensure you have the following:

- Python 3.8+
- A valid **TikAPI** key for fetching TikTok videos
- A **Google Cloud Platform (GCP)** project with **BigQuery** enabled
- A **Gemini AI** API key
- A `.env` file containing the required credentials:

### `.env` File

```
TIKAPI_KEY=your_tikapi_key
GEMINI_KEY=your_gemini_api_key
GCP_PROJECT_ID=your_gcp_project_id
BQ_DATASET_ID=your_bigquery_dataset_id
```

## Installation

1. Clone the repository:
   ```sh
   git clone https://github.com/your-repo/tiktok-summarizer.git
   cd tiktok-summarizer
   ```
2. Create a virtual environment and activate it:
   ```sh
   python -m venv .venv
   source .venv/bin/activate  # On macOS/Linux
   .venv\Scripts\activate    # On Windows
   ```
3. Install the required dependencies:
   ```sh
   pip install -r requirements.txt
   ```

## Usage

Run the script with the following command:

```sh
python main.py --keyword "NBA" --minimal_video_number 40 --use_bq_cache
```

### Command-line Arguments

- `--keyword` (**required**): The keyword to fetch videos for.
- `--minimal_video_number` (**optional**, default=40): The minimum number of videos to process.
- `--use_bq_cache` (**optional**, flag): If set, reuses the existing BigQuery table instead of creating a new one.

## Workflow

1. **Fetch TikTok Videos:** The script queries TikAPI for videos based on the specified keyword.
2. **Download Videos:** The videos are saved locally for processing.
3. **Generate Descriptions:** Each video is analyzed using Gemini AI to generate a summary.
4. **Store in BigQuery:** The descriptions are inserted into a BigQuery table.
5. **Final Summary:** A final summary is generated using Gemini AI based on all stored descriptions.

## Functions Breakdown

### `main.py`

- ``: Fetches video responses from TikAPI.
- ``: Saves TikTok videos locally.
- ``: Generates a description for a given video using Gemini AI.
- ``: Creates a BigQuery table to store video summaries.
- ``: Writes individual video descriptions to BigQuery.
- ``: Generates a final summary from all stored descriptions.

## Example Output

```
Getting response from tikapi...
Take 5 queries to reach more than 40 videos.
Processing Response 0: with 10 videos. Now downloading...
Generating description of videos and insert to BQ...
...
Generating final summary of those videos.
Final Summary: "The trending topics on TikTok under the keyword 'NBA' include recent game highlights, player performances, trade rumors, and fan reactions."
```

## Troubleshooting

- **Issue:** Unable to connect to TikAPI
  - Ensure your `TIKAPI_KEY` is correct and active.
- **Issue:** BigQuery table creation fails
  - Check that your GCP project and dataset exist.
- **Issue:** Gemini AI API request fails
  - Ensure your `GEMINI_KEY` is valid and your GCP billing is active.

## License

This project is licensed under the MIT License.

