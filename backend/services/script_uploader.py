from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import config


class ScriptUploaderProcessManager:
    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None

    @staticmethod
    def _build_command() -> list[str]:
        project_root = Path(__file__).resolve().parents[2]
        script_path = project_root / "python" / "main.py"
        if not script_path.is_file():
            raise FileNotFoundError(f"Auto uploader script not found: {script_path}")

        cmd = [
            sys.executable,
            str(script_path),
            "--watch-dir",
            config.SCRIPT_UPLOADER_WATCH_DIR,
            "--endpoint",
            config.SCRIPT_UPLOADER_ENDPOINT,
            "--poll-interval",
            str(config.SCRIPT_UPLOADER_POLL_INTERVAL),
            "--min-upload-interval",
            str(config.SCRIPT_UPLOADER_MIN_UPLOAD_INTERVAL),
            "--timeout",
            str(config.SCRIPT_UPLOADER_TIMEOUT),
        ]
        return cmd

    def start(self) -> None:
        if not config.SCRIPT_UPLOADER_ENABLED:
            print("Script uploader is disabled by config.")
            return
        if self._proc is not None and self._proc.poll() is None:
            return

        cmd = self._build_command()
        self._proc = subprocess.Popen(cmd)
        print(f"Script uploader started (pid={self._proc.pid}).")

    def stop(self) -> None:
        if self._proc is None:
            return
        if self._proc.poll() is not None:
            self._proc = None
            return

        self._proc.terminate()
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait(timeout=5)
        finally:
            print("Script uploader stopped.")
            self._proc = None

    def status(self) -> dict[str, int | bool | None]:
        if self._proc is None:
            return {"running": False, "pid": None}
        if self._proc.poll() is None:
            return {"running": True, "pid": self._proc.pid}
        return {"running": False, "pid": None}
