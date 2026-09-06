from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from config import settings


@pytest.fixture
def audio_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "audio_dir", tmp_path)
    monkeypatch.setattr(settings, "tmp_dir", tmp_path / "tmp")
    monkeypatch.setattr(settings, "bailian_api_key", "sk-test-not-real")
    return tmp_path


@pytest.fixture
def client(audio_dir: Path) -> TestClient:
    from main import app

    return TestClient(app)


def write_upload(
    audio_dir: Path,
    *,
    audio_id: str = "aud_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    created_at: datetime | None = None,
    payload: bytes = b"fake-webm-bytes",
) -> str:
    created = created_at or datetime.now(timezone.utc)
    (audio_dir / f"{audio_id}.webm").write_bytes(payload)
    (audio_dir / f"{audio_id}.json").write_text(
        json.dumps(
            {
                "audio_id": audio_id,
                "kind": "upload",
                "created_at": created.isoformat(),
                "stored_name": f"{audio_id}.webm",
            }
        ),
        encoding="utf-8",
    )
    return audio_id
