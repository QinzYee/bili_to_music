import re
import time
import requests

from config import API_VIDEO_INFO, API_PLAY_URL, HEADERS, REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY


def extract_bvid(url: str) -> str | None:
    match = re.search(r"(BV[a-zA-Z0-9]+)", url)
    if match:
        return match.group(1)
    return None


def _request_with_retry(url: str, params: dict) -> dict:
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == 0:
                return data.get("data", {})
            raise ValueError(f"API error: code={data.get('code')}, message={data.get('message')}")
        except (requests.RequestException, ValueError) as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise e


def get_video_info(bvid: str) -> dict:
    data = _request_with_retry(API_VIDEO_INFO, {"bvid": bvid})
    pages = []
    for p in data.get("pages", []):
        pages.append({
            "cid": p.get("cid"),
            "page": p.get("page", 1),
            "part": p.get("part", ""),
        })
    return {
        "bvid": bvid,
        "title": data.get("title", ""),
        "pages": pages,
    }


def get_audio_url(bvid: str, cid: int) -> str:
    params = {
        "bvid": bvid,
        "cid": cid,
        "qn": 0,
        "fnval": 16,
        "fourk": 0,
    }
    data = _request_with_retry(API_PLAY_URL, params)
    audio_list = data.get("dash", {}).get("audio", [])
    if not audio_list:
        raise ValueError("未找到音频流")
    best_audio = max(audio_list, key=lambda a: a.get("bandwidth", 0))
    return best_audio.get("baseUrl") or best_audio.get("base_url") or best_audio.get("url")
