from __future__ import annotations

import asyncio
import mimetypes
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from config import DATA_IMAGE_DIR
from database import init_database
from models.data_monitor import MonitorRecord
from models.schemas import MonitorRecordRead


_backend_dir = Path(__file__).resolve().parents[1]
_data_image_dir = (_backend_dir / DATA_IMAGE_DIR).resolve()
_data_image_dir.mkdir(parents=True, exist_ok=True)

_db_init_lock = asyncio.Lock()
_db_initialized = False


def build_image_url(image_path: str) -> str:
    filename = Path(image_path).name
    return f"/static/data-image/{filename}"


def to_read_model(record: MonitorRecord) -> MonitorRecordRead:
    return MonitorRecordRead(
        id=record.id,
        scene_image_path=record.scene_image_path,
        scene_image_url=build_image_url(record.scene_image_path),
        status=record.status,
        remark=record.remark,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


async def ensure_database_initialized() -> None:
    global _db_initialized

    if _db_initialized:
        return

    async with _db_init_lock:
        if _db_initialized:
            return
        await init_database()
        _db_initialized = True


def _suffix_from_mime_type(mime_type: str | None) -> str:
    if not mime_type:
        return ".jpg"

    guessed = mimetypes.guess_extension(mime_type, strict=False) or ".jpg"
    if guessed == ".jpe":
        guessed = ".jpg"
    if not re.fullmatch(r"\.[a-zA-Z0-9]+", guessed):
        return ".jpg"
    return guessed.lower()


def save_image_to_data_image(image_bytes: bytes, mime_type: str | None = None) -> str:
    suffix = _suffix_from_mime_type(mime_type)
    filename = f"monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}{suffix}"
    target = _data_image_dir / filename
    target.write_bytes(image_bytes)
    return str(Path(DATA_IMAGE_DIR) / filename)


def delete_stored_image(scene_image_path: str) -> None:
    target = (_backend_dir / scene_image_path).resolve()
    try:
        target.relative_to(_data_image_dir)
    except ValueError:
        # Never delete files outside backend/data_image.
        return

    if target.exists() and target.is_file():
        target.unlink()


async def create_monitor_record(
    db: AsyncSession,
    *,
    image_bytes: bytes,
    mime_type: str | None,
    status: str,
    remark: str = "",
) -> MonitorRecordRead:
    await ensure_database_initialized()

    normalized_status = status.strip().lower()
    if normalized_status not in {"发生火灾", "无火灾"}:
        normalized_status = "normal"

    scene_image_path = save_image_to_data_image(image_bytes=image_bytes, mime_type=mime_type)
    record = MonitorRecord(
        scene_image_path=scene_image_path,
        status=normalized_status,
        remark=remark.strip(),
    )
    db.add(record)
    try:
        await db.commit()
        await db.refresh(record)
    except Exception:
        await db.rollback()
        delete_stored_image(scene_image_path)
        raise
    return to_read_model(record)
