"""Pilot endpoints for operator-supervised L0 Form-Inspection Pilot (Phase 2.1).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 11, Section 12)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from worker.pilot.models import (
    PilotFormRecord,
    PilotQualityReport,
    PilotReviewRequest,
)
from worker.pilot.orchestrator import PilotOrchestrator
from worker.profile.localfile import LocalFileProfileSource

logger = logging.getLogger("services.api.routes.pilot")

router = APIRouter(prefix="/api/v1/pilot", tags=["Pilot"])

_orchestrator_instance: Optional[PilotOrchestrator] = None


def get_pilot_orchestrator() -> PilotOrchestrator:
    """Dependency injector for PilotOrchestrator singleton."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = PilotOrchestrator()
    return _orchestrator_instance


class InspectFormRequest(BaseModel):
    """Payload to trigger an operator L0 inspection."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    provider: str = Field(..., description="Provider name (greenhouse, lever, ashby, naukri, etc.)")
    job_url: str = Field(..., description="Job application URL")
    company: str = Field(..., description="Company name")
    title: str = Field(..., description="Job title")
    job_id: Optional[str] = Field(default=None)


@router.post("/inspect", response_model=PilotFormRecord, status_code=status.HTTP_201_CREATED)
async def trigger_inspection(
    payload: InspectFormRequest,
    orchestrator: PilotOrchestrator = Depends(get_pilot_orchestrator),
) -> PilotFormRecord:
    """Execute an operator-controlled L0 form inspection and build truthful fill plan."""
    try:
        profile_source = LocalFileProfileSource("fixtures/profile.yaml")
        profile = await profile_source.get_snapshot()

        record = await orchestrator.inspect_form(
            user_id=payload.user_id,
            provider_name=payload.provider,
            job_url=payload.job_url,
            company=payload.company,
            title=payload.title,
            profile=profile,
            job_id=payload.job_id,
            is_live_page=payload.job_url.startswith("http"),
        )
        return record
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Error during pilot form inspection: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Inspection failed.")


@router.get("/records", response_model=List[PilotFormRecord])
async def list_records(
    user_id: Optional[UUID] = Query(default=None),
    orchestrator: PilotOrchestrator = Depends(get_pilot_orchestrator),
) -> List[PilotFormRecord]:
    """List all inspected pilot forms, optionally filtered by user."""
    return orchestrator.list_records(user_id=user_id)


@router.get("/records/{record_id}", response_model=PilotFormRecord)
async def get_record(
    record_id: UUID,
    orchestrator: PilotOrchestrator = Depends(get_pilot_orchestrator),
) -> PilotFormRecord:
    """Retrieve detailed metadata and field schema for an inspected form."""
    rec = orchestrator.get_record(record_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pilot record not found.")
    return rec


@router.post("/records/{record_id}/review", response_model=PilotFormRecord)
async def submit_human_review(
    record_id: UUID,
    payload: PilotReviewRequest,
    orchestrator: PilotOrchestrator = Depends(get_pilot_orchestrator),
) -> PilotFormRecord:
    """Submit human operator review for a pilot inspection record."""
    try:
        updated_rec = orchestrator.record_human_review(record_id, payload)
        return updated_rec
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to submit review for record %s: %s", record_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Review recording failed.")


@router.get("/metrics", response_model=PilotQualityReport)
async def get_pilot_metrics(
    orchestrator: PilotOrchestrator = Depends(get_pilot_orchestrator),
) -> PilotQualityReport:
    """Retrieve aggregate pilot metrics, reviewed accuracy, and gate readiness."""
    return orchestrator.generate_quality_report()
