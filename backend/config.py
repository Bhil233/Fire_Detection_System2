from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()

QWEN_API_KEY = os.getenv("QWEN_API_KEY", "") or os.getenv("DASHSCOPE_API_KEY", "")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-vl-plus")
QWEN_BASE_URL = os.getenv(
    "QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
).rstrip("/")
QWEN_API_URL = f"{QWEN_BASE_URL}/chat/completions"


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _to_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


SCRIPT_UPLOADER_ENABLED = _to_bool(os.getenv("SCRIPT_UPLOADER_ENABLED"), True)
SCRIPT_UPLOADER_WATCH_DIR = os.getenv("SCRIPT_UPLOADER_WATCH_DIR", "detected_frames")
DATA_IMAGE_DIR = os.getenv("DATA_IMAGE_DIR", "data_image")
SCRIPT_UPLOADER_ENDPOINT = os.getenv(
    "SCRIPT_UPLOADER_ENDPOINT",
    "http://127.0.0.1:8000/api/script/detect-fire",
)
SCRIPT_UPLOADER_POLL_INTERVAL = _to_float(os.getenv("SCRIPT_UPLOADER_POLL_INTERVAL"), 0.5)
SCRIPT_UPLOADER_MIN_UPLOAD_INTERVAL = _to_float(
    os.getenv("SCRIPT_UPLOADER_MIN_UPLOAD_INTERVAL"), 1.0
)
SCRIPT_UPLOADER_TIMEOUT = _to_float(os.getenv("SCRIPT_UPLOADER_TIMEOUT"), 30.0)

MYSQL_URL = os.getenv("MYSQL_URL", "").strip()
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = _to_int(os.getenv("MYSQL_PORT"), 3306)
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "fire_detection")
MYSQL_CHARSET = os.getenv("MYSQL_CHARSET", "utf8mb4")
