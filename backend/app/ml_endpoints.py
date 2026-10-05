"""HTTP interface for the Week 8 valuation and lead-scoring models."""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from .services.ml_service import MODEL_BUNDLE_PATH, MODEL_VERSION, models
from .config import settings
from .services.security import require_api_key

router = APIRouter(tags=["week8-ml"])


class PriceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    city: str = Field(..., min_length=2, max_length=80)
    location: str = Field(..., min_length=2, max_length=120)
    property_type: str = Field(..., min_length=2, max_length=40)
    area_marla: float = Field(..., gt=0, le=500)
    bedrooms: float = Field(0, ge=0, le=50)
    bathrooms: float = Field(0, ge=0, le=50)
    listed_price: float | None = Field(None, ge=0)
    province_name: str = Field("Unknown", max_length=80)
    purpose: str = Field("For Sale", max_length=40)
    area_type: str = Field("Marla", max_length=40)
    latitude: float = Field(0, ge=-90, le=90)
    longitude: float = Field(0, ge=-180, le=180)
    amenity_score: float = Field(3, ge=0, le=5)
    listing_year: int = Field(2019, ge=2000, le=2100)


class LeadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field("call", min_length=2, max_length=40)
    budget_pkr: float = Field(..., gt=0)
    preferred_city: str = Field(..., min_length=2, max_length=80)
    purpose: str = Field("buy", max_length=30)
    number_of_calls: float = Field(0, ge=0, le=100)
    call_duration_seconds: float = Field(0, ge=0, le=86400)
    response_time_minutes: float = Field(0, ge=0, le=100000)
    visit_booked: int = Field(0, ge=0, le=1)
    days_since_first_contact: float = Field(0, ge=0, le=3650)
    objection_raised: str = Field("none", max_length=40)


@router.get("/health")
def ml_health() -> Dict[str, Any]:
    return {"status": "ok", "model_version": MODEL_VERSION, "trained": models.price_model is not None, "artifact_loaded": models.artifact_loaded, "artifact_path": str(MODEL_BUNDLE_PATH)}


@router.get("/model/info")
def model_info() -> Dict[str, Any]:
    try:
        models.ensure_trained()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {"model_version": MODEL_VERSION, "metrics": models.metrics, "source": "dataset_properties.csv", "trained_date": models.trained_at, "artifact_loaded": models.artifact_loaded}


@router.post("/predict/price", dependencies=[Depends(require_api_key)])
def predict_price(request: PriceRequest) -> Dict[str, Any]:
    try:
        return models.predict_price(request.model_dump())
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/explain/price", dependencies=[Depends(require_api_key)])
def explain_price(request: PriceRequest) -> Dict[str, Any]:
    try:
        return models.explain("price", request.model_dump())
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/predict/lead-score", dependencies=[Depends(require_api_key)])
def predict_lead(request: LeadRequest) -> Dict[str, Any]:
    try:
        return models.score_lead(request.model_dump())
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"{type(error).__name__}: {error}") from error


@router.post("/explain/lead", dependencies=[Depends(require_api_key)])
def explain_lead(request: LeadRequest) -> Dict[str, Any]:
    try:
        return models.explain("lead", request.model_dump())
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/predict/batch", dependencies=[Depends(require_api_key)])
async def predict_batch(file: UploadFile = File(...)) -> Dict[str, Any]:
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV upload must be 5 MB or smaller")
    try:
        rows = list(csv.DictReader(io.StringIO(content.decode("utf-8"))))
    except (UnicodeDecodeError, csv.Error) as error:
        raise HTTPException(status_code=400, detail="Upload must be a UTF-8 CSV file") from error
    if not rows or len(rows) > settings.ml_max_batch_rows:
        raise HTTPException(status_code=400, detail=f"CSV must contain between 1 and {settings.ml_max_batch_rows} rows")
    results: List[Dict[str, Any]] = []
    for row in rows:
        try:
            results.append(models.predict_price(row))
        except (TypeError, ValueError, RuntimeError) as error:
            results.append({"error": str(error)})
    return {"results": results, "model_version": MODEL_VERSION}