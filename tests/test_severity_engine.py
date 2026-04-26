from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from backend.nlp import severity_engine as se


class DummyEmbedder:
	def embed(self, texts: list[str]) -> np.ndarray:
		vectors = []
		for t in texts:
			tl = t.lower()
			if "urgent" in tl or "flood" in tl or "emergency" in tl:
				vectors.append([1.0, 0.0])
			elif "routine" in tl or "annual" in tl:
				vectors.append([0.0, 1.0])
			else:
				vectors.append([0.5, 0.5])
		return np.array(vectors, dtype=np.float32)


def test_recency_score_unknown_date_has_warning() -> None:
	mult, warning = se._recency_score(None)
	assert mult == 0.75
	assert warning is not None


def test_area_scale_factor_bounds() -> None:
	assert 0.5 <= se._area_scale_factor(1, None) <= 1.5
	assert 0.5 <= se._area_scale_factor(1_000_000_000, None) <= 1.5
	assert se._area_scale_factor(None, None) == 1.0


def test_build_map_marker_contains_expected_properties() -> None:
	event = se.EventInput(category="food", location_name="Bengaluru", affected_population=1000)
	result = se.SeverityResult(
		score=0.42,
		band=se.SeverityBand.MODERATE,
		map_color="#DD6B20",
		breakdown={"final_score": 0.42},
		top_evidence=["Urgent food shortage."],
		warnings=[],
	)

	marker = se.build_map_marker(event, result)

	assert marker["type"] == "Feature"
	assert marker["properties"]["severity_band"] == "MODERATE"
	assert marker["properties"]["radius_m"] >= 500


def test_score_with_dummy_embedder(monkeypatch) -> None:
	monkeypatch.setattr(se.SeverityEngine, "_init_embedder", lambda self, use_vertex: DummyEmbedder())

	engine = se.SeverityEngine(use_vertex=False, translate_non_english=False)
	event = se.EventInput(
		category="disaster_relief",
		document_texts=["Urgent flood emergency affecting 2000 people."],
		affected_population=2000,
		reported_at=datetime.now(timezone.utc),
		num_supporting_docs=2,
	)

	result = engine.score(event)

	assert 0.0 <= result.score <= 1.0
	assert result.band in {se.SeverityBand.LOW, se.SeverityBand.MODERATE, se.SeverityBand.CRITICAL}
	assert "final_score" in result.breakdown


def test_score_no_text_adds_warning(monkeypatch) -> None:
	monkeypatch.setattr(se.SeverityEngine, "_init_embedder", lambda self, use_vertex: DummyEmbedder())
	engine = se.SeverityEngine(use_vertex=False, translate_non_english=False)

	event = se.EventInput(
		category="education",
		document_texts=[],
		manager_context="",
		reported_at=datetime.now(timezone.utc) - timedelta(days=400),
	)
	result = engine.score(event)

	assert any("No document text provided" in w for w in result.warnings)


def test_score_batch_preserves_order(monkeypatch) -> None:
	monkeypatch.setattr(se.SeverityEngine, "_init_embedder", lambda self, use_vertex: DummyEmbedder())
	engine = se.SeverityEngine(use_vertex=False, translate_non_english=False)

	events = [
		se.EventInput(category="food", document_texts=["urgent food need"]),
		se.EventInput(category="education", document_texts=["annual routine class"]),
	]
	results = engine.score_batch(events)

	assert len(results) == 2
	assert all(isinstance(r, se.SeverityResult) for r in results)
