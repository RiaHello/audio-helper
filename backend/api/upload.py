from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Request, UploadFile

from config import settings
from errors import AppError
from schemas import ErrorResponse, UploadResponse
from services.audio_probe import probe_audio
from services.store import ensure_storage_dirs, save_upload

logger = logging.getLogger(__name__)

router = APIRouter()
READ_CHUNK_SIZE = 64 * 1024


async def _save_upload_to_temp(file: UploadFile) -> tuple[Path, int]:
    ensure_storage_dirs()
    temp_path = settings.tmp_dir / f"upload-{uuid4().hex}.part"
    size = 0
    try:
        with temp_path.open("wb") as buffer:
            while True:
                chunk = await file.read(READ_CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.max_audio_bytes:
                    raise AppError(
                        413,
                        "FILE_TOO_LARGE",
                        "录音文件超过 5MB，请缩短录音后重试。",
                        "upload",
                    )
                buffer.write(chunk)
    except AppError:
        temp_path.unlink(missing_ok=True)
        raise
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    if size == 0:
        temp_path.unlink(missing_ok=True)
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "上传文件为空，请重新录音后重试。",
            "upload",
        )
    return temp_path, size


@router.post(
    "/upload",
    response_model=UploadResponse,
    responses={
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
async def upload_audio(
    request: Request,
    file: UploadFile = File(..., alias="file"),
) -> UploadResponse:
    temp_path: Path | None = None
    try:
        temp_path, size = await _save_upload_to_temp(file)
        probe = await asyncio.to_thread(probe_audio, temp_path)
        audio_id = save_upload(
            temp_path,
            size_bytes=size,
            duration_seconds=probe["duration_seconds"],
            container=probe["container"],
            codec=probe["codec"],
        )
        temp_path = None
        logger.info(
            "upload succeeded; stage=upload; audio_id=%s; size=%s; duration=%.3f",
            audio_id,
            size,
            probe["duration_seconds"],
        )
        return UploadResponse(
            request_id=request.state.request_id,
            data={"audio_id": audio_id},
        )
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        await file.close()
