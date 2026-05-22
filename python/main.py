import argparse
import re
import time
from pathlib import Path
from threading import Lock

from upload_image import FireUploadClient
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="Watch detected image folder and upload the latest saved image."
    )
    parser.add_argument(
        "--watch-dir",
        default="detected_frames",
        help="Directory where yolo.py saves detected frames",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        help="Settle delay before uploading after a file event (seconds)",
    )
    parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1:8000/api/script/detect-fire",
        help="Detection API endpoint",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout seconds")
    parser.add_argument(
        "--min-upload-interval",
        type=float,
        default=1.0,
        help="Minimum interval between two uploads in seconds",
    )
    parser.add_argument("--temperature", type=float, default=None, help="Temperature sensor value")
    parser.add_argument("--smoke-density", type=float, default=None, help="Smoke density sensor value")
    return parser.parse_args()


def get_latest_image_path(watch_dir: Path) -> Path | None:
    # 获取目录中最近修改的一张图片
    if not watch_dir.exists():
        return None

    image_files = [
        path for path in watch_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTS
    ]
    if not image_files:
        return None

    return max(image_files, key=lambda p: p.stat().st_mtime)


def extract_yolo_confidence(file_path: Path) -> float | None:
    match = re.search(r"(?:^|_)conf_(\d+(?:\.\d+)?)(?:_|$)", file_path.stem)
    if match is None:
        return None
    return max(0.0, min(1.0, float(match.group(1))))


class UploadOnImageEventHandler(FileSystemEventHandler):
    # 监听目录中文件变化并执行上传
    def __init__(
        self,
        watch_dir: Path,
        client: FireUploadClient,
        settle_delay: float,
    ) -> None:
        self.watch_dir = watch_dir
        self.client = client
        self.settle_delay = max(0.0, settle_delay)
        self._uploaded_mtime_by_path: dict[Path, float] = {}
        self._lock = Lock()

    def _is_supported_image(self, file_path: Path) -> bool:
        # 仅处理约定图片后缀
        return file_path.suffix.lower() in IMAGE_EXTS

    def _normalize_path(self, src_path: str) -> Path:
        # 统一成绝对路径 便于后续比较
        return Path(src_path).resolve()

    def _try_upload(self, file_path: Path) -> None:
        # 非监听目录或不支持后缀时直接忽略
        if file_path.parent != self.watch_dir:
            return
        if not self._is_supported_image(file_path):
            return

        # 等待文件写入稳定 避免上传半写入文件
        if self.settle_delay > 0:
            time.sleep(self.settle_delay)

        if not file_path.exists() or not file_path.is_file():
            return

        # 使用 mtime 去重 避免同一文件重复上传
        file_mtime = file_path.stat().st_mtime
        with self._lock:
            last_mtime = self._uploaded_mtime_by_path.get(file_path, -1.0)
            if file_mtime <= last_mtime:
                return

        # 调用上传客户端发送到后端
        payload = self.client.upload_image(
            file_path,
            yolo_confidence=extract_yolo_confidence(file_path),
        )
        print(f"Uploaded: {file_path}")
        print(payload)

        with self._lock:
            self._uploaded_mtime_by_path[file_path] = file_mtime

    def on_created(self, event: FileSystemEvent) -> None:
        # 处理新建文件事件
        if event.is_directory:
            return
        try:
            self._try_upload(self._normalize_path(event.src_path))
        except Exception as exc:
            print(f"Upload failed: {exc}")

    def on_modified(self, event: FileSystemEvent) -> None:
        # 处理文件修改事件
        if event.is_directory:
            return
        try:
            self._try_upload(self._normalize_path(event.src_path))
        except Exception as exc:
            print(f"Upload failed: {exc}")


def main() -> None:
    # 初始化参数 目录 上传客户端
    args = parse_args()
    watch_dir = Path(args.watch_dir).expanduser()
    watch_dir.mkdir(parents=True, exist_ok=True)

    client = FireUploadClient(
        endpoint=args.endpoint,
        timeout=args.timeout,
        min_interval=args.min_upload_interval,
        temperature=args.temperature,
        smoke_density=args.smoke_density,
    )

    print(f"Watching: {watch_dir.resolve()}")
    print(f"Endpoint: {args.endpoint}")
    print("Mode: filesystem events (watchdog)")

    # 创建并启动 watchdog 观察者
    handler = UploadOnImageEventHandler(
        watch_dir=watch_dir.resolve(),
        client=client,
        settle_delay=args.poll_interval,
    )
    observer = Observer()
    observer.schedule(handler, path=str(watch_dir.resolve()), recursive=False)
    observer.start()

    # 启动后可选补传一次目录中最新图片
    try:
        latest_image = get_latest_image_path(watch_dir)
        if latest_image is not None:
            handler._try_upload(latest_image.resolve())
    except Exception as exc:
        print(f"Initial upload failed: {exc}")

    try:
        # 主循环 保持进程存活并持续监听
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        # 退出时释放观察者资源
        observer.stop()
        observer.join()


if __name__ == "__main__":
    # 脚本入口
    main()
