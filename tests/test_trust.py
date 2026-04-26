from __future__ import annotations

import pytest

from backend.nlp.trust_scorer import NGOTrustScore, TrustScorer, VolunteerPointsLedger


def test_ngo_trust_apply_audit_updates_state() -> None:
	trust = NGOTrustScore(ngo_id="ngo-1")

	trust.apply_audit(star_rating=5.0, goal_met=True, attendance_ratio=0.9)

	assert trust.total_events_completed == 1
	assert 0.0 <= trust.composite_score <= 1.0
	assert trust.last_updated is not None


def test_ngo_trust_gate_blocks_low_score() -> None:
	trust = NGOTrustScore(ngo_id="ngo-2", composite_score=0.10)

	allowed, reason = trust.can_create_event()

	assert allowed is False
	assert "below the minimum threshold" in reason


def test_volunteer_points_and_reliability_flow() -> None:
	ledger = VolunteerPointsLedger(volunteer_id="vol-1")

	ledger.record_assignment(accepted=True)
	ledger.record_assignment(accepted=True)
	earned = ledger.record_attendance(
		event_id="evt-1",
		severity_band="CRITICAL",
		goal_met=True,
		skill_used=True,
		early_accept=True,
		ngo_star_rating=5.0,
	)
	ledger.record_no_show(event_id="evt-2")

	assert earned > 0
	assert ledger.total_points == earned
	assert ledger.reliability_score == 0.5
	assert ledger.is_reliable() is False


@pytest.mark.asyncio
async def test_trust_scorer_defaults_without_db() -> None:
	scorer = TrustScorer(db_client=None)

	trust = await scorer.get_ngo_trust("ngo-3")
	ledger = await scorer.get_volunteer_ledger("vol-3")

	assert trust.ngo_id == "ngo-3"
	assert ledger.volunteer_id == "vol-3"
