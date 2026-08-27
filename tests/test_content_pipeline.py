import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from conference_overview.chinese_content import (
    AwardDeepReadZh,
    AwardQuickReadZh,
    ChineseContentBundle,
    ContentPublicationBlocked,
    PaperSummaryZh,
    paper_route_key,
)
from conference_overview.content_pipeline import (
    OfficialPdfSource,
    export_chinese_content_sources,
    extract_official_pdf_source,
    load_authored_content,
    resolve_current_chinese_content,
    write_chinese_content_bundle,
)
from conference_overview.models import PaperRecord, RecordStatus, SourceRef

_ABSTRACT = "Official abstract without numbers."
_ABSTRACT_SHA256 = "01c8e4f38e1b92444f0f93f96a27a950e4cc0eb3d414aee7072afae974a693f6"
_LONG_SUMMARY = (
    "这项研究围绕语言模型的稳定学习展开，先分析现有方法在复杂输入下容易出现的偏差，"
    "再提出结合结构信息与动态选择机制的新方法。实验覆盖多个公开任务，并与常用基线进行比较。"
    "结果显示，该方法在主要设置下表现更稳定，同时减少了无效计算。作者也指出，当前实验集中在"
    "有限的数据和模型规模上，能否推广到其他语言与更大系统仍需继续研究。论文没有进一步报告真实部署环境中的表现。"
)


def paper(index: int, *, abstract: str | None = _ABSTRACT) -> PaperRecord:
    paper_id = f"acl:2026.acl-long.{index}"
    return PaperRecord(
        paper_id=paper_id,
        title=f"Paper {index}",
        normalized_title=f"paper {index}",
        authors=["A. Author"],
        venue="ACL",
        year=2026,
        track="long",
        landing_url=f"https://aclanthology.org/2026.acl-long.{index}/",
        source=SourceRef(
            name="ACL Anthology",
            url="https://aclanthology.org/volumes/2026.acl-long/",
            retrieved_at=datetime(2026, 8, 24, tzinfo=UTC),
            sha256="a" * 64,
        ),
        status=RecordStatus.COMPLETE,
        abstract=abstract,
        pdf_url=f"https://aclanthology.org/2026.acl-long.{index}.pdf",
    )


def summary(index: int) -> PaperSummaryZh:
    paper_id = f"acl:2026.acl-long.{index}"
    return PaperSummaryZh(
        schema_version="paper-summary-zh-v1",
        paper_id=paper_id,
        route_key=paper_route_key(paper_id),
        venue="ACL",
        year=2026,
        track="long",
        source_title=f"Paper {index}",
        source_abstract_sha256=_ABSTRACT_SHA256,
        one_sentence="论文提出一种更稳定的语言模型学习方法。",
        summary_zh=_LONG_SUMMARY,
        research_problem="现有方法在复杂输入下容易出现不稳定表现。",
        core_method="方法结合结构信息与动态选择机制。",
        main_findings="论文报告该方法在多个公开任务上表现更稳定。",
        scope_and_limitations="实验范围限于论文使用的数据和模型规模。",
        content_method="title-abstract-grounded-summary-v1",
    )


def award(index: int) -> AwardDeepReadZh:
    return AwardDeepReadZh(
        schema_version="award-deep-read-zh-v1",
        paper_id=f"acl:2026.acl-long.{index}",
        source_pdf_sha256="c" * 64,
        quick_read=AwardQuickReadZh(
            research_problem="论文研究模型在复杂任务中的稳定表现。",
            core_method="作者提出分阶段分析与动态调整方法。",
            main_finding="实验显示该方法改善了主要任务表现。",
        ),
        abstract_zh="论文系统研究模型在复杂任务中的稳定性，并提出分阶段分析方法。",
        background=("现有方法难以区分不同错误来源。",),
        method_walkthrough=("先分析输入，再动态选择处理步骤。",),
        why_it_matters=("这项工作提供了更细致的分析方法。",),
        limitations=("实验只覆盖论文报告的数据范围。",),
        research_implications=("后续研究可以继续检查不同任务中的稳定性。",),
    )


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def complete_pdf_fixture() -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        (
            b"<< /Length 49 >>\nstream\n"
            b"BT /F1 12 Tf 72 720 Td (paper body marker) Tj ET\n"
            b"endstream"
        ),
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode())
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode()
    )
    return bytes(output)


