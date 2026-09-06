import logging
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import api_router
from config import settings
from errors import AppError
from schemas import ErrorResponse
from services.store import ensure_storage_dirs

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

app = FastAPI(title="语音约碰面地点", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request.state.request_id = str(uuid4())
    return await call_next(request)


def _error_payload(request: Request, code: str, message: str, stage: str) -> dict:
    payload = ErrorResponse(
        request_id=getattr(request.state, "request_id", str(uuid4())),
        error={"code": code, "message": message, "stage": stage},
    )
    return payload.model_dump()


def _stage_from_path(path: str) -> str:
    if path.rstrip("/").endswith("/upload"):
        return "upload"
    if path.rstrip("/").endswith("/health"):
        return "health"
    return "unknown"


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(request, exc.code, exc.message, exc.stage),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    stage = _stage_from_path(request.url.path)
    message = "请求缺少文件字段 file，或字段类型不正确。" if stage == "upload" else "请求字段不正确。"
    return JSONResponse(
        status_code=422,
        content=_error_payload(request, "VALIDATION_ERROR", message, stage),
    )


@app.on_event("startup")
def on_startup() -> None:
    ensure_storage_dirs()


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
