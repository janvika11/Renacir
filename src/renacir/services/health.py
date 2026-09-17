from renacir.models.health import HealthResponse


class HealthService:
    def get_health(self) -> HealthResponse:
        return HealthResponse()
