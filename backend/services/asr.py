from __future__ import annotations

import base64
import logging
import time
from pathlib import Path

import httpx

from config import settings
from errors import AppError

logger = logging.getLogger(__name__)


def _extract_text(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if content is None:
        return ""
    if not isinstance(content, str):
        return None
    return content


async def transcribe(audio_path: Path) -> str:
    if not settings.bailian_api_key:
        logger.error("asr missing api key; stage=asr")
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "语音识别服务未配置。",
            "asr",
        )

    audio_bytes = audio_path.read_bytes()
    encoded = base64.b64encode(audio_bytes).decode("ascii")
    if len(encoded) >= settings.max_asr_base64_bytes:
        logger.info(
            "asr encoded audio too large; stage=asr; encoded_bytes=%s",
            len(encoded),
        )
        raise AppError(
            413,
            "FILE_TOO_LARGE",
            "录音编码后超过识别限制，请缩短录音后重试。",
            "asr",
        )

    payload = {
        "model": settings.bailian_asr_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": f"data:audio/webm;base64,{encoded}",
                        },
                    }
                ],
            }
        ],
        "stream": False,
        "asr_options": {
            "enable_itn": True,
        },
    }
    headers = {
        "Authorization": f"Bearer {settings.bailian_api_key}",
        "Content-Type": "application/json",
    }

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=settings.asr_timeout_seconds) as client:
            response = await client.post(
                settings.bailian_asr_url,
                headers=headers,
                json=payload,
            )
    except httpx.TimeoutException:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.error("asr timeout; stage=asr; elapsed_ms=%s", elapsed_ms)
        raise AppError(
            504,
            "UPSTREAM_TIMEOUT",
            "语音识别超时，请稍后重试。",
            "asr",
        ) from None
    except httpx.HTTPError:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.error("asr network error; stage=asr; elapsed_ms=%s", elapsed_ms)
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "语音识别暂时不可用，请稍后重试。",
            "asr",
        ) from None

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "asr upstream returned; stage=asr; http_status=%s; elapsed_ms=%s",
        response.status_code,
        elapsed_ms,
    )
    if response.status_code >= 400:
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "语音识别暂时不可用，请稍后重试。",
            "asr",
        )

    try:
        body = response.json()
    except ValueError:
        logger.error("asr upstream returned non-json; stage=asr")
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "语音识别暂时不可用，请稍后重试。",
            "asr",
        ) from None

    text = _extract_text(body)
    if text is None:
        logger.error("asr upstream payload invalid; stage=asr")
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "语音识别暂时不可用，请稍后重试。",
            "asr",
        )
    stripped = text.strip()
    if not stripped:
        raise AppError(
            422,
            "ASR_EMPTY_TEXT",
            "没有听清你的话，请靠近麦克风后重新说一次。",
            "asr",
        )

    logger.info("asr succeeded; stage=asr; text_len=%s; elapsed_ms=%s", len(stripped), elapsed_ms)
    return stripped
