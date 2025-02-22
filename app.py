from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from utils import (query_response_from_tikapi, download_video_from_response, describe_video,
                   create_bigquery_table, write_summary_to_bq, final_summary)
from tqdm import tqdm
from jinja2 import Environment, FileSystemLoader
import uvicorn

# 加载环境变量
load_dotenv("test.env")

# FastAPI 实例
app = FastAPI()

# 设置 Jinja2 模板目录
templates = Environment(loader=FileSystemLoader("templates"))

# 视频摘要提示词
PROMPT = ("Summarize this video. I hope to know the following, but it depends on you to decide if those are applicable."
          "1. Tell what are the objects in the video, the properties of them, and what's the relationship between them."
          "2. Tell what events are happening in this video. "
          "3. Tell what are the actions done in the video. "
          "4. Tell what's the vibe under this video. "
          "You don't need to satisfy all above, but just take a reference. No need to return result as a bullet, "
          "but just directly return the summary value, without any word like okay sure. ")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """渲染 UI，支持关键词输入"""
    template = templates.get_template("index.html")
    return HTMLResponse(content=template.render(summary=None, keyword=None), status_code=200)

@app.post("/", response_class=HTMLResponse)
async def summarize_videos(request: Request, keyword: str = Form(...)):
    """获取视频摘要并返回到同一个页面"""
    try:
        # 查询视频
        response_ls = query_response_from_tikapi(keyword=keyword, video_number=40)
        create_bigquery_table(table_id=keyword)

        for idx, response in enumerate(response_ls):
            paths = download_video_from_response(response, directory=keyword)
            for path in tqdm(paths, desc="Processing videos..."):
                summary = describe_video(path, PROMPT)
                write_summary_to_bq(
                    project_id=os.environ["GCP_PROJECT_ID"],
                    dataset_id=os.environ["BQ_DATASET_ID"],
                    table_id=keyword,
                    filename=path,
                    summary=summary
                )

        # 生成最终摘要
        result = final_summary(
            project_id=os.environ["GCP_PROJECT_ID"],
            dataset_id=os.environ["BQ_DATASET_ID"],
            table_id=keyword
        )

        # 渲染 HTML，显示结果
        template = templates.get_template("index.html")
        return HTMLResponse(content=template.render(summary=result, keyword=keyword), status_code=200)

    except Exception as e:
        return HTMLResponse(content=f"<h2>Error: {str(e)}</h2>", status_code=500)
    


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)

