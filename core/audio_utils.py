import os
import subprocess

from config import FFMPEG_PATH


def is_ffmpeg_available() -> bool:
    try:
        result = subprocess.run(
            [FFMPEG_PATH, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False


def convert_audio(input_path: str, output_path: str, output_format: str) -> str:
    if output_format == "m4a":
        if input_path != output_path:
            os.replace(input_path, output_path)
        return output_path

    if output_format == "mp3":
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-vn",
            "-acodec", "libmp3lame",
            "-ab", "192k",
            output_path,
        ]
    else:
        raise ValueError(f"不支持的格式: {output_format}")

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg 错误: {result.stderr.decode('utf-8', errors='ignore')}")
    except FileNotFoundError:
        raise RuntimeError("未找到 ffmpeg，请确保 ffmpeg.exe 在 resources 目录或系统 PATH 中")

    if os.path.isfile(input_path) and input_path != output_path:
        os.remove(input_path)

    return output_path
