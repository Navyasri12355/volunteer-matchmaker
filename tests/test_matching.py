from __future__ import annotations

from backend.nlp.trust_scorer import VOL_RELIABILITY_THRESHOLD, VolunteerPointsLedger


def test_matching_reliability_threshold_signal() -> None:
	ledger = VolunteerPointsLedger(volunteer_id="vol-match")

	for _ in range(5):
		ledger.record_assignment(accepted=True)

	for i in range(2):
		ledger.record_attendance(
			event_id=f"evt-{i}",
			severity_band="LOW",
			goal_met=False,
			skill_used=False,
			early_accept=False,
			ngo_star_rating=3.0,
		)

	ledger.record_no_show("evt-3")

	assert ledger.reliability_score < VOL_RELIABILITY_THRESHOLD
	assert ledger.is_reliable() is False


def test_matching_reliability_when_no_assignments_is_optimistic() -> None:
	ledger = VolunteerPointsLedger(volunteer_id="vol-new")
	assert ledger.reliability_score == 1.0
	assert ledger.is_reliable() is True
