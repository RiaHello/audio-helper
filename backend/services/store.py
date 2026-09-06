from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from config import settings
from errors import AppError

AUDIO_ID_PATTERN = re.compile(r"^aud_[0-9a-f]{32}$")


def ensure_storage_dirs() -> None:
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)


def save_upload(
    source: Path,
    *,
    size_bytes: int,
    duration_seconds: float,
    container: str,
    codec: str,
) -> str:
    ensure_storage_dirs()
    audio_id = f"aud_{uuid4().hex}"
    stored_name = f"{audio_id}.webm"
    destination = settings.audio_dir / stored_name
    source.replace(destination)

    created_at = datetime.now(timezone.utc)
    metadata = {
        "audio_id": audio_id,
        "kind": "upload",
        "created_at": created_at.isoformat(),
        "stored_name": stored_name,
        "size_bytes": size_bytes,
        "duration_seconds": duration_seconds,
        "container": container,
        "codec": codec,
    }
    metadata_path = settings.audio_dir / f"{audio_id}.json"
    try:
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return audio_id


def _parse_created_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def get_upload(audio_id: str, *, stage: str) -> Path:
    if not AUDIO_ID_PATTERN.fullmatch(audio_id):
        raise AppError(
            404,
            "AUDIO_NOT_FOUND",
            "录音已过期或不存在，请重新录音。",
            stage,
        )

    metadata_path = settings.audio_dir / f"{audio_id}.json"
    audio_path = settings.audio_dir / f"{audio_id}.webm"
    if not metadata_path.is_file() or not audio_path.is_file():
        raise AppError(
            404,
            "AUDIO_NOT_FOUND",
            "录音已过期或不存在，请重新录音。",
            stage,
        )

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise AppError(
            404,
            "AUDIO_NOT_FOUND",
            "录音已过期或不存在，请重新录音。",
            stage,
        ) from None

    created_at = _parse_created_at(metadata.get("created_at"))
    if created_at is None:
        raise AppError(
            404,
            "AUDIO_NOT_FOUND",
            "录音已过期或不存在，请重新录音。",
            stage,
        )

    expires_at = created_at + timedelta(hours=settings.audio_ttl_hours)
    if datetime.now(timezone.utc) >= expires_at:
        raise AppError(
            404,
            "AUDIO_NOT_FOUND",
            "录音已过期或不存在，请重新录音。",
            stage,
        )

    return audio_path
