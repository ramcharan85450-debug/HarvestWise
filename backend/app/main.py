from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    routes_benchmark,
    routes_explain,
    routes_fields,
    routes_forecast,
    routes_harvest,
    routes_outcomes,
    routes_scenario,
)
from app.config import APP_TITLE, APP_VERSION, CORS_ALLOW_ORIGINS
from app.models_registry.model_loader import available_checkpoints, models_are_live
from app.services.errors import RealDataUnavailable

app = FastAPI(title=APP_TITLE, version=APP_VERSION)


@app.exception_handler(RealDataUnavailable)
def real_data_unavailable_handler(request: Request, exc: RealDataUnavailable):
    """503 with the reason, rather than a 200 carrying a simulated answer.

    A consumer that cannot tell a real forecast from a placeholder one will
    eventually present a placeholder as a result. Making the absence loud is
    the only version of this that stays safe as the project is demoed and
    written up.
    """
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc), "reason": "real_data_unavailable"},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(routes_fields.router)
app.include_router(routes_forecast.router)
app.include_router(routes_harvest.router)
app.include_router(routes_explain.router)
app.include_router(routes_benchmark.router)
app.include_router(routes_scenario.router)
app.include_router(routes_outcomes.router)


@app.get("/health", tags=["health"])
def health():
    return {
        "status": "ok",
        "models_live": models_are_live(),
        "checkpoints": available_checkpoints(),
    }