def test_export_partitions_non_awards_by_numeric_suffix(tmp_path: Path) -> None:
    paths = export_chinese_content_sources(
        papers=[paper(index) for index in range(1, 6)],
        award_ids=set(),
        award_deep_reads={},
        award_pdf_provenance={},
        output_dir=tmp_path,
        shard_count=4,
    )

    ordinary = [path for path in paths if "paper-summary-source" in path.name]
    assert [path.name for path in ordinary] == [
        "paper-summary-source-00.jsonl",
        "paper-summary-source-01.jsonl",
        "paper-summary-source-02.jsonl",
        "paper-summary-source-03.jsonl",
    ]
    assert [row["paper_id"] for row in read_jsonl(ordinary[1])] == [
        "acl:2026.acl-long.1",
        "acl:2026.acl-long.5",
    ]
    exported_ids = {
        str(row["paper_id"])
        for path in ordinary
        for row in read_jsonl(path)
    }
    assert exported_ids == {
        "acl:2026.acl-long.1",
        "acl:2026.acl-long.2",
        "acl:2026.acl-long.3",
        "acl:2026.acl-long.4",
        "acl:2026.acl-long.5",
    }


def test_export_supports_stable_pmlr_paper_ids(tmp_path: Path) -> None:
    papers = [
        paper(index).model_copy(
            update={
                "paper_id": f"pmlr:v267:paper{index}a",
                "venue": "ICML",
                "year": 2025,
                "track": "main",
            }
        )
        for index in range(1, 4)
    ]

    paths = export_chinese_content_sources(
        papers=papers,
        award_ids=set(),
        award_deep_reads={},
        award_pdf_provenance={},
        output_dir=tmp_path,
        shard_count=2,
    )

    assert {
        row["paper_id"]
        for path in paths
        if "paper-summary-source" in path.name
        for row in read_jsonl(path)
    } == {paper.paper_id for paper in papers}


def test_export_keeps_awards_out_of_ordinary_shards(tmp_path: Path) -> None:
    deep_read = award(2)
    paths = export_chinese_content_sources(
        papers=[paper(1), paper(2)],
        award_ids={deep_read.paper_id},
        award_deep_reads={deep_read.paper_id: {"method_summary": "Official method."}},
        award_pdf_provenance={
            deep_read.paper_id: {
                "pdf_url": "https://aclanthology.org/2026.acl-long.2.pdf",
                "sha256": "c" * 64,
                "byte_size": 1234,
            }
        },
        output_dir=tmp_path,
        shard_count=2,
    )

    award_path = next(path for path in paths if path.name == "award-deep-read-source.jsonl")
    assert [row["paper_id"] for row in read_jsonl(award_path)] == [deep_read.paper_id]
    ordinary_ids = {
        row["paper_id"]
        for path in paths
        if "paper-summary-source" in path.name
        for row in read_jsonl(path)
    }
    assert deep_read.paper_id not in ordinary_ids


def test_export_uses_verified_pdf_text_when_web_abstract_is_missing(
    tmp_path: Path,
) -> None:
    source = OfficialPdfSource(
        byte_size=4321,
        sha256="d" * 64,
        text="Official PDF paper body marker.",
    )

    paths = export_chinese_content_sources(
        papers=[paper(1, abstract=None)],
        award_ids=set(),
        award_deep_reads={},
        award_pdf_provenance={},
        ordinary_pdf_sources={"acl:2026.acl-long.1": source},
        output_dir=tmp_path,
        shard_count=1,
    )

    row = read_jsonl(paths[0])[0]
    assert row["content_method"] == "official-pdf-grounded-summary-v1"
    assert row["source_pdf_sha256"] == "d" * 64
    assert row["source_text"] == "Official PDF paper body marker."


def test_extract_official_pdf_source_checks_completeness_and_reads_text() -> None:
    pdf = complete_pdf_fixture()

    source = extract_official_pdf_source(pdf, expected_length=len(pdf))

    assert source.byte_size == len(pdf)
    assert source.sha256 == hashlib.sha256(pdf).hexdigest()
    assert "paper body marker" in source.text


def test_extract_official_pdf_source_rejects_truncated_bytes() -> None:
    pdf = complete_pdf_fixture()

    with pytest.raises(ContentPublicationBlocked, match="truncated"):
        extract_official_pdf_source(pdf[:-6], expected_length=len(pdf))


