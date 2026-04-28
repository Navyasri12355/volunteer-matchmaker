"""Best-effort processing hooks for uploaded NGO/volunteer/event documents."""

from __future__ import annotations

import logging
from pathlib import Path
from dataclasses import asdict
from typing import Any

from sqlalchemy.orm import Session

from api.core.config import settings
from api.models.ngo import NGO
from api.models.skill import SkillCertificate, SkillVerificationStatus
from api.models.volunteer import Volunteer
from api.services.ingestion_service import IngestionService
from api.services.matching_service import MatchingService
from api.services.nlp_service import NLPService
from api.services.trust_service import TrustService
from backend.ingestion.ingestor import chunk_documents, load_document
from backend.nlp.event_nlp_extractor import EventNLPExtractor
from backend.nlp.skill_verifier import SkillVerifier
from backend.nlp.severity_engine import SeverityEngine

logger = logging.getLogger(__name__)


def _serialize_severity_result(result) -> dict[str, Any]:
    # Support either backend object with attributes or a pre-converted dict
    if isinstance(result, dict):
        return result
    return {
        "score": result.score,
        "band": result.band.value if hasattr(result.band, "value") else str(result.band),
        "map_color": result.map_color,
        "breakdown": result.breakdown,
        "top_evidence": result.top_evidence,
        "warnings": result.warnings,
    }


def _serialize_verification_result(result) -> dict[str, Any]:
    return {
        "volunteer_id": result.volunteer_id,
        "skill_key": result.skill_key,
        "status": result.status.value if hasattr(result.status, "value") else str(result.status),
        "issue_date": result.issue_date.isoformat() if result.issue_date else None,
        "expiry_date": result.expiry_date.isoformat() if result.expiry_date else None,
        "verified_at": result.verified_at.isoformat() if result.verified_at else None,
        "ocr_text_snippet": result.ocr_text_snippet,
        "failure_reason": result.failure_reason,
        "requires_manual": result.requires_manual,
        "storage_path": result.storage_path,
    }


def _collect_text_blocks(filepaths: list[str]) -> list[str]:
    texts: list[str] = []
    for file_path in filepaths:
        try:
            raw_docs = load_document(file_path)
            chunks = chunk_documents(raw_docs)
            page_texts: dict[int, list[str]] = {}
            for chunk in chunks:
                page_number = int(chunk["metadata"].get("page", 1))
                page_texts.setdefault(page_number, []).append(chunk["content"])
            for page_content in page_texts.values():
                texts.append(" ".join(page_content))
        except Exception as exc:
            logger.warning("Failed to read %s for pipeline text extraction: %s", Path(file_path).name, exc)
    return texts


