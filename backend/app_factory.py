from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import shutil

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import DATA_IMAGE_DIR, SCRIPT_UPLOADER_WATCH_DIR
from routers import data_monitor_router, detect_router
from services.script_uploader import ScriptUploaderProcessManager


def _clear_directory_files(directory: Path) -> None:
    # 清空目录内所有文件和子目录
    # 用于应用启动和关闭时清理临时检测帧
    if not directory.exists():
        return

    for item in directory.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            try:
                item.unlink()
            except FileNotFoundError:
                pass


def create_app() -> FastAPI:
    # 创建脚本自动上传进程管理器
    uploader_manager = ScriptUploaderProcessManager()
    # 脚本监听目录 主要用于保存和监听检测帧
    detected_frames_dir = (Path(__file__).resolve().parent / SCRIPT_UPLOADER_WATCH_DIR).resolve()
    # 数据图片目录 用于持久化监控记录图片
    data_image_dir = (Path(__file__).resolve().parent / DATA_IMAGE_DIR).resolve()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 应用启动前先清理检测帧目录 避免旧文件重复处理
        _clear_directory_files(detected_frames_dir)
        # 启动自动上传脚本进程
        uploader_manager.start()
        try:
            yield
        finally:
            # 应用关闭时停止脚本进程 并再次清理检测帧目录
            uploader_manager.stop()
            _clear_directory_files(detected_frames_dir)

    # 创建 FastAPI 应用并挂载生命周期钩子
    app = FastAPI(title="AI Fire Detection API", lifespan=lifespan)
    # 将进程管理器挂到 app.state 供路由读取健康状态
    app.state.script_uploader_manager = uploader_manager
    # 确保静态目录存在 不存在则创建
    detected_frames_dir.mkdir(parents=True, exist_ok=True)
    data_image_dir.mkdir(parents=True, exist_ok=True)
    # 配置 CORS 当前允许全部来源 便于前后端联调
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # 挂载检测帧静态目录
    app.mount(
        "/static/detected-frames",
        StaticFiles(directory=str(detected_frames_dir)),
        name="detected_frames",
    )
    # 挂载监控图片静态目录
    app.mount(
        "/static/data-image",
        StaticFiles(directory=str(data_image_dir)),
        name="data_image",
    )
    # 注册火灾检测路由 手动检测 脚本检测 WebSocket
    app.include_router(detect_router)
    # 注册数据监控路由 记录列表和 CRUD
    app.include_router(data_monitor_router)
    # 返回装配完成的应用实例
    return app
