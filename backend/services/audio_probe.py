from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from config import settings
from errors import AppError

logger = logging.getLogger(__name__)

PROBE_TIMEOUT_SECONDS = 8
PACKET_PROBE_TIMEOUT_SECONDS = 8


def _is_usable_duration(value: object) -> bool:
    if value is None or value == "" or value == "N/A":
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return number > 0 and number != float("inf")


def _run_ffprobe(args: list[str], timeout: int) -> dict:
    if shutil.which("ffprobe") is None:
        logger.error("ffprobe is not installed; stage=upload")
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "服务器无法校验音频格式，请稍后重试。",
            "upload",
        )

    command = ["ffprobe", "-v", "error", *args]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.error("ffprobe timed out; stage=upload")
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "音频校验超时，请稍后重试。",
            "upload",
        ) from None

    if completed.returncode != 0:
        logger.info(
            "ffprobe rejected file; stage=upload; reason=%s",
            (completed.stderr or "").strip()[:200],
        )
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "仅支持浏览器录制的 WebM/Opus 音频，请更换浏览器后重试。",
            "upload",
        )

    try:
        return json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        logger.error("ffprobe returned invalid json; stage=upload")
        raise AppError(
            502,
            "UPSTREAM_ERROR",
            "音频校验失败，请稍后重试。",
            "upload",
        ) from None


def _duration_from_packets(path: Path) -> float | None:
    payload = _run_ffprobe(
        [
            "-select_streams",
            "a:0",
            "-show_entries",
            "packet=pts_time,duration_time",
            "-of",
            "json",
            str(path),
        ],
        PACKET_PROBE_TIMEOUT_SECONDS,
    )
    packets = payload.get("packets") or []
    last_end: float | None = None
    for packet in packets:
        pts = packet.get("pts_time")
        if not _is_usable_duration(pts):
            continue
        end = float(pts)
        duration_time = packet.get("duration_time")
        if _is_usable_duration(duration_time):
            end += float(duration_time)
        last_end = end
    return last_end


def probe_audio(path: Path) -> dict:
    payload = _run_ffprobe(
        [
            "-show_entries",
            "format=format_name,duration",
            "-show_entries",
            "stream=codec_name,codec_type,duration",
            "-of",
            "json",
            str(path),
        ],
        PROBE_TIMEOUT_SECONDS,
    )

    format_info = payload.get("format") or {}
    format_name = str(format_info.get("format_name") or "").lower()
    tokens = {token.strip() for token in format_name.split(",") if token.strip()}
    if "webm" not in tokens and "matroska" not in tokens:
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "仅支持浏览器录制的 WebM/Opus 音频，请更换浏览器后重试。",
            "upload",
        )

    audio_streams = [
        stream
        for stream in payload.get("streams") or []
        if stream.get("codec_type") == "audio"
    ]
    if not audio_streams:
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "仅支持浏览器录制的 WebM/Opus 音频，请更换浏览器后重试。",
            "upload",
        )

    codec = str(audio_streams[0].get("codec_name") or "").lower()
    if codec != "opus":
        raise AppError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "仅支持浏览器录制的 WebM/Opus 音频，请更换浏览器后重试。",
            "upload",
        )

    duration = None
    if _is_usable_duration(format_info.get("duration")):
        duration = float(format_info["duration"])
    elif _is_usable_duration(audio_streams[0].get("duration")):
        duration = float(audio_streams[0]["duration"])
    else:
        duration = _duration_from_packets(path)

    if duration is None:
        raise AppError(
            422,
            "AUDIO_DURATION_INVALID",
            "无法确认录音时长，请重新录制。",
            "upload",
        )

    if duration < settings.min_audio_seconds or duration > settings.max_audio_seconds:
        raise AppError(
            422,
            "AUDIO_DURATION_INVALID",
            "录音需在 1 到 60 秒之间，请重新录制。",
            "upload",
        )

    return {
        "container": format_name,
        "codec": codec,
        "duration_seconds": duration,
    }
