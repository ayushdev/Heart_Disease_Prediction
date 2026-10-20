import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("build_report", Path("scripts/build_report.py"))
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def test_missing_evidence_cannot_be_called_final():
    evidence = {
        "repository_url": "",
        "video_path": "",
        "video_url": "",
        "captures": [{"path": "does-not-exist.png"}],
        "checks": {"container": "does-not-exist.json"},
    }
    missing = report.missing_evidence(evidence)
    assert len(missing) == 4
    assert any("recording" in message for message in missing)


def test_final_report_blocks_missing_execution(monkeypatch):
    monkeypatch.setattr(
        report,
        "read_json",
        lambda path: {
            "repository_url": "",
            "video_path": "",
            "video_url": "",
            "captures": [],
            "checks": {},
        },
    )
    with pytest.raises(ValueError, match="Final report blocked"):
        report.build(final=True)


def test_narrative_covers_exactly_ten_pages():
    pages = report.read_json("docs/report_content.json")
    assert len(pages) == 10
    assert all(len(page["paragraphs"]) >= 4 for page in pages)
