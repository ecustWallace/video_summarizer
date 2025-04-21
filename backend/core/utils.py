from tikapi import TikAPI
import os


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
    print(response.status_code)
    if directory:
        os.makedirs(directory, exist_ok=True)
    paths = []
    for item in response.json()['item_list']:
        item = item['video']
        if 'playAddr' not in item and 'downloadAddr' not in item:
            continue
        if 'downloadAddr' in item:
            response.save_video(item['downloadAddr'], f"{directory}/{item['id']}.mp4")
        elif 'playAddr' in item:
            response.save_video(item['playAddr'], f"{directory}/{item['id']}.mp4")
        paths.append(f"{directory}/{item['id']}.mp4")
    return paths


connected_clients = {}  # key: websocket client id, value: WebSocket


async def send_progress(message: str):
    disconnected_clients = []
    for client_id, client in connected_clients.items():
        try:
            await client.send_text(message)
        except Exception:
            disconnected_clients.append(client_id)

    for client_id in disconnected_clients:
        del connected_clients[client_id]