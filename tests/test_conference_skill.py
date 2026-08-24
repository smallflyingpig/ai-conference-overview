from __future__ import annotations

import re
from pathlib import Path

import yaml

SKILL_ROOT = Path(".agents/skills/analyzing-conference-trends")


def _read(relative_path: str) -> str:
    return (SKILL_ROOT / relative_path).read_text(encoding="utf-8")


def _frontmatter(markdown: str) -> dict[str, object]:
    _, raw, _ = markdown.split("---", maxsplit=2)
    loaded = yaml.safe_load(raw)
    assert isinstance(loaded, dict)
    return loaded


def test_skill_is_discoverable_for_supported_conference_analysis() -> None:
    skill = _read("SKILL.md")
    metadata = _frontmatter(skill)

    assert metadata["name"] == "analyzing-conference-trends"
    description = str(metadata["description"])
    assert description.startswith("Use when ")
    for venue in ("ACL", "EMNLP", "ICLR", "ICML", "NeurIPS", "CVPR", "ICCV", "ECCV"):
        assert venue in description

    interface = yaml.safe_load(_read("agents/openai.yaml"))["interface"]
    assert interface["default_prompt"].startswith("Use $analyzing-conference-trends ")


def test_entrypoint_routes_cli_and_conditional_references() -> None:
    skill = _read("SKILL.md")

    assert "conference-trends" in skill
    assert "export-classification" in skill
    assert "analyze" in skill
    assert "build-site" in skill
    for reference in (
        "evidence-policy.md",
        "source-routing.md",
        "taxonomy-guide.md",
        "report-contract.md",
    ):
        assert f"references/{reference}" in skill


def test_policy_keeps_distribution_trend_and_cross_venue_claims_bounded() -> None:
    policy = _read("references/evidence-policy.md").lower()

    assert re.search(r"one-year.+(?:distribution|snapshot|hotspot)", policy)
    assert "three consecutive years" in policy
    assert re.search(r"raw (?:paper )?counts?.+not.+(?:interest|trend)", policy)
    assert "topic share" in policy
    assert "venue enrichment" in policy


def test_award_taxonomy_and_publication_gates_are_explicit() -> None:
    sources = _read("references/source-routing.md").lower()
    taxonomy = _read("references/taxonomy-guide.md").lower()
    report = _read("references/report-contract.md").lower()

    assert "not_announced" in sources
    assert "not_verified" in sources
    assert "personal social-media" in sources
    assert "exactly one primary" in taxonomy
    assert "90%" in taxonomy
    assert "80%" in taxonomy
    assert "publication" in report
    assert "last publishable" in report
    for evidence_type in (
        "official_metadata",
        "paper_reported",
        "cross_paper_synthesis",
        "inference",
    ):
        assert evidence_type in _read("references/evidence-policy.md")