def _mime_from_path(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    if suffix == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return "application/octet-stream"


async def process_event_upload_pipeline(
    db: Session,
    event_id: str,
    ngo_id: str,
    category: str,
    location_name: str,
    lat: float,
    lng: float,
    affected_population: int | None,
    affected_area_km2: float | None,
    severity_band: str,
    filepaths: list[str],
) -> dict[str, Any]:
    """Run the event upload pipeline and return a structured summary."""
    stage_status = {
        "storage": "done",
        "ingestion": "pending",
        "nlp": "pending",
        "matching": "pending",
        "trust": "pending",
    }
    summary: dict[str, Any] = {
        "event_id": event_id,
        "stage_status": stage_status,
        "severity": None,
        "entities": None,
        "matches": [],
    }

    try:
        ingestion = IngestionService(engine=SeverityEngine())
        severity_result, marker = await ingestion.process_event_documents(
            filepaths=filepaths,
            category=category,
            location_name=location_name,
            affected_population=affected_population,
            affected_area_km2=affected_area_km2,
        )
        stage_status["ingestion"] = "done"

        texts = _collect_text_blocks(filepaths)
        nlp = NLPService(SeverityEngine(), EventNLPExtractor(use_gcp_nl=settings.use_gcp_nl_api))
        entities = await nlp.extract_entities(texts)
        stage_status["nlp"] = "done"

        matches = await MatchingService.rank_volunteers_for_event(
            db=db,
            event_id=event_id,
            event_lat=lat,
            event_lng=lng,
            event_category=category,
            event_severity_band=severity_band,
        )
        stage_status["matching"] = "done" if matches else "done-empty"

        trust_service = TrustService()
        allowed, reason = await trust_service.check_ngo_can_create_event(db, ngo_id)
        stage_status["trust"] = "done" if allowed else f"blocked: {reason}"

        summary.update(
            {
                "severity": _serialize_severity_result(severity_result),
                "marker": marker,
                "entities": entities if isinstance(entities, dict) else asdict(entities),
                "matches": matches,
                "trust_gate": {"allowed": allowed, "reason": reason},
            }
        )
    except Exception as exc:
        stage_status["ingestion"] = f"failed: {exc}"
        stage_status["nlp"] = "skipped"
        logger.warning("Event pipeline failed for %s: %s", event_id, exc)

    _ = severity_band
    logger.info("Event pipeline status for %s: %s", event_id, stage_status)
    return summary


async def process_volunteer_upload_pipeline(
    db: Session,
    volunteer_id: str,
    skill_key: str,
    filepaths: list[str],
) -> dict[str, Any]:
    """Run the volunteer certificate pipeline and return a structured summary."""
    stage_status = {
        "storage": "done",
        "ingestion": "pending",
        "nlp": "pending",
        "matching": "pending",
        "trust": "pending",
    }
    summary: dict[str, Any] = {
        "volunteer_id": volunteer_id,
        "skill_key": skill_key,
        "stage_status": stage_status,
        "verification": None,
        "match_summary": None,
        "trust": None,
    }

    try:
        texts = _collect_text_blocks(filepaths)
        stage_status["ingestion"] = "done" if texts else "done-empty"

        verifier = SkillVerifier(use_vision_api=settings.use_cloud_vision, gcp_project=settings.gcp_project)
        verification_result = None
        for file_path in filepaths:
            file_bytes = Path(file_path).read_bytes()
            verification_result = verifier.verify_certificate(
                volunteer_id=volunteer_id,
                skill_key=skill_key,
                file_bytes=file_bytes,
                file_mime=_mime_from_path(file_path),
                storage_path=file_path,
            )
        stage_status["nlp"] = "done"

        volunteer = db.query(Volunteer).filter(Volunteer.volunteer_id == volunteer_id).first()
        match_summary = MatchingService.evaluate_volunteer_profile(volunteer, skill_key=skill_key) if volunteer else None
        stage_status["matching"] = "done" if match_summary else "skipped"

        trust_service = TrustService()
        ledger = await trust_service.scorer.get_volunteer_ledger(volunteer_id)
        stage_status["trust"] = "done"

        if verification_result is not None:
            # Query for existing certificate matching the uploaded files
            certificate = (
                db.query(SkillCertificate)
                .filter(
                    SkillCertificate.volunteer_id == volunteer_id,
                    SkillCertificate.skill_key == skill_key,
                    SkillCertificate.storage_path.in_(filepaths),
                )
                .first()
            )
            
            # If no exact match, try to find the most recent certificate for this skill
            if certificate is None:
                certificate = (
                    db.query(SkillCertificate)
                    .filter(
                        SkillCertificate.volunteer_id == volunteer_id,
                        SkillCertificate.skill_key == skill_key,
                    )
                    .order_by(SkillCertificate.created_at.desc())
                    .first()
                )
            
            # Update certificate status from verification result
            if certificate is not None:
                certificate.status = SkillVerificationStatus(verification_result.status.value)
                certificate.expiry_date = verification_result.expiry_date
                certificate.failure_reason = verification_result.failure_reason
                certificate.requires_manual = verification_result.requires_manual
                certificate.verified_at = verification_result.verified_at
            
            # If verification succeeded, add skill to volunteer profile
            if volunteer is not None and verification_result.status.value in {"verified", "self_declared"}:
                skills = list(volunteer.skills or [])
                if skill_key not in skills:
                    skills.append(skill_key)
                volunteer.skills = skills
                volunteer.is_verified = True
            
            db.commit()

        summary.update(
            {
                "verification": _serialize_verification_result(verification_result) if verification_result is not None else None,
                "match_summary": match_summary,
                "trust": ledger.to_firestore_dict(),
            }
        )
    except Exception as exc:
        stage_status["ingestion"] = f"failed: {exc}"
        stage_status["nlp"] = "skipped"
        logger.warning("Volunteer pipeline failed for %s: %s", volunteer_id, exc)

    logger.info("Volunteer pipeline status for %s: %s", volunteer_id, stage_status)
    return summary


async def process_ngo_upload_pipeline(
    db: Session,
    ngo_id: str,
    filepaths: list[str],
) -> dict[str, Any]:
    """Run the NGO document pipeline and return a structured summary."""
    stage_status = {
        "storage": "done",
        "ingestion": "pending",
        "nlp": "pending",
        "matching": "pending",
        "trust": "pending",
    }
    summary: dict[str, Any] = {
        "ngo_id": ngo_id,
        "stage_status": stage_status,
        "severity": None,
        "entities": None,
        "trust": None,
    }

    try:
        ingestion = IngestionService(engine=SeverityEngine())
        severity_result, marker = await ingestion.process_event_documents(
            filepaths=filepaths,
            category="education",
            location_name="ngo-document",
        )
        stage_status["ingestion"] = "done"

        texts = _collect_text_blocks(filepaths)
        nlp = NLPService(SeverityEngine(), EventNLPExtractor(use_gcp_nl=settings.use_gcp_nl_api))
        entities = await nlp.extract_entities(texts)
        stage_status["nlp"] = "done"

        ngo = db.query(NGO).filter(NGO.ngo_id == ngo_id).first()
        if ngo is not None:
            trust_service = TrustService()
            allowed, reason = await trust_service.check_ngo_can_create_event(db, ngo_id)
            stage_status["trust"] = "done" if allowed else f"blocked: {reason}"
            summary["trust"] = {"allowed": allowed, "reason": reason, "trust_score": ngo.trust_score}
        else:
            stage_status["trust"] = "skipped"

        summary.update(
            {
                "severity": _serialize_severity_result(severity_result),
                "marker": marker,
                "entities": asdict(entities),
            }
        )
    except Exception as exc:
        stage_status["ingestion"] = f"failed: {exc}"
        stage_status["nlp"] = "skipped"
        logger.warning("NGO pipeline failed for %s: %s", ngo_id, exc)

    logger.info("NGO pipeline status for %s: %s", ngo_id, stage_status)
    return summary
