"""
skill_verifier.py
-----------------
Handles verification of volunteer skill certificates.

Responsibilities
~~~~~~~~~~~~~~~~
- Accept an uploaded certificate file (image or PDF) and a declared skill.
- Check that the certificate is recent enough (configurable per skill type).
- Optionally use Google Cloud Vision API (Document AI / Vision OCR) to
  extract the issue/expiry date from the certificate image.
- Return a CertificateVerificationResult with status, expiry, and flags.

Google Cloud service used
~~~~~~~~~~~~~~~~~~~~~~~~~
- **Cloud Vision API** (TEXT_DETECTION) – free 1 000 units/month.
  Used to OCR the certificate image and extract dates.
  Falls back to a manual-review flag when Vision is unavailable.

Certificate storage
~~~~~~~~~~~~~~~~~~~
Certificates are stored in **Firebase Storage** (not Firestore).
This module only handles verification logic.
The path convention is:  volunteers/{volunteer_id}/certs/{skill_key}_{timestamp}.{ext}

Supported skills (spec says "first aid" as the example; others can be added)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Each skill type has:
  - A max_age_years: certificates older than this are rejected.
  - requires_upload: whether a file is mandatory (vs self-declared).
  - keywords: OCR hints to confirm the cert is for the right skill.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Skill type registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SkillType:
    key:            str
    display_name:   str
    max_age_years:  int         # cert older than this → expired
    requires_upload: bool       # must upload a cert file
    ocr_keywords:   List[str]   # words expected in a valid cert


SKILL_TYPES: dict[str, SkillType] = {
    "first_aid": SkillType(
        key="first_aid",
        display_name="First Aid",
        max_age_years=3,
        requires_upload=True,
        ocr_keywords=["first aid", "cpr", "basic life support", "bls", "red cross",
                       "st john", "american heart", "resuscitation"],
    ),
    "disaster_response": SkillType(
        key="disaster_response",
        display_name="Disaster Response",
        max_age_years=5,
        requires_upload=True,
        ocr_keywords=["disaster", "emergency response", "ndrf", "search and rescue",
                       "incident command"],
    ),
    "medical_professional": SkillType(
        key="medical_professional",
        display_name="Medical Professional",
        max_age_years=1,   # license must be current
        requires_upload=True,
        ocr_keywords=["medical council", "mbbs", "nursing", "paramedic", "doctor",
                       "license", "registration"],
    ),
    "water_sanitation": SkillType(
        key="water_sanitation",
        display_name="Water & Sanitation",
        max_age_years=5,
        requires_upload=False,   # self-declared + NGO confirms
        ocr_keywords=["wash", "water quality", "sanitation", "plumbing"],
    ),
    "teaching": SkillType(
        key="teaching",
        display_name="Teaching / Tutoring",
        max_age_years=10,
        requires_upload=False,
        ocr_keywords=["b.ed", "teacher", "education", "pedagogy"],
    ),
    "driving": SkillType(
        key="driving",
        display_name="Driving (Heavy Vehicle)",
        max_age_years=2,
        requires_upload=True,
        ocr_keywords=["driving licence", "motor vehicle", "transport", "heavy"],
    ),
}

# Any skill not in the registry is treated as self-declared, no cert needed.
UNKNOWN_SKILL_TYPE = SkillType(
    key="_unknown",
    display_name="Other",
    max_age_years=99,
    requires_upload=False,
    ocr_keywords=[],
)


# ---------------------------------------------------------------------------
# Verification result
# ---------------------------------------------------------------------------

class VerificationStatus(str, Enum):
    VERIFIED        = "verified"       # cert uploaded, OCR passed, not expired
    PENDING_REVIEW  = "pending_review" # uploaded but couldn't auto-verify (OCR failed)
    EXPIRED         = "expired"        # cert older than max_age_years
    REJECTED        = "rejected"       # cert not relevant to declared skill
    SELF_DECLARED   = "self_declared"  # skill doesn't require upload, taken at face value
    MISSING         = "missing"        # upload required but not provided


@dataclass
class CertificateVerificationResult:
    volunteer_id:      str
    skill_key:         str
    status:            VerificationStatus
    issue_date:        Optional[date]   = None
    expiry_date:       Optional[date]   = None
    verified_at:       Optional[datetime] = None
    ocr_text_snippet:  str             = ""
    failure_reason:    str             = ""
    requires_manual:   bool            = False   # flag for admin queue
    storage_path:      str             = ""      # Firebase Storage path


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------

class SkillVerifier:
    """
    Verifies volunteer skill certificates.

    Parameters
    ----------
    use_vision_api : bool
        If True, use Google Cloud Vision API for OCR.
        If False (or credentials absent), falls back to manual review flag.
    gcp_project : str | None
        GCP project ID.
    """

    def __init__(
        self,
        use_vision_api: bool = True,
        gcp_project: Optional[str] = None,
    ):
        self._project      = gcp_project or os.getenv("GCP_PROJECT", "")
        self._vision_client = self._init_vision(use_vision_api)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify_certificate(
        self,
        volunteer_id: str,
        skill_key: str,
        file_bytes: Optional[bytes],
        file_mime: Optional[str],       # "image/jpeg" | "image/png" | "application/pdf"
        storage_path: str = "",
    ) -> CertificateVerificationResult:
        """
        Verify a certificate for a volunteer.

        Parameters
        ----------
        volunteer_id  : Firestore volunteer document ID.
        skill_key     : Key from SKILL_TYPES (e.g. "first_aid").
        file_bytes    : Raw bytes of the uploaded certificate file.
                        Pass None if no file was uploaded.
        file_mime     : MIME type of the file.
        storage_path  : Firebase Storage path where the file was saved.
        """
        skill = SKILL_TYPES.get(skill_key, UNKNOWN_SKILL_TYPE)

        # Case 1: skill doesn't require upload
        if not skill.requires_upload:
            return CertificateVerificationResult(
                volunteer_id  = volunteer_id,
                skill_key     = skill_key,
                status        = VerificationStatus.SELF_DECLARED,
                verified_at   = datetime.now(timezone.utc),
                storage_path  = storage_path,
            )

        # Case 2: upload required but not provided
        if file_bytes is None:
            return CertificateVerificationResult(
                volunteer_id   = volunteer_id,
                skill_key      = skill_key,
                status         = VerificationStatus.MISSING,
                failure_reason = "Certificate upload is required for this skill.",
                storage_path   = storage_path,
            )

        # Case 3: try OCR verification
        ocr_text = self._ocr(file_bytes, file_mime or "image/jpeg")
        if not ocr_text:
            # OCR failed → flag for manual review
            return CertificateVerificationResult(
                volunteer_id   = volunteer_id,
                skill_key      = skill_key,
                status         = VerificationStatus.PENDING_REVIEW,
                failure_reason = "Could not read certificate automatically; queued for manual review.",
                requires_manual= True,
                storage_path   = storage_path,
            )

        # Check skill relevance
        lower_ocr = ocr_text.lower()
        keyword_hits = sum(1 for kw in skill.ocr_keywords if kw in lower_ocr)
        if keyword_hits == 0:
            return CertificateVerificationResult(
                volunteer_id   = volunteer_id,
                skill_key      = skill_key,
                status         = VerificationStatus.REJECTED,
                ocr_text_snippet = ocr_text[:300],
                failure_reason = (
                    f"Certificate does not appear to be a {skill.display_name} certificate "
                    f"(no matching keywords found)."
                ),
                requires_manual= True,  # could be legit; let admin check
                storage_path   = storage_path,
            )

        # Extract dates
        issue_date, expiry_date = _extract_dates(ocr_text)

        # Check expiry / age
        today = date.today()
        if expiry_date and expiry_date < today:
            return CertificateVerificationResult(
                volunteer_id     = volunteer_id,
                skill_key        = skill_key,
                status           = VerificationStatus.EXPIRED,
                issue_date       = issue_date,
                expiry_date      = expiry_date,
                ocr_text_snippet = ocr_text[:300],
                failure_reason   = f"Certificate expired on {expiry_date}.",
                storage_path     = storage_path,
            )

        if issue_date:
            age_years = (today - issue_date).days / 365.25
            if age_years > skill.max_age_years:
                return CertificateVerificationResult(
                    volunteer_id     = volunteer_id,
                    skill_key        = skill_key,
                    status           = VerificationStatus.EXPIRED,
                    issue_date       = issue_date,
                    ocr_text_snippet = ocr_text[:300],
                    failure_reason   = (
                        f"Certificate is {age_years:.1f} years old; "
                        f"maximum allowed for {skill.display_name} is {skill.max_age_years} years."
                    ),
                    storage_path     = storage_path,
                )

        # All checks passed
        return CertificateVerificationResult(
            volunteer_id     = volunteer_id,
            skill_key        = skill_key,
            status           = VerificationStatus.VERIFIED,
            issue_date       = issue_date,
            expiry_date      = expiry_date,
            verified_at      = datetime.now(timezone.utc),
            ocr_text_snippet = ocr_text[:300],
            storage_path     = storage_path,
        )

    # ------------------------------------------------------------------
    # OCR helpers
    # ------------------------------------------------------------------

    def _init_vision(self, use_vision_api: bool):
        if not use_vision_api or not self._project:
            return None
        try:
            from google.cloud import vision  # type: ignore
            client = vision.ImageAnnotatorClient()
            logger.info("Google Cloud Vision API client initialised.")
            return client
        except Exception as exc:
            logger.info("Vision API not available (%s) – manual review fallback.", exc)
            return None

    def _ocr(self, file_bytes: bytes, mime_type: str) -> str:
        """
        Run OCR on the file bytes.  Returns extracted text or empty string.
        """
        if self._vision_client:
            return self._ocr_vision(file_bytes, mime_type)
        # No Vision client → return empty to trigger manual review
        logger.info("No Vision client; certificate queued for manual review.")
        return ""

    def _ocr_vision(self, file_bytes: bytes, mime_type: str) -> str:
        from google.cloud import vision  # type: ignore

        try:
            image    = vision.Image(content=file_bytes)
            response = self._vision_client.document_text_detection(image=image)
            if response.error.message:
                logger.warning("Vision API error: %s", response.error.message)
                return ""
            return response.full_text_annotation.text or ""
        except Exception as exc:
            logger.warning("Vision OCR failed: %s", exc)
            return ""


# ---------------------------------------------------------------------------
# Date extraction helper
# ---------------------------------------------------------------------------

_DATE_PATTERNS = [
    # DD/MM/YYYY or DD-MM-YYYY
    re.compile(r"\b(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})\b"),
    # Month DD, YYYY  or DD Month YYYY
    re.compile(
        r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+(\d{4})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+(\d{1,2})[,\s]+(\d{4})\b",
        re.IGNORECASE,
    ),
    # YYYY-MM-DD
    re.compile(r"\b(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})\b"),
]

_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

_EXPIRY_CONTEXT = re.compile(
    r"(?:expiry|expiration|valid\s+until|valid\s+through|expires?)[:\s]*"
    r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}|\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}|"
    r"\d{1,2}\s+\w+\s+\d{4})",
    re.IGNORECASE,
)
_ISSUE_CONTEXT = re.compile(
    r"(?:issued?[:\s]+|issue\s+date[:\s]*|date\s+of\s+issue[:\s]*)"
    r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}|\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}|"
    r"\d{1,2}\s+\w+\s+\d{4})",
    re.IGNORECASE,
)


def _parse_date_string(s: str) -> Optional[date]:
    """Best-effort parse of a date string extracted from OCR text."""
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d",
                "%d %B %Y", "%B %d, %Y", "%B %d %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _extract_dates(text: str) -> tuple[Optional[date], Optional[date]]:
    """
    Return (issue_date, expiry_date) from OCR text.
    Both may be None if dates aren't found.
    """
    issue_date  = None
    expiry_date = None

    m = _EXPIRY_CONTEXT.search(text)
    if m:
        expiry_date = _parse_date_string(m.group(1))

    m = _ISSUE_CONTEXT.search(text)
    if m:
        issue_date = _parse_date_string(m.group(1))

    # Fall back: just grab all dates in order; assume first = issue, last = expiry
    if issue_date is None or expiry_date is None:
        all_dates: List[date] = []
        for pat in _DATE_PATTERNS:
            for raw in pat.findall(text):
                d = _parse_date_string("/".join(str(x) for x in raw))
                if d:
                    all_dates.append(d)
        all_dates = sorted(set(all_dates))
        if all_dates:
            if issue_date is None:
                issue_date = all_dates[0]
            if expiry_date is None and len(all_dates) > 1:
                expiry_date = all_dates[-1]

    return issue_date, expiry_date
