import os
import time
import requests

from config import HEADERS, DOWNLOAD_CHUNK_SIZE, MAX_RETRIES, RETRY_DELAY


def download_file(
    url: str,
    save_path: str,
    progress_callback=None,
) -> str:
    for attempt in range(MAX_RETRIES):
        try:
            headers = {**HEADERS, "Range": "bytes=0-"}
            resp = requests.get(url, headers=headers, stream=True, timeout=30)
            resp.raise_for_status()

            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            start_time = time.time()

            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            elapsed = time.time() - start_time
                            speed = downloaded / elapsed if elapsed > 0 else 0
                            percent = downloaded / total_size * 100
                            remaining = (total_size - downloaded) / speed if speed > 0 else 0
                            progress_callback(percent, downloaded, total_size, speed, remaining)

            return save_path

        except (requests.RequestException, IOError) as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise e
