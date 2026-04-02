from __future__ import annotations

import asyncio
import base64
import json
from threading import Lock

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.schemas import DetectResponse
from services.monitor_records import create_monitor_record
from services.qwen_client import call_qwen
from utils import parse_fire_result


router = APIRouter()


class _LatestScriptUploadStore:
    # 线程安全缓存“脚本上传最新图片 + 识别结果”
    def __init__(self) -> None:
        self._lock = Lock()
        self._image_bytes: bytes | None = None
        self._mime_type: str | None = None
        self._result: DetectResponse | None = None

    def save(self, image_bytes: bytes, mime_type: str, result: DetectResponse) -> None:
        with self._lock:
            self._image_bytes = image_bytes
            self._mime_type = mime_type
            self._result = result

    def load(self) -> tuple[bytes | None, str | None, DetectResponse | None]:
        with self._lock:
            return self._image_bytes, self._mime_type, self._result


class _ScriptUploadSocketHub:
    # 管理 WebSocket 客户端并广播脚本检测结果
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._clients: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    @staticmethod
    def _build_payload(image_bytes: bytes, mime_type: str, result: DetectResponse) -> str:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "type": "script_upload_result",
            "image_data_url": f"data:{mime_type};base64,{encoded}",
            "fire_detected": result.fire_detected,
            "result_text": result.result_text,
            "monitor_record": result.monitor_record.model_dump(mode="json")
            if result.monitor_record is not None
            else None,
        }
        return json.dumps(payload, ensure_ascii=False)

    async def send_snapshot(
        self, websocket: WebSocket, image_bytes: bytes, mime_type: str, result: DetectResponse
    ) -> None:
        await websocket.send_text(self._build_payload(image_bytes, mime_type, result))

    async def broadcast_snapshot(
        self, image_bytes: bytes, mime_type: str, result: DetectResponse
    ) -> None:
        # 先复制客户端列表，减少锁持有时间
        async with self._lock:
            clients = list(self._clients)

        if not clients:
            return

        message = self._build_payload(image_bytes, mime_type, result)
        disconnected: list[WebSocket] = []

        for client in clients:
            try:
                await client.send_text(message)
            except Exception:
                disconnected.append(client)

        if disconnected:
            async with self._lock:
                for client in disconnected:
                    self._clients.discard(client)


latest_script_upload_store = _LatestScriptUploadStore()
script_upload_socket_hub = _ScriptUploadSocketHub()


async def _read_and_validate_image(file: UploadFile) -> tuple[bytes, str]:
    # 上传内容必须是图片且不能为空
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="仅支持图像文件")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="上传文件为空")

    return image_bytes, file.content_type


async def _run_detection(image_bytes: bytes, mime_type: str) -> tuple[bool, str]:
    # 调用大模型并将结果解析为布尔值
    model_text = await call_qwen(image_bytes=image_bytes, mime_type=mime_type)
    fire_detected = parse_fire_result(model_text)
    return fire_detected, model_text


async def _detect_and_create_record(
    *,
    image_bytes: bytes,
    mime_type: str,
    source: str,
    db: AsyncSession,
) -> DetectResponse:
    # 完成识别并创建监控记录
    fire_detected, model_text = await _run_detection(image_bytes=image_bytes, mime_type=mime_type)
    status = "发生火灾" if fire_detected else "无火灾"
    remark = "自动上传" if source == "script_detect_fire" else "手动上传"

    try:
        monitor_record = await create_monitor_record(
            db=db,
            image_bytes=image_bytes,
            mime_type=mime_type,
            status=status,
            remark=remark,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"检测已完成但未能创建监控记录: {exc}",
        ) from exc

    if fire_detected:
        return DetectResponse(
            fire_detected=True,
            result_text="发现火灾，请立即处理",
            raw_model_output=model_text,
            monitor_record=monitor_record,
        )

    return DetectResponse(
        fire_detected=False,
        result_text="未发现火灾",
        raw_model_output=model_text,
        monitor_record=monitor_record,
    )


@router.websocket("/ws/script/latest-upload-image")
async def latest_script_upload_image_ws(websocket: WebSocket) -> None:
    # 脚本检测结果实时推送
    await script_upload_socket_hub.connect(websocket)
    try:
        # 新连接先下发一次当前快照
        image_bytes, mime_type, result = latest_script_upload_store.load()
        if image_bytes is not None and mime_type is not None and result is not None:
            await script_upload_socket_hub.send_snapshot(websocket, image_bytes, mime_type, result)

        # 保持连接存活，等待客户端心跳
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await script_upload_socket_hub.disconnect(websocket)


@router.post("/api/manual/detect-fire", response_model=DetectResponse)
async def manual_detect_fire(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> DetectResponse:
    # 手动检测接口
    image_bytes, mime_type = await _read_and_validate_image(file)
    return await _detect_and_create_record(
        image_bytes=image_bytes,
        mime_type=mime_type,
        source="manual_detect_fire",
        db=db,
    )


@router.post("/api/script/detect-fire", response_model=DetectResponse)
async def script_detect_fire(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> DetectResponse:
    # 脚本上传检测接口
    image_bytes, mime_type = await _read_and_validate_image(file)
    result = await _detect_and_create_record(
        image_bytes=image_bytes,
        mime_type=mime_type,
        source="script_detect_fire",
        db=db,
    )

    # 更新最新快照并广播给所有 WebSocket 客户端
    latest_script_upload_store.save(image_bytes=image_bytes, mime_type=mime_type, result=result)
    await script_upload_socket_hub.broadcast_snapshot(
        image_bytes=image_bytes, mime_type=mime_type, result=result
    )
    return result


@router.get("/api/health/script-uploader")
async def script_uploader_health(request: Request) -> dict:
    # 查询脚本上传子进程状态
    manager = getattr(request.app.state, "script_uploader_manager", None)
    if manager is None:
        return {"running": False, "pid": None, "detail": "script_uploader_manager not initialized"}
    status = manager.status()
    return {"running": status["running"], "pid": status["pid"]}
