import os
import sys

APP_NAME = "BilibiliAudioDownloader"
APP_VERSION = "1.0.0"

DEFAULT_SAVE_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "BilibiliAudio")

DEFAULT_FORMAT = "m4a"
SUPPORTED_FORMATS = ["m4a", "mp3"]

API_VIDEO_INFO = "https://api.bilibili.com/x/web-interface/view"
API_PLAY_URL = "https://api.bilibili.com/x/player/playurl"

REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_DELAY = 2

DOWNLOAD_CHUNK_SIZE = 8192

MAX_WORKERS = 3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com",
}

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.join(os.path.dirname(sys.executable), "_internal")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FFMPEG_PATH = os.path.join(BASE_DIR, "resources", "ffmpeg.exe")
if not os.path.isfile(FFMPEG_PATH):
    FFMPEG_PATH = "ffmpeg"
