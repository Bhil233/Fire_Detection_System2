from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.data_monitor import MonitorRecord
from models.schemas import MonitorRecordRead
from services.monitor_records import (
    create_monitor_record,
    delete_stored_image,
    ensure_database_initialized,
    save_image_to_data_image,
    to_read_model,
)
from services.qwen_client import call_qwen
from utils import parse_fire_confidence, parse_fire_result


router = APIRouter()


async def _read_and_validate_jpg(file: UploadFile) -> bytes:
    content_type = (file.content_type or "").lower()
    if content_type not in {"image/jpeg", "image/jpg"}:
        raise HTTPException(status_code=400, detail="Only JPG image is supported")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")

    return image_bytes


async def _auto_detect_status(
    image_bytes: bytes,
    *,
    yolo_confidence: float | None = None,
    temperature: float | None = None,
    smoke_density: float | None = None,
) -> tuple[str, float]:
    model_text = await call_qwen(
        image_bytes=image_bytes,
        mime_type="image/jpeg",
        yolo_confidence=yolo_confidence,
        temperature=temperature,
        smoke_density=smoke_density,
    )
    return ("fire" if parse_fire_result(model_text) else "normal", parse_fire_confidence(model_text))


@router.get("/api/data-monitor/records", response_model=list[MonitorRecordRead])
async def list_monitor_records(
    sort_by: Literal[
        "id",
        "status",
        "fire_confidence",
        "yolo_confidence",
        "temperature",
        "smoke_density",
        "remark",
        "created_at",
        "updated_at",
        "time",
    ] = Query(default="created_at"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    db: AsyncSession = Depends(get_db),
) -> list[MonitorRecordRead]:
    try:
        await ensure_database_initialized()
        sort_column_map = {
            "id": MonitorRecord.id,
            "status": MonitorRecord.status,
            "fire_confidence": MonitorRecord.fire_confidence,
            "yolo_confidence": MonitorRecord.yolo_confidence,
            "temperature": MonitorRecord.temperature,
            "smoke_density": MonitorRecord.smoke_density,
            "remark": MonitorRecord.remark,
            "created_at": MonitorRecord.created_at,
            "updated_at": MonitorRecord.updated_at,
            "time": MonitorRecord.created_at,
        }
        sort_column = sort_column_map[sort_by]
        order_expr = sort_column.asc() if sort_order == "asc" else sort_column.desc()
        result = await db.execute(select(MonitorRecord).order_by(order_expr, MonitorRecord.id.desc()))
        rows = list(result.scalars().all())
        return [to_read_model(row) for row in rows]
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Data monitor database is unavailable. Please check MySQL config. {exc}",
        ) from exc


@router.post("/api/data-monitor/records", response_model=MonitorRecordRead, status_code=201)
async def create_monitor_record_api(
    scene_image: UploadFile = File(...),
    remark: str = Form(""),
    yolo_confidence: float | None = Form(default=None, ge=0.0, le=1.0),
    temperature: float | None = Form(default=None),
    smoke_density: float | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> MonitorRecordRead:
    try:
        image_bytes = await _read_and_validate_jpg(scene_image)
        status, fire_confidence = await _auto_detect_status(
            image_bytes,
            yolo_confidence=yolo_confidence,
            temperature=temperature,
            smoke_density=smoke_density,
        )
        return await create_monitor_record(
            db=db,
            image_bytes=image_bytes,
            mime_type="image/jpeg",
            status=status,
            fire_confidence=fire_confidence,
            yolo_confidence=yolo_confidence,
            temperature=temperature,
            smoke_density=smoke_density,
            remark=remark,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create record. Please check MySQL connection. {exc}",
        ) from exc


@router.put("/api/data-monitor/records/{record_id}", response_model=MonitorRecordRead)
async def update_monitor_record(
    record_id: int,
    remark: str | None = Form(default=None),
    scene_image: UploadFile | None = File(default=None),
    yolo_confidence: float | None = Form(default=None, ge=0.0, le=1.0),
    temperature: float | None = Form(default=None),
    smoke_density: float | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> MonitorRecordRead:
    new_scene_image_path: str | None = None
    old_scene_image_path: str | None = None
    try:
        await ensure_database_initialized()
        record = await db.get(MonitorRecord, record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Record not found")

        if remark is not None:
            record.remark = remark.strip()

        if yolo_confidence is not None:
            record.yolo_confidence = yolo_confidence
        if temperature is not None:
            record.temperature = temperature
        if smoke_density is not None:
            record.smoke_density = smoke_density

        if scene_image is not None:
            image_bytes = await _read_and_validate_jpg(scene_image)
            old_scene_image_path = record.scene_image_path
            new_scene_image_path = save_image_to_data_image(
                image_bytes=image_bytes,
                mime_type="image/jpeg",
            )
            record.scene_image_path = new_scene_image_path
            record.status, record.fire_confidence = await _auto_detect_status(
                image_bytes,
                yolo_confidence=yolo_confidence,
                temperature=temperature,
                smoke_density=smoke_density,
            )
            record.yolo_confidence = yolo_confidence
            record.temperature = temperature
            record.smoke_density = smoke_density

        record.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(record)

        if old_scene_image_path and new_scene_image_path:
            delete_stored_image(old_scene_image_path)

        return to_read_model(record)
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        if new_scene_image_path is not None:
            delete_stored_image(new_scene_image_path)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update record. Please check MySQL connection. {exc}",
        ) from exc


@router.delete("/api/data-monitor/records/{record_id}")
async def delete_monitor_record(record_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        await ensure_database_initialized()
        record = await db.get(MonitorRecord, record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Record not found")

        scene_image_path = record.scene_image_path
        await db.delete(record)
        await db.commit()
        delete_stored_image(scene_image_path)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete record. Please check MySQL connection. {exc}",
        ) from exc
