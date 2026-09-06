from __future__ import annotations

import json
import logging
import re
import time

import httpx
from pydantic import ValidationError

from config import settings
from errors import AppError
from schemas import ExtractData, ExtractModelOutput

logger = logging.getLogger(__name__)

COFFEE_ALIASES = {"咖啡", "喝咖啡", "咖啡厅", "cafe", "café"}


def load_extract_prompt() -> str:
    path = settings.backend_dir / "prompts" / "extract.txt"
    return path.read_text(encoding="utf-8")


def normalize_city(value: str) -> str:
    stripped = value.strip()
    if stripped.endswith("市"):
        stripped = stripped[:-1]
    return stripped.casefold()


def normalize_category(value: str | None) -> str:
    if value is None:
        return "咖啡店"
    stripped = value.strip()
    if not stripped:
        return "咖啡店"
    if stripped.casefold() in COFFEE_ALIASES:
        return "咖啡店"
    return stripped


def _content_from_response(payload: object) -> str | None:
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


def _parse_model_json(content: str) -> dict:
    text = content.strip()
    if not text:
        raise AppError(
            502,
            "MODEL_OUTPUT_INVALID",
            "地点信息整理失败，请稍后重试。",
            "extract",
        )
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        logger.error("extract model returned invalid json; stage=extract")
        raise AppError(
            502,
            "MODEL_OUTPUT_INVALID",
            "地点信息整理失败，请稍后重试。",
            "extract",
        ) from None
    if not isinstance(payload, dict):
        raise AppError(
            502,
            "MODEL_OUTPUT_INVALID",
            "地点信息整理失败，请稍后重试。",
            "extract",
        )
    return payload


async def _call_deepseek(user_text: str, page_city: str) -> str:
    if not settings.deepseek_api_key:
        logger.error("extract missing api key; stage=extract")
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "地点提取服务未配置。",
            "extract",
        )

    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": load_extract_prompt()},
            {
                "role": "user",
                "content": f"页面城市：{page_city}\n用户原话：{user_text}",
            },
        ],
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
        "max_tokens": settings.extract_max_tokens,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=settings.extract_timeout_seconds) as client:
            response = await client.post(
                settings.deepseek_api_url,
                headers=headers,
                json=payload,
            )
    except httpx.TimeoutException:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.error("extract timeout; stage=extract; elapsed_ms=%s", elapsed_ms)
        raise AppError(
            504,
            "UPSTREAM_TIMEOUT",
            "地点信息整理超时，请稍后重试。",
            "extract",
        ) from None
    except httpx.HTTPError:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.error("extract network error; stage=extract; elapsed_ms=%s", elapsed_ms)
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "地点提取暂时不可用，请稍后重试。",
            "extract",
        ) from None

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "extract upstream returned; stage=extract; http_status=%s; elapsed_ms=%s",
        response.status_code,
        elapsed_ms,
    )
    if response.status_code >= 400:
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "地点提取暂时不可用，请稍后重试。",
            "extract",
        )

    try:
        body = response.json()
    except ValueError:
        logger.error("extract upstream returned non-json; stage=extract")
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "地点提取暂时不可用，请稍后重试。",
            "extract",
        ) from None

    content = _content_from_response(body)
    if content is None:
        logger.error("extract upstream payload invalid; stage=extract")
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "地点提取暂时不可用，请稍后重试。",
            "extract",
        )
    return content


def complete_extract(model_output: ExtractModelOutput, page_city: str) -> ExtractData:
    logger.info(
        "extract model parsed; stage=extract; party_count=%s; incomplete_reason=%s",
        model_output.party_count,
        model_output.incomplete_reason,
    )
    if model_output.party_count != 2:
        raise AppError(
            422,
            "PARTY_COUNT_INVALID",
            "第一版只支持两个人碰面，请只说两个人各自所在的地点。",
            "extract",
        )
    if model_output.address_a is None or model_output.address_b is None:
        raise AppError(
            422,
            "EXTRACT_INCOMPLETE",
            "没听清两个人各自的具体地点，请说出两个可查询的地名，例如车站或地铁站。",
            "extract",
        )

    city_a = model_output.city_a or page_city.strip() or None
    city_b = model_output.city_b or page_city.strip() or None
    if city_a is None or city_b is None:
        raise AppError(
            422,
            "EXTRACT_INCOMPLETE",
            "没听清两个人各自的具体地点，请说出两个可查询的地名，例如车站或地铁站。",
            "extract",
        )
    if normalize_city(city_a) != normalize_city(city_b):
        raise AppError(
            422,
            "CROSS_CITY",
            "两个人不在同一座城市。第一版请在同一座城市内重新说明地点。",
            "extract",
        )

    return ExtractData(
        city_a=city_a.strip(),
        address_a=model_output.address_a.strip(),
        city_b=city_b.strip(),
        address_b=model_output.address_b.strip(),
        category=normalize_category(model_output.category),
    )


def parse_extract_output(content: str) -> ExtractModelOutput:
    payload = _parse_model_json(content)
    try:
        return ExtractModelOutput.model_validate(payload)
    except ValidationError:
        logger.error("extract model fields invalid; stage=extract")
        raise AppError(
            502,
            "MODEL_OUTPUT_INVALID",
            "地点信息整理失败，请稍后重试。",
            "extract",
        ) from None


async def extract_meetup(user_text: str, page_city: str) -> ExtractData:
    content = await _call_deepseek(user_text, page_city)
    model_output = parse_extract_output(content)
    return complete_extract(model_output, page_city)
