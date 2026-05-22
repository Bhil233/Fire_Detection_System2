from __future__ import annotations

import base64
from typing import Any

import httpx
from fastapi import HTTPException

import config


def _build_prompt(
    *,
    yolo_confidence: float | None = None,
    temperature: float | None = None,
    smoke_density: float | None = None,
) -> str:
    # Build auxiliary sensor context string (inserted into the reasoning step).
    context_parts: list[str] = []
    if yolo_confidence is not None:
        context_parts.append(f"YOLO检测置信度={max(0.0, min(1.0, float(yolo_confidence))):.2f}")
    if temperature is not None:
        context_parts.append(f"环境温度={temperature}°C")
    if smoke_density is not None:
        context_parts.append(f"烟雾浓度={smoke_density}")
    sensor_context = "；".join(context_parts) if context_parts else "无辅助传感器数据"

    prompt = (
        "你是一个火灾检测助手。请严格按以下步骤进行推理分析，再给出最终结果。\n\n"

        "【推理步骤】\n"
        "第1步 — 观察火焰特征：图像中是否存在明火？火焰的颜色（橙红/蓝/黄）、大小、形状、是否在扩散？\n"
        "第2步 — 观察烟雾特征：是否存在烟雾？烟雾的颜色（黑/灰/白）、浓度、扩散范围？是否可能是水蒸气、雾气或灰尘？\n"
        "第3步 — 观察其他异常：是否有异常亮光、反光、烧焦痕迹、或与火灾相关的间接证据？\n"
        "第4步 — 综合辅助数据：结合传感器数据（如有）进行交叉验证。\n"
        f"  当前传感器数据：{sensor_context}\n"
        "第5步 — 综合判断：基于以上所有证据，给出0.0到1.0的置信度。\n\n"

        "【少样本参考示例】\n\n"

        "示例1 — 明显火灾：\n"
        "  图像：户外山林中大面积橙红色明火，火焰高度超过2米，浓密黑烟升腾，周围植被干燥。\n"
        "  推理：第1步-大面积明火，橙红色，正在扩散；第2步-浓密黑烟，范围大，持续上升，非水蒸气；"
        "第3步-火光明显，周围植被为可燃物；第4步-传感器温度68°C、烟雾浓度0.9，与视觉一致；"
        "第5步-多重强证据指向火灾，危险程度高。\n"
        "  {\"confidence\": 0.95}\n\n"

        "示例2 — 安全可控火源：\n"
        "  图像：室内厨房，燃气灶上有蓝色小火苗，火焰稳定，锅内有食物，抽油烟机开启。\n"
        "  推理：第1步-存在火焰但蓝色、小火、稳定、有人为控制迹象；第2步-无异常烟雾，仅有烹饪蒸汽；"
        "第3步-无异常光亮或烧焦痕迹；第4步-传感器温度32°C（正常）、烟雾浓度0.1（低）；"
        "第5步-火焰为安全可控场景，非火灾。\n"
        "  {\"confidence\": 0.35}\n\n"

        "示例3 — 疑似弱信号：\n"
        "  图像：仓库角落有稀薄灰白色雾状区域，边缘模糊，远处有日光灯，无可见火焰。\n"
        "  推理：第1步-未发现明火；第2步-存在模糊灰白雾状物，可能是烟雾也可能是灰尘或水雾，"
        "特征不够明确；第3步-日光灯为正常光源，无可疑反光；第4步-传感器温度28°C（正常）、"
        "烟雾浓度0.25（略高）；第5步-视觉弱信号+传感器略有异常，不能排除早期火灾，给偏低置信度。\n"
        "  {\"confidence\": 0.30}\n\n"

        "示例4 — 完全正常：\n"
        "  图像：普通办公室，桌椅电脑，日光灯照明，窗户透入自然光，所有物体轮廓清晰。\n"
        "  推理：第1步-无任何火焰；第2步-无任何烟雾或雾状物；第3步-所有光源正常，无异常；"
        "第4步-传感器温度24°C、烟雾浓度0.02，均正常；第5步-无任何火灾相关证据。\n"
        "  {\"confidence\": 0.0}\n\n"

        "示例5 — 中等疑似（夜间反光干扰）：\n"
        "  图像：夜间室外停车场，远处车灯照射在湿地面产生橙黄色反光，周围有薄雾。\n"
        "  推理：第1步-橙黄色反光可能被误判为火焰，但形状固定、无跳动、来自车灯反射；"
        "第2步-薄雾均匀分布，更符合夜间湿气特征而非烟雾；第3步-反光来源可解释（车灯+湿地）；"
        "第4步-传感器温度18°C、烟雾浓度0.08，均正常；第5步-视觉疑似特征有合理解释，火灾可能性低。\n"
        "  {\"confidence\": 0.15}\n\n"

        "【输出要求】\n"
        "仅输出一个JSON对象，包含推理过程和置信度分数，格式如下：\n"
        "{\"reasoning\": \"第1步-...；第2步-...；第3步-...；第4步-...；第5步-...\", \"confidence\": <number>}\n"
        "不要返回任何额外文本、注释或代码块标记。"
    )

    return prompt


async def call_qwen(
    image_bytes: bytes,
    mime_type: str,
    *,
    yolo_confidence: float | None = None,
    temperature: float | None = None,
    smoke_density: float | None = None,
) -> str:
    if not config.QWEN_API_KEY:
        raise HTTPException(status_code=500, detail="Missing QWEN_API_KEY environment variable.")

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{image_b64}"
    payload: dict[str, Any] = {
        "model": config.QWEN_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a strict fire-image detection assistant.",
            },
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {
                        "type": "text",
                        "text": _build_prompt(
                            yolo_confidence=yolo_confidence,
                            temperature=temperature,
                            smoke_density=smoke_density,
                        ),
                    },
                ],
            },
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            config.QWEN_API_URL,
            headers={
                "Authorization": f"Bearer {config.QWEN_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Qwen API error: {resp.text}")
        data = resp.json()

    choices = data.get("choices", [])
    if not choices:
        raise HTTPException(status_code=502, detail="Qwen returned no choices.")

    text = choices[0].get("message", {}).get("content", "")
    if isinstance(text, list):
        text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
    text = str(text).strip()
    if not text:
        raise HTTPException(status_code=502, detail="Qwen returned empty text.")
    return text
