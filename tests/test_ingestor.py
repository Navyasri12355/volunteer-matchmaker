from __future__ import annotations

from pathlib import Path

import pytest

from backend.ingestion import ingestor


def test_load_document_txt(tmp_path: Path) -> None:
	fp = tmp_path / "note.txt"
	fp.write_text("hello world", encoding="utf-8")

	docs = ingestor.load_document(str(fp))

	assert len(docs) == 1
	assert docs[0]["content"] == "hello world"
	assert docs[0]["metadata"]["filetype"] == "txt"
	assert docs[0]["metadata"]["source"] == "note.txt"


def test_load_document_unsupported_type_raises(tmp_path: Path) -> None:
	fp = tmp_path / "bad.bin"
	fp.write_bytes(b"123")

	with pytest.raises(ValueError, match="Unsupported file type"):
		ingestor.load_document(str(fp))


def test_chunk_documents_adds_chunk_index_and_preserves_metadata() -> None:
	docs = [
		{
			"content": "A " * 400,
			"metadata": {"source": "mock.txt", "page": 1, "filetype": "txt"},
		}
	]

	chunks = ingestor.chunk_documents(docs, chunk_size=80, chunk_overlap=0)

	assert len(chunks) > 1
	assert all("chunk_index" in c["metadata"] for c in chunks)
	assert all(c["metadata"]["source"] == "mock.txt" for c in chunks)


def test_ingest_directory_processes_supported_files_and_continues_on_error(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	def fake_walk(_directory: str):
		yield "root", [], ["a.txt", "b.pdf", "skip.jpg"]

	calls: list[str] = []

	def fake_load_document(filepath: str):
		calls.append(filepath)
		if filepath.endswith("b.pdf"):
			raise RuntimeError("broken")
		return [{"content": "x", "metadata": {"source": "a.txt", "page": 1, "filetype": "txt"}}]

	def fake_chunk_documents(docs, chunk_size: int, chunk_overlap: int):
		assert chunk_size == 123
		assert chunk_overlap == 7
		return [{"content": docs[0]["content"], "metadata": {**docs[0]["metadata"], "chunk_index": 0}}]

	monkeypatch.setattr(ingestor.os, "walk", fake_walk)
	monkeypatch.setattr(ingestor, "load_document", fake_load_document)
	monkeypatch.setattr(ingestor, "chunk_documents", fake_chunk_documents)

	out = ingestor.ingest_directory("irrelevant", chunk_size=123, chunk_overlap=7)

	assert len(out) == 1
	assert out[0]["metadata"]["chunk_index"] == 0
	assert any(path.endswith("a.txt") for path in calls)
	assert any(path.endswith("b.pdf") for path in calls)
