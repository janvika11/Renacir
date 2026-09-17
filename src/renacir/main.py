from fastapi import FastAPI

from renacir.api.health import router as health_router
from renacir.config import settings
from renacir.utils.logging import configure_logging

configure_logging(settings.log_level)

app = FastAPI(title="Renacir", version="0.1.0")
app.include_router(health_router)