def test_writer_publishes_three_files_and_atomic_pointer(tmp_path: Path) -> None:
    bundle = ChineseContentBundle(
        release_generation="generations/" + "a" * 64,
        papers_sha256="b" * 64,
        summaries=(summary(1),),
        award_deep_reads=(award(2),),
        ordinary_count=1,
        award_count=1,
        total_count=2,
    )

    generation = write_chinese_content_bundle(
        bundle, tmp_path, generated_at=datetime(2026, 8, 25, tzinfo=UTC)
    )

    assert sorted(path.name for path in generation.iterdir()) == [
        "award-deep-reads.zh.jsonl",
        "content-manifest.json",
        "paper-summaries.zh.jsonl",
    ]
    pointer = json.loads((tmp_path / "current.json").read_text())
    assert pointer["release_generation"] == "generations/" + "a" * 64
    assert pointer["papers_sha256"] == "b" * 64
    assert pointer["generation"] == f"generations/{generation.name}"
    assert set(pointer["artifact_sha256"]) == {
        "award-deep-reads.zh.jsonl",
        "content-manifest.json",
        "paper-summaries.zh.jsonl",
    }


def test_import_rejects_rehashed_but_stale_abstract_binding(tmp_path: Path) -> None:
    summary_path = tmp_path / "paper-summaries-00.zh.jsonl"
    stale = summary(1).model_copy(update={"source_abstract_sha256": "0" * 64})
    summary_path.write_text(json.dumps(stale.model_dump(mode="json")) + "\n")
    award_path = tmp_path / "award-deep-reads.zh.jsonl"
    award_path.write_text("")

    with pytest.raises(ContentPublicationBlocked, match="abstract SHA-256"):
        load_authored_content(
            summary_files=[summary_path],
            award_path=award_path,
            papers=[paper(1)],
            award_ids=set(),
            release_generation="generations/" + "a" * 64,
            papers_sha256="b" * 64,
            award_pdf_sha256={},
            award_source_text={},
            allow_incomplete=False,
        )


def test_incomplete_import_validates_selected_ids_without_publishing(
    tmp_path: Path,
) -> None:
    summary_path = tmp_path / "paper-summaries-00.zh.jsonl"
    summary_path.write_text(json.dumps(summary(1).model_dump(mode="json")) + "\n")
    award_path = tmp_path / "award-deep-reads.zh.jsonl"
    award_path.write_text("")

    draft = load_authored_content(
        summary_files=[summary_path],
        award_path=award_path,
        papers=[paper(1), paper(2)],
        award_ids=set(),
        release_generation="generations/" + "a" * 64,
        papers_sha256="b" * 64,
        award_pdf_sha256={},
        award_source_text={},
        allow_incomplete=True,
    )

    assert draft.total_count == 1
    assert not (tmp_path / "current.json").exists()


def test_writer_rejects_bundle_counts_that_disagree_with_records(tmp_path: Path) -> None:
    forged = ChineseContentBundle(
        release_generation="generations/" + "a" * 64,
        papers_sha256="b" * 64,
        summaries=(summary(1),),
        award_deep_reads=(award(2),),
        ordinary_count=2,
        award_count=1,
        total_count=3,
    )

    with pytest.raises(ContentPublicationBlocked, match="content counts"):
        write_chinese_content_bundle(
            forged, tmp_path, generated_at=datetime(2026, 8, 25, tzinfo=UTC)
        )


def test_resolver_rejects_artifact_changed_after_pointer_write(tmp_path: Path) -> None:
    bundle = ChineseContentBundle(
        release_generation="generations/" + "a" * 64,
        papers_sha256="b" * 64,
        summaries=(summary(1),),
        award_deep_reads=(award(2),),
        ordinary_count=1,
        award_count=1,
        total_count=2,
    )
    generation = write_chinese_content_bundle(
        bundle, tmp_path, generated_at=datetime(2026, 8, 25, tzinfo=UTC)
    )
    (generation / "paper-summaries.zh.jsonl").write_text("forged\n")

    with pytest.raises(ContentPublicationBlocked, match="hash mismatch"):
        resolve_current_chinese_content(tmp_path)


def test_repeated_write_of_same_bundle_is_byte_stable(tmp_path: Path) -> None:
    bundle = ChineseContentBundle(
        release_generation="generations/" + "a" * 64,
        papers_sha256="b" * 64,
        summaries=(summary(1),),
        award_deep_reads=(award(2),),
        ordinary_count=1,
        award_count=1,
        total_count=2,
    )
    generated_at = datetime(2026, 8, 25, tzinfo=UTC)

    first = write_chinese_content_bundle(bundle, tmp_path, generated_at=generated_at)
    first_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in first.iterdir()
    }
    second = write_chinese_content_bundle(bundle, tmp_path, generated_at=generated_at)

    assert second == first
    assert {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in second.iterdir()
    } == first_hashes
