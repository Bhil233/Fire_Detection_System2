import argparse
import json
import mimetypes
import time
from pathlib import Path
from typing import Iterable

import httpx

# 后端脚本检测接口默认地址
DEFAULT_ENDPOINT = "http://127.0.0.1:8000/api/script/detect-fire"


def parse_args() -> argparse.Namespace:
    # 解析命令行参数
    # images 支持一个或多个图片路径
    # endpoint timeout min-interval 用于控制上传行为
    parser = argparse.ArgumentParser(
        description="Upload images to script module sequentially and print results."
    )
    parser.add_argument("images", nargs="+", help="One or more image file paths")
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help="Detection API endpoint",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout seconds")
    parser.add_argument(
        "--min-interval",
        type=float,
        default=1.0,
        help="Minimum interval between two uploads in seconds",
    )
    parser.add_argument("--yolo-confidence", type=float, default=None, help="YOLO confidence from 0.0 to 1.0")
    parser.add_argument("--temperature", type=float, default=None, help="Temperature sensor value")
    parser.add_argument("--smoke-density", type=float, default=None, help="Smoke density sensor value")
    return parser.parse_args()


def _to_path(image_path: str | Path) -> Path:
    # 统一转换为 Path 并展开用户目录
    return Path(image_path).expanduser()


def _build_optional_data(
    *,
    yolo_confidence: float | None = None,
    temperature: float | None = None,
    smoke_density: float | None = None,
) -> dict[str, str]:
    data: dict[str, str] = {}
    if yolo_confidence is not None:
        confidence = max(0.0, min(1.0, float(yolo_confidence)))
        data["yolo_confidence"] = str(confidence)
    if temperature is not None:
        data["temperature"] = str(temperature)
    if smoke_density is not None:
        data["smoke_density"] = str(smoke_density)
    return data


def _upload_one(
    client: httpx.Client,
    endpoint: str,
    image_path: Path,
    *,
    yolo_confidence: float | None = None,
    temperature: float | None = None,
    smoke_density: float | None = None,
) -> dict:
    # 上传单张图片并返回 JSON 结果
    if not image_path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")

    # 依据文件扩展名推断 MIME 类型
    mime_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"

    with image_path.open("rb") as file_obj:
        files = {"file": (image_path.name, file_obj, mime_type)}
        data = _build_optional_data(
            yolo_confidence=yolo_confidence,
            temperature=temperature,
            smoke_density=smoke_density,
        )
        response = client.post(endpoint, files=files, data=data or None)

    response.raise_for_status()
    return response.json()


class FireUploadClient:
    # 上传客户端
    # 封装单图上传 批量上传 和最小间隔限流
    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 30.0,
        min_interval: float = 1.0,
        yolo_confidence: float | None = None,
        temperature: float | None = None,
        smoke_density: float | None = None,
    ):
        self.endpoint = endpoint
        self.timeout = timeout
        self.min_interval = max(0.0, min_interval)
        self.yolo_confidence = yolo_confidence
        self.temperature = temperature
        self.smoke_density = smoke_density
        self._last_upload_started_at: float | None = None

    def _wait_for_rate_limit(self) -> None:
        # 控制两次上传开始时间之间至少间隔 min_interval 秒
        if self._last_upload_started_at is None:
            return
        elapsed = time.monotonic() - self._last_upload_started_at
        wait_seconds = self.min_interval - elapsed
        if wait_seconds > 0:
            time.sleep(wait_seconds)
    
    def upload_image(
        self,
        image_path: str | Path,
        *,
        yolo_confidence: float | None = None,
        temperature: float | None = None,
        smoke_density: float | None = None,
    ) -> dict:
        # 上传单张图片
        image_file = _to_path(image_path)
        with httpx.Client(timeout=self.timeout) as client:
            self._wait_for_rate_limit()
            self._last_upload_started_at = time.monotonic()
            return _upload_one(
                client=client,
                endpoint=self.endpoint,
                image_path=image_file,
                yolo_confidence=(
                    self.yolo_confidence if yolo_confidence is None else yolo_confidence
                ),
                temperature=self.temperature if temperature is None else temperature,
                smoke_density=self.smoke_density if smoke_density is None else smoke_density,
            )
    
    def upload_images(self, image_paths: Iterable[str | Path]) -> list[dict]:
        # 顺序批量上传图片
        results: list[dict] = []
        with httpx.Client(timeout=self.timeout) as client:
            for image_path in image_paths:
                image_file = _to_path(image_path)
                self._wait_for_rate_limit()
                self._last_upload_started_at = time.monotonic()
                result = _upload_one(
                    client=client,
                    endpoint=self.endpoint,
                    image_path=image_file,
                    yolo_confidence=self.yolo_confidence,
                    temperature=self.temperature,
                    smoke_density=self.smoke_density,
                )
                results.append(result)
        return results


def upload_image(
    image_path: str | Path,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout: float = 30.0,
    min_interval: float = 1.0,
    yolo_confidence: float | None = None,
    temperature: float | None = None,
    smoke_density: float | None = None,
) -> dict:
    # 函数式入口 上传单张图片
    client = FireUploadClient(
        endpoint=endpoint,
        timeout=timeout,
        min_interval=min_interval,
        yolo_confidence=yolo_confidence,
        temperature=temperature,
        smoke_density=smoke_density,
    )
    return client.upload_image(image_path)


def upload_images(
    image_paths: Iterable[str | Path],
    endpoint: str = DEFAULT_ENDPOINT,
    timeout: float = 30.0,
    min_interval: float = 1.0,
) -> list[dict]:
    # 函数式入口 批量上传图片
    client = FireUploadClient(endpoint=endpoint, timeout=timeout, min_interval=min_interval)
    return client.upload_images(image_paths)


def main() -> None:
    # 命令行执行入口
    args = parse_args()
    image_paths = [_to_path(item) for item in args.images]
    client = FireUploadClient(
        endpoint=args.endpoint,
        timeout=args.timeout,
        min_interval=args.min_interval,
        yolo_confidence=args.yolo_confidence,
        temperature=args.temperature,
        smoke_density=args.smoke_density,
    )
    results = client.upload_images(image_paths)

    for index, (image_path, payload) in enumerate(zip(image_paths, results), start=1):
        print(f"[{index}/{len(image_paths)}] {image_path}")
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # 仅在直接运行脚本时执行
    main()
