"""Stateless FastAPI inference with private request logs and per-process metrics."""

import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator

from heart_risk.inference import ModelService
from heart_risk.schema import validate_features

logger = logging.getLogger("heart_risk.requests")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())


class Patient(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
        json_schema_extra={
            "examples": [
                {
                    "age": 63,
                    "sex": 1,
                    "cp": 1,
                    "trestbps": 145,
                    "chol": 233,
                    "fbs": 1,
                    "restecg": 2,
                    "thalach": 150,
                    "exang": 0,
                    "oldpeak": 2.3,
                    "slope": 3,
                    "ca": 0,
                    "thal": 6,
                }
            ]
        },
    )
    age: float = Field(gt=0, description="Age in years")
    sex: float = Field(json_schema_extra={"enum": [0, 1]})
    cp: float = Field(json_schema_extra={"enum": [1, 2, 3, 4]})
    trestbps: float = Field(gt=0, description="Resting blood pressure, mm Hg")
    chol: float = Field(gt=0, description="Serum cholesterol, mg/dl")
    fbs: float = Field(json_schema_extra={"enum": [0, 1]})
    restecg: float = Field(json_schema_extra={"enum": [0, 1, 2]})
    thalach: float = Field(gt=0, description="Maximum heart rate achieved, bpm")
    exang: float = Field(json_schema_extra={"enum": [0, 1]})
    oldpeak: float = Field(ge=0, description="Exercise-induced ST depression")
    slope: float = Field(json_schema_extra={"enum": [1, 2, 3]})
    ca: float | None = Field(
        description="Vessels: 0, 1, 2, 3; null if unknown",
        json_schema_extra={"enum": [0, 1, 2, 3, None]},
    )
    thal: float | None = Field(
        description="3=normal, 6=fixed defect, 7=reversible; null if unknown",
        json_schema_extra={"enum": [3, 6, 7, None]},
    )

    @model_validator(mode="before")
    @classmethod
    def original_uci_schema(cls, value):
        if not isinstance(value, dict):
            raise ValueError("Input must be one JSON patient object")
        return validate_features(value)


class Prediction(BaseModel):
    prediction: int = Field(ge=0, le=1)
    disease_probability: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    model_version: str
    request_id: str


def create_app(model_dir: Path | None = None, service=None) -> FastAPI:
    registry = CollectorRegistry()
    requests = Counter(
        "heart_requests_total", "HTTP requests", ["method", "route", "status"], registry=registry
    )
    latency = Histogram(
        "heart_request_seconds",
        "HTTP request latency",
        ["route"],
        registry=registry,
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
    )
    predictions = Counter(
        "heart_predictions_total", "Predicted labels", ["prediction"], registry=registry
    )

    @asynccontextmanager
    async def lifespan(application):
        application.state.service = service or ModelService(
            model_dir or Path(os.environ.get("MODEL_DIR", "models"))
        )
        yield
        application.state.service = None

    app = FastAPI(
        title="Cleveland Heart Risk API",
        version="1.0.0",
        lifespan=lifespan,
        description="Educational disease-presence classifier. Not a clinical diagnostic service.",
    )
    app.state.service = None

    @app.middleware("http")
    async def observe(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            response = JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal prediction service error",
                    "request_id": request.state.request_id,
                },
            )
        elapsed = time.perf_counter() - started
        route = getattr(request.scope.get("route"), "path", "unmatched")
        if route != "/metrics":
            method = (
                request.method
                if request.method in {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}
                else "OTHER"
            )
            requests.labels(method, route, str(status)).inc()
            latency.labels(route).observe(elapsed)
            active = app.state.service
            logger.info(
                json.dumps(
                    {
                        "timestamp": datetime.now(UTC).isoformat(),
                        "request_id": request.state.request_id,
                        "method": method,
                        "route": route,
                        "status": status,
                        "duration_seconds": elapsed,
                        "model_version": active.metadata["model_version"] if active else None,
                    }
                )
            )
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.get("/healthz")
    def health():
        return {"status": "alive"}

    @app.get("/readyz")
    def ready():
        if app.state.service is None:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return {"status": "ready", "model_version": app.state.service.metadata["model_version"]}

    @app.post("/predict", response_model=Prediction)
    def predict(patient: Patient, request: Request):
        if app.state.service is None:
            return JSONResponse(status_code=503, content={"detail": "Model unavailable"})
        result = app.state.service.predict(patient.model_dump())
        predictions.labels(str(result["prediction"])).inc()
        return {**result, "request_id": request.state.request_id}

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(registry), headers={"Content-Type": CONTENT_TYPE_LATEST})

    return app


app = create_app()
