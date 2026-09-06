from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from config import settings


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
