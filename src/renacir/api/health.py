from fastapi import APIRouter

from renacir.models.health import HealthResponse
from renacir.services.health import HealthService

router = APIRouter(tags=["health"])
_health_service = HealthService()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return _health_service.get_health()
