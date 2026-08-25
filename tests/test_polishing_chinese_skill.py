from __future__ import annotations

from pathlib import Path

import yaml

SKILL_ROOT = Path(".agents/skills/polishing-chinese-writing")


def _read(relative_path: str) -> str:
    return (SKILL_ROOT / relative_path).read_text(encoding="utf-8")


def _frontmatter(markdown: str) -> dict[str, object]:
    _, raw, _ = markdown.split("---", maxsplit=2)
    loaded = yaml.safe_load(raw)
    assert isinstance(loaded, dict)
    return loaded


def test_skill_is_discoverable_for_awkward_chinese_copy() -> None:
    skill = _read("SKILL.md")
    metadata = _frontmatter(skill)

    assert metadata["name"] == "polishing-chinese-writing"
    description = str(metadata["description"])
    assert description.startswith("Use when ")
    for trigger in ("Chinese", "technical", "translation", "website"):
        assert trigger.lower() in description.lower()

    interface = yaml.safe_load(_read("agents/openai.yaml"))["interface"]
    assert interface["default_prompt"].startswith(
        "Use $polishing-chinese-writing "
    )


def test_skill_requires_semantic_rewriting_and_fact_preservation() -> None:
    skill = _read("SKILL.md")

    for phrase in (
        "先理解，再改写",
        "不能机械替换",
        "事实边界",
        "数字",
        "专有名词",
        "读出声",
    ):
        assert phrase in skill


def test_reference_covers_technicalese_and_contextual_rewrites() -> None:
    reference = _read("references/rewrite-guide.md")

    for term in (
        "门禁",
        "约束",
        "核验",
        "结论",
        "证据",
        "lineage",
        "audit",
        "withheld",
    ):
        assert term in reference
    assert "不要整表查找替换" in reference
    assert "根据句子实际表达的意思" in reference


def test_skill_defines_a_concise_delivery_contract() -> None:
    skill = _read("SKILL.md")

    assert "默认只交付改写后的正文" in skill
    assert "保留原文结构" in skill
    assert "术语保留" in skill
    assert "自检" in skill
    assert "用户点名" in skill
    assert "逐项搜索" in skill
