from __future__ import annotations

from datetime import date

import pytest

from backend.nlp.skill_verifier import (
    SkillVerifier,
    VerificationStatus,
    _extract_dates,
    _parse_date_string,
)


def test_self_declared_skill_without_upload_is_accepted() -> None:
    verifier = SkillVerifier(use_vision_api=False)
    result = verifier.verify_certificate(
        volunteer_id="vol-1",
        skill_key="teaching",
        file_bytes=None,
        file_mime=None,
    )

    assert result.status == VerificationStatus.SELF_DECLARED


def test_missing_required_upload_returns_missing() -> None:
    verifier = SkillVerifier(use_vision_api=False)
    result = verifier.verify_certificate(
        volunteer_id="vol-2",
        skill_key="first_aid",
        file_bytes=None,
        file_mime=None,
    )

    assert result.status == VerificationStatus.MISSING


def test_pending_review_when_ocr_unavailable() -> None:
    verifier = SkillVerifier(use_vision_api=False)
    result = verifier.verify_certificate(
        volunteer_id="vol-3",
        skill_key="first_aid",
        file_bytes=b"dummy-bytes",
        file_mime="image/png",
    )

    assert result.status == VerificationStatus.PENDING_REVIEW
    assert result.requires_manual is True


def test_rejected_when_keywords_do_not_match(monkeypatch: pytest.MonkeyPatch) -> None:
    verifier = SkillVerifier(use_vision_api=False)
    monkeypatch.setattr(verifier, "_ocr", lambda file_bytes, file_mime: "Certificate of music appreciation")

    result = verifier.verify_certificate(
        volunteer_id="vol-4",
        skill_key="first_aid",
        file_bytes=b"x",
        file_mime="image/jpeg",
    )

    assert result.status == VerificationStatus.REJECTED


def test_verified_with_recent_issue_and_future_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    verifier = SkillVerifier(use_vision_api=False)
    monkeypatch.setattr(
        verifier,
        "_ocr",
        lambda file_bytes, file_mime: (
            "First Aid and CPR Certificate\\n"
            "Issue Date: 01/01/2025\\n"
            "Expiry: 01/01/2030"
        ),
    )

    result = verifier.verify_certificate(
        volunteer_id="vol-5",
        skill_key="first_aid",
        file_bytes=b"x",
        file_mime="image/jpeg",
    )

    assert result.status == VerificationStatus.VERIFIED
    assert result.issue_date is not None
    assert result.expiry_date is not None


def test_date_parsing_helpers() -> None:
    assert _parse_date_string("01/12/2025") == date(2025, 12, 1)

    issue, expiry = _extract_dates("Issued: 01/01/2024 Expires: 01/01/2028")
    assert issue is not None
    assert expiry is not None
