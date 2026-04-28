"""
trust_scorer.py
---------------
Computes and manages two distinct scoring systems:

1. **NGO Trust Score** – internal only; visible only to admins.
   Used as a gate for event creation (score must exceed threshold).
   Sources:
     - Post-event audit: volunteer reviews, attendance ratio, goal met flag
     - Number of completed events (activity signal)
     - Document quality at submission time (from severity_engine doc_strength)

2. **Volunteer Points Ledger** – public; shown on volunteer profiles.
   Points are additive; earned per event with multipliers for severity,
   skill match, and early acceptance.

Design decisions from spec
~~~~~~~~~~~~~~~~~~~~~~~~~~
- Scores are NOT published for NGOs; admin-only.
- Volunteer points ARE public.
- Don't over-depend on scoring early → all score updates are soft (weighted
  rolling average), not hard resets.
- Allow manual overrides → admin_override methods accept an optional reason.
- NGO gets a "Verified" tag from admin action, not from score alone.
- Scores act as an *audit tool*, not a public leaderboard for NGOs.

PostgreSQL storage
~~~~~~~~~~~~~~~~~~
NGO trust scores are stored on the NGO ORM model.
Volunteer points ledgers are stored on the Volunteer ORM model.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# NGO trust score thresholds
TRUST_GATE_THRESHOLD    = 0.40   # min trust score to create events
TRUST_VERIFIED_SIGNAL   = 0.70   # informational flag for admins (not auto-verified)

# Trust score component weights (must sum to 1.0)
TRUST_W_AUDIT_REVIEWS   = 0.40   # avg star rating from volunteer reviews
TRUST_W_GOAL_COMPLETION = 0.25   # fraction of events where goal was met
TRUST_W_ATTENDANCE      = 0.20   # actual / expected volunteers ratio
TRUST_W_ACTIVITY        = 0.15   # log-scaled number of completed events

# Rolling average smoothing factor (0 = never update, 1 = replace entirely)
# 0.25 means each new audit contributes 25% to the running score → stable
TRUST_EMA_ALPHA = 0.25

# Volunteer point values
VOL_POINTS_BASE_SHOW_UP   = 10    # just showing up
VOL_POINTS_GOAL_MET       = 15    # event goal was marked as met
VOL_POINTS_SEVERE_EVENT   = 10    # bonus for CRITICAL severity events
VOL_POINTS_SKILL_MATCH    = 5     # verified skill was used
VOL_POINTS_EARLY_ACCEPT   = 3     # accepted assignment within 24h
VOL_POINTS_PERFECT_REVIEW = 5     # received 5-star review from NGO

# Reliability score: ratio of accepted-and-showed-up to total assigned
# Below this → volunteer flagged as unreliable; affects matching rank
VOL_RELIABILITY_THRESHOLD = 0.60


# ---------------------------------------------------------------------------
# NGO Trust Score
# ---------------------------------------------------------------------------

@dataclass
class NGOTrustScore:
    """
    Running trust state for a single NGO.

    All score components are kept separately so admins can inspect
    which dimension is dragging the score down.
    """
    ngo_id: str

    # Running averages (initialised to neutral 0.5)
    avg_review_score:      float = 0.50   # 0–1 (normalised from 0–5 stars)
    avg_goal_completion:   float = 0.50   # 0–1
    avg_attendance_ratio:  float = 0.50   # 0–1 (capped at 1.0)
    activity_score:        float = 0.00   # 0–1 (log-scaled, grows with events)

    # Raw counters (for activity_score calculation)
    total_events_completed: int = 0
    total_events_created:   int = 0

    # Composite
    composite_score: float = 0.50

    # Admin flags
    is_verified:    bool = False   # set by admin only
    is_suspended:   bool = False
    admin_note:     str  = ""

    # Metadata
    last_updated: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Score update
    # ------------------------------------------------------------------

    def apply_audit(
        self,
        star_rating: float,        # 1–5 from volunteers
        goal_met: bool,
        attendance_ratio: float,   # actual_volunteers / expected_volunteers
    ) -> None:
        """
        Update running averages with a new post-event audit result.
        Uses exponential moving average so early bad events fade over time.
        """
        norm_review    = max(0.0, min((star_rating - 1) / 4.0, 1.0))
        norm_goal      = 1.0 if goal_met else 0.0
        norm_attendance = max(0.0, min(attendance_ratio, 1.0))

        alpha = TRUST_EMA_ALPHA
        self.avg_review_score     = _ema(self.avg_review_score,     norm_review,     alpha)
        self.avg_goal_completion  = _ema(self.avg_goal_completion,  norm_goal,       alpha)
        self.avg_attendance_ratio = _ema(self.avg_attendance_ratio, norm_attendance, alpha)

        self.total_events_completed += 1
        self.activity_score = _log_scale_activity(self.total_events_completed)

        self._recompute_composite()
        self.last_updated = datetime.now(timezone.utc)

        logger.info(
            "NGO %s trust updated → composite=%.3f (review=%.2f, goal=%.2f, attend=%.2f, activity=%.2f)",
            self.ngo_id, self.composite_score,
            self.avg_review_score, self.avg_goal_completion,
            self.avg_attendance_ratio, self.activity_score,
        )

    def on_event_created(self) -> None:
        """Call whenever the NGO creates a new event (increments counter)."""
        self.total_events_created += 1
        # Activity score is based on *completed* events, not created ones.
        # Creating many events with no follow-through should not boost trust.

    def can_create_event(self) -> Tuple[bool, str]:
        """
        Gate check: can this NGO create a new event?
        Returns (allowed: bool, reason: str).
        """
        if self.is_suspended:
            return False, "NGO account is suspended."
        if self.composite_score < TRUST_GATE_THRESHOLD:
            return False, (
                f"Trust score ({self.composite_score:.2f}) is below the minimum "
                f"threshold ({TRUST_GATE_THRESHOLD:.2f}).  Complete more events "
                f"or improve audit scores to unlock event creation."
            )
        return True, "OK"

    # ------------------------------------------------------------------
    # Admin overrides
    # ------------------------------------------------------------------

    def admin_set_verified(self, verified: bool, note: str = "") -> None:
        self.is_verified = verified
        self.admin_note  = note
        self.last_updated = datetime.now(timezone.utc)
        logger.info("NGO %s verified=%s by admin. Note: %s", self.ngo_id, verified, note)

    def admin_suspend(self, reason: str) -> None:
        self.is_suspended = True
        self.admin_note   = reason
        self.last_updated = datetime.now(timezone.utc)
        logger.warning("NGO %s SUSPENDED. Reason: %s", self.ngo_id, reason)

    def admin_override_score(self, new_score: float, note: str) -> None:
        """Direct score override by admin (use sparingly; logged)."""
        new_score = max(0.0, min(1.0, new_score))
        logger.warning(
            "ADMIN OVERRIDE: NGO %s score set from %.3f to %.3f. Note: %s",
            self.ngo_id, self.composite_score, new_score, note,
        )
        self.composite_score = new_score
        self.admin_note      = f"[OVERRIDE] {note}"
        self.last_updated    = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _recompute_composite(self) -> None:
        self.composite_score = round(
            TRUST_W_AUDIT_REVIEWS   * self.avg_review_score
            + TRUST_W_GOAL_COMPLETION * self.avg_goal_completion
            + TRUST_W_ATTENDANCE      * self.avg_attendance_ratio
            + TRUST_W_ACTIVITY        * self.activity_score,
            4,
        )


# ---------------------------------------------------------------------------
# Volunteer Points Ledger
# ---------------------------------------------------------------------------

@dataclass
class PointsEntry:
    event_id:    str
    points:      int
    reason:      str
    earned_at:   datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class VolunteerPointsLedger:
    """
    Tracks points and reliability for a single volunteer.
    Points are public; reliability_score is used internally for matching.
    """
    volunteer_id: str

    total_points:       int   = 0
    reliability_score:  float = 1.0   # starts optimistic
    events_assigned:    int   = 0
    events_attended:    int   = 0
    events_accepted:    int   = 0     # confirmed after assignment
    history: List[PointsEntry] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Points earning
    # ------------------------------------------------------------------

    def record_attendance(
        self,
        event_id: str,
        severity_band: str,     # "CRITICAL" | "MODERATE" | "LOW"
        goal_met: bool,
        skill_used: bool,
        early_accept: bool,
        ngo_star_rating: float, # 1–5 from NGO review
    ) -> int:
        """Award points for a completed event. Returns points earned."""
        earned = VOL_POINTS_BASE_SHOW_UP

        if goal_met:
            earned += VOL_POINTS_GOAL_MET
        if severity_band == "CRITICAL":
            earned += VOL_POINTS_SEVERE_EVENT
        elif severity_band == "MODERATE":
            earned += VOL_POINTS_SEVERE_EVENT // 2
        if skill_used:
            earned += VOL_POINTS_SKILL_MATCH
        if early_accept:
            earned += VOL_POINTS_EARLY_ACCEPT
        if ngo_star_rating >= 5.0:
            earned += VOL_POINTS_PERFECT_REVIEW

        self.total_points += earned
        self.events_attended += 1
        self.history.append(PointsEntry(
            event_id=event_id,
            points=earned,
            reason=(
                f"Attended | severity={severity_band} | goal={'met' if goal_met else 'unmet'}"
                f"{' | skill' if skill_used else ''}{' | early' if early_accept else ''}"
            ),
        ))
        self._update_reliability()

        logger.info(
            "Volunteer %s earned %d points for event %s (total=%d)",
            self.volunteer_id, earned, event_id, self.total_points,
        )
        return earned

    def record_no_show(self, event_id: str) -> None:
        """Called when volunteer was assigned but did not attend."""
        self.events_attended   # don't increment
        self._update_reliability()
        logger.info("Volunteer %s no-show for event %s", self.volunteer_id, event_id)

    def record_assignment(self, accepted: bool) -> None:
        """Call when a volunteer is assigned and either accepts or declines."""
        self.events_assigned += 1
        if accepted:
            self.events_accepted += 1

    # ------------------------------------------------------------------
    # Reliability
    # ------------------------------------------------------------------

    def _update_reliability(self) -> None:
        if self.events_assigned == 0:
            self.reliability_score = 1.0
            return
        ratio = self.events_attended / self.events_assigned
        self.reliability_score = round(max(0.0, min(1.0, ratio)), 4)

    def is_reliable(self) -> bool:
        return self.reliability_score >= VOL_RELIABILITY_THRESHOLD


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ema(current: float, new_value: float, alpha: float) -> float:
    """Exponential moving average."""
    return round(alpha * new_value + (1 - alpha) * current, 6)


def _log_scale_activity(n_events: int) -> float:
    """
    Maps completed event count to [0, 1].
    Saturates gradually: 1 event → 0.08, 10 → 0.46, 50 → 0.81, 100 → 0.97
    """
    if n_events <= 0:
        return 0.0
    return round(min(math.log(n_events + 1) / math.log(101), 1.0), 4)
