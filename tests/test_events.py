from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.ingestion import ingestor_to_severity as bridge
from backend.nlp.severity_engine import SeverityBand, SeverityResult


class FakeEngine:
	def __init__(self):
		self.last_event = None

	def score(self, event):
		self.last_event = event
		return SeverityResult(
			score=0.81,
			band=SeverityBand.CRITICAL,
			map_color="#E53E3E",
			breakdown={"final_score": 0.81},
			top_evidence=["Urgent rescue required."],
			warnings=[],
		)


def test_ingest_and_score_builds_event_and_marker(monkeypatch: pytest.MonkeyPatch) -> None:
	def fake_load_document(filepath: str):
		if filepath.endswith("bad.pdf"):
			raise RuntimeError("cannot parse")
		return [
			{"content": "A", "metadata": {"page": 1, "source": "good.txt", "filetype": "txt"}},
			{"content": "B", "metadata": {"page": 2, "source": "good.txt", "filetype": "txt"}},
		]

	def fake_chunk_documents(raw_docs, chunk_size: int, chunk_overlap: int):
		assert chunk_size == 100
		assert chunk_overlap == 10
		return [
			{"content": "hello", "metadata": {"page": 1}},
			{"content": "world", "metadata": {"page": 1}},
			{"content": "again", "metadata": {"page": 2}},
		]

	def fake_marker(event, result):
		return {"ok": True, "band": result.band.value, "texts": event.document_texts}

	monkeypatch.setattr(bridge, "load_document", fake_load_document)
	monkeypatch.setattr(bridge, "chunk_documents", fake_chunk_documents)
	monkeypatch.setattr(bridge, "build_map_marker", fake_marker)

	engine = FakeEngine()
	result, marker = bridge.ingest_and_score(
		filepaths=["good.txt", "bad.pdf"],
		category="food",
		engine=engine,
		location_name="Test City",
		affected_population=500,
		reported_at=datetime.now(timezone.utc),
		chunk_size=100,
		chunk_overlap=10,
	)

	assert result.band == SeverityBand.CRITICAL
	assert marker["ok"] is True
	assert engine.last_event is not None
	assert engine.last_event.num_supporting_docs == 2
	assert engine.last_event.document_texts == ["hello world", "again"]
