from datetime import datetime, timedelta, timezone

import httpx
import respx

from config import settings
from tests.conftest import write_upload


def test_asr_missing_audio_id(client):
    response = client.post("/asr", json={})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["stage"] == "asr"
    assert "request_id" in body


def test_asr_unknown_id(client, audio_dir):
    response = client.post("/asr", json={"audio_id": "aud_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"})
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "AUDIO_NOT_FOUND"
    assert body["error"]["stage"] == "asr"
    assert body["error"]["message"] == "录音已过期或不存在，请重新录音。"


def test_asr_expired_id(client, audio_dir):
    audio_id = write_upload(
        audio_dir,
        created_at=datetime.now(timezone.utc) - timedelta(hours=25),
    )
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AUDIO_NOT_FOUND"


def test_asr_rejects_path_like_id(client, audio_dir):
    response = client.post("/asr", json={"audio_id": "../secret"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AUDIO_NOT_FOUND"


@respx.mock
def test_asr_success_uses_upstream_text(client, audio_dir):
    audio_id = write_upload(audio_dir)
    respx.post(settings.bailian_asr_url).mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "我在杭州东站，朋友在龙翔桥。"}}]},
        )
    )
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["text"] == "我在杭州东站，朋友在龙翔桥。"
    assert "request_id" in body


@respx.mock
def test_asr_empty_text(client, audio_dir):
    audio_id = write_upload(audio_dir)
    respx.post(settings.bailian_asr_url).mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "   "}}]},
        )
    )
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "ASR_EMPTY_TEXT"
    assert body["error"]["stage"] == "asr"


@respx.mock
def test_asr_upstream_error(client, audio_dir):
    audio_id = write_upload(audio_dir)
    respx.post(settings.bailian_asr_url).mock(return_value=httpx.Response(500, json={"message": "fail"}))
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "UPSTREAM_ERROR"
    assert response.json()["error"]["stage"] == "asr"


@respx.mock
def test_asr_timeout(client, audio_dir):
    audio_id = write_upload(audio_dir)
    respx.post(settings.bailian_asr_url).mock(side_effect=httpx.TimeoutException("timeout"))
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "UPSTREAM_TIMEOUT"
    assert response.json()["error"]["stage"] == "asr"


def test_asr_encoded_size_too_large(client, audio_dir, monkeypatch):
    monkeypatch.setattr(settings, "max_asr_base64_bytes", 16)
    audio_id = write_upload(audio_dir, payload=b"0123456789")
    response = client.post("/asr", json={"audio_id": audio_id})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert response.json()["error"]["stage"] == "asr"
