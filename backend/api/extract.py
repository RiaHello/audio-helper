from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from schemas import ErrorResponse, ExtractRequest, ExtractResponse
from services.extract import extract_meetup

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/extract",
    response_model=ExtractResponse,
    responses={
        422: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
)
async def create_extract(request: Request, body: ExtractRequest) -> ExtractResponse:
    logger.info("extract started; stage=extract; text_len=%s", len(body.text))
    data = await extract_meetup(body.text, body.city)
    return ExtractResponse(request_id=request.state.request_id, data=data)
