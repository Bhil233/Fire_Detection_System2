from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DetectResponse(BaseModel):
    fire_detected: bool
    fire_confidence: float | None = None
    result_text: str
    raw_model_output: str | None = None
    monitor_record: "MonitorRecordRead | None" = None


class MonitorRecordBase(BaseModel):
    status: str = Field(..., min_length=1, max_length=32)
    fire_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    yolo_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    temperature: float | None = None
    smoke_density: float | None = None
    remark: str = Field(default="", max_length=255)


class MonitorRecordRead(MonitorRecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scene_image_path: str
    scene_image_url: str
    created_at: datetime
    updated_at: datetime
