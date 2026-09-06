from uuid import uuid4

from fastapi import APIRouter

from schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse(request_id=str(uuid4()), data={"status": "ok"})
