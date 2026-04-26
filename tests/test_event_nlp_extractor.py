from __future__ import annotations

import pytest

from backend.nlp.event_nlp_extractor import EventNLPExtractor


def test_extract_empty_texts_returns_defaults() -> None:
    extractor = EventNLPExtractor(use_gcp_nl=False)
    result = extractor.extract(["", "   "])

    assert result.affected_population is None
    assert result.extraction_method == "regex"


def test_extract_regex_parses_population_deaths_area_and_category() -> None:
    extractor = EventNLPExtractor(use_gcp_nl=False)
    text = (
        "Flood in Assam affected 1,200 people across 25 km2. "
        "At least 12 deaths reported and 35 cases confirmed. "
        "Urgent evacuation required."
    )

    result = extractor.extract([text])

    assert result.affected_population == 1200
    assert result.death_count == 12
    assert result.case_count == 35
    assert result.area_km2 == 25.0
    assert result.urgency_level == "high"
    assert result.suggested_category is not None


def test_extract_falls_back_to_regex_when_gcp_path_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    extractor = EventNLPExtractor(use_gcp_nl=False)
    extractor._nl_client = object()

    def fail(_text: str):
        raise RuntimeError("gcp down")

    monkeypatch.setattr(extractor, "_extract_gcp", fail)

    result = extractor.extract(["Annual workshop had 15 cases in one district."])

    assert result.extraction_method == "regex"
    assert result.urgency_level in {"medium", "high"}
