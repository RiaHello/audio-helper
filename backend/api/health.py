from fastapi import APIRouter, Request

from schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def get_health(request: Request) -> HealthResponse:
    return HealthResponse(request_id=request.state.request_id, data={"status": "ok"})
