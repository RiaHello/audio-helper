from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from schemas import AsrRequest, AsrResponse, ErrorResponse
from services.asr import transcribe
from services.store import get_upload

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/asr",
    response_model=AsrResponse,
    responses={
        404: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
)
async def create_asr(request: Request, body: AsrRequest) -> AsrResponse:
    audio_path = get_upload(body.audio_id, stage="asr")
    logger.info("asr started; stage=asr; audio_id=%s", body.audio_id)
    text = await transcribe(audio_path)
    return AsrResponse(request_id=request.state.request_id, data={"text": text})
