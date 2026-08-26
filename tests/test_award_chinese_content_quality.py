import json
import re
from decimal import Decimal
from pathlib import Path

import yaml

_ROOT = Path(__file__).parents[1]
_AUTHORED = _ROOT / "data/content/acl/2026-long/authored/award-deep-reads.zh.jsonl"
_SOURCE = _ROOT / "data/content/acl/2026-long/source-batches/award-deep-read-source.jsonl"
_NUMBER = re.compile(r"(?<![A-Za-z0-9_])[+-]?\d+(?:[.,]\d+)*")


def _rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _numbers(text: str) -> set[Decimal]:
    values: set[Decimal] = set()
    for token in _NUMBER.findall(text):
        try:
            values.add(Decimal(token.replace(",", "")))
        except ArithmeticError:
            continue
    return values


def test_all_award_chinese_readings_are_compact_but_self_contained() -> None:
    authored = {row["paper_id"]: row for row in _rows(_AUTHORED)}
    sources = {row["paper_id"]: row for row in _rows(_SOURCE)}

    assert len(authored) == len(sources) == 30
    assert authored.keys() == sources.keys()

    for paper_id, reading in authored.items():
        quick_read = reading["quick_read"]
        sections = [
            *quick_read.values(),
            reading["abstract_zh"],
            *reading["background"],
            *reading["method_walkthrough"],
            *reading["why_it_matters"],
            *reading["limitations"],
            *reading["research_implications"],
        ]
        public_text = "".join(sections)
        result_text = "".join(reading["why_it_matters"])
        source_values = {
            Decimal(str(claim["value"]))
            for claim in sources[paper_id]["deep_read"]["result_claims"]
        }

        assert 700 <= len(public_text) <= 900, paper_id
        assert len(reading["why_it_matters"]) >= 2, paper_id
        assert _numbers(result_text).intersection(source_values), paper_id


def test_icml_award_readings_cover_all_papers_and_preserve_result_boundaries() -> None:
    authored_path = (
        _ROOT
        / "data/content/icml/2025-main/authored/award-deep-reads.zh.jsonl"
    )
    deep_read_path = _ROOT / "data/awards/icml/2025-main-deep-reads.yaml"
    authored = {row["paper_id"]: row for row in _rows(authored_path)}
    deep_reads = {
        row["paper_id"]: row
        for row in yaml.safe_load(deep_read_path.read_text())["deep_reads"]
    }

    assert len(authored) == len(deep_reads) == 8
    assert authored.keys() == deep_reads.keys()
    for paper_id, reading in authored.items():
        sections = [
            *reading["quick_read"].values(),
            reading["abstract_zh"],
            *reading["background"],
            *reading["method_walkthrough"],
            *reading["why_it_matters"],
            *reading["limitations"],
            *reading["research_implications"],
        ]
        public_text = "".join(sections)
        deep_read = deep_reads[paper_id]
        assert 450 <= len(public_text) <= 900, paper_id
        assert len(reading["why_it_matters"]) >= 2, paper_id
        if deep_read["result_claims"]:
            source_values = {
                Decimal(str(claim["value"]))
                for claim in deep_read["result_claims"]
            }
            assert _numbers(public_text).intersection(source_values), paper_id
        else:
            assert deep_read["no_numeric_result"]["paper_type"] == "position_paper"
            assert "没有" in reading["quick_read"]["main_finding"]
