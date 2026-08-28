"""Venue-neutral collection and validation dispatch."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx

from conference_overview.adapters.icml import (
    FetchedIcmlSource,
    IcmlRawCorpus,
    fetch_icml_sources,
    parse_icml_sources,
)
from conference_overview.adapters.pmlr import (
    FinalSourceStatus,
    fetch_final_source,
    parse_pmlr_citeproc,
    parse_pmlr_volume,
    pmlr_volume_paper_ids,
    reconcile_pmlr_records,
)
from conference_overview.classification import assert_theme_publishable, load_taxonomy
from conference_overview.fetch import fetch_bytes
from conference_overview.metrics import topic_share
from conference_overview.models import (
    AnalysisAvailability,
    EvidenceClaim,
    EvidenceType,
    PaperRecord,
    PublicationContext,
    RecordStatus,
    SourceRef,
    VenueRequest,
)
from conference_overview.pipeline import (
    CollectionResult,
    UnsupportedPipelineRoute,
    _atomic_write,
    _current_assignment_state,
    _json_bytes,
    _jsonl_bytes,
    _load_award_deep_reads,
    _load_award_records,
    _load_low_confidence_reviews,
    _load_theme_audits,
    analyze_acl_scope,
    collect_acl_scope,
    rebuild_acl_scope_from_snapshots,
    validate_acl_scope,
)
from conference_overview.pipeline import (
    load_scope_records as load_acl_scope_records,
)
from conference_overview.reports import (
    ReleaseBundle,
    resolve_current_release,
)
from conference_overview.reports import (
    write_release as publish_release,
)
from conference_overview.scope import ScopePaths
from conference_overview.storage import store_snapshot
from conference_overview.synthesis import build_single_year_advances
from conference_overview.validate import (
    PublicationBlocked,
    ValidationReport,
    assert_publishable,
    validate_records,
)


def collect_scope(
    request: VenueRequest,
    root: Path,
    *,
    client: httpx.Client | None = None,
) -> CollectionResult:
    if request.adapter == "icml_virtual":
        return collect_icml_scope(request, root, client=client)
    if request.adapter == "pmlr":
        return collect_pmlr_scope(request, root, client=client)
    if request.adapter == "acl_anthology":
        return collect_acl_scope(request, root, client=client)
    raise UnsupportedPipelineRoute(
        f"unsupported pipeline route: {request.venue}/{request.year}/{request.track or '-'}"
    )


def _persist_source(fetched: FetchedIcmlSource, snapshots: Path) -> FetchedIcmlSource:
    source = store_snapshot(fetched.data, fetched.url, snapshots).model_copy(
        update={"name": fetched.source.name}
    )
    return FetchedIcmlSource(
        kind=fetched.kind,
        url=fetched.url,
        data=fetched.data,
        source=source,
    )


def collect_icml_scope(
    request: VenueRequest,
    root: Path,
    *,
    client: httpx.Client | None = None,
) -> CollectionResult:
    paths = ScopePaths.for_request(Path(root), request)
    owns_client = client is None
    active_client = client or httpx.Client()
    try:
        fetched = fetch_icml_sources(request, active_client)
    finally:
        if owns_client:
            active_client.close()
    corpus = IcmlRawCorpus(
        event_pages=tuple(
            _persist_source(source, paths.snapshots) for source in fetched.event_pages
        ),
        abstracts=_persist_source(fetched.abstracts, paths.snapshots),
        openreview_pages=tuple(
            _persist_source(source, paths.snapshots)
            for source in fetched.openreview_pages
        ),
    )
    return _normalize_icml_corpus(request, paths, corpus)


def _fetched_pmlr(kind: str, url: str, data: bytes) -> FetchedIcmlSource:
    return FetchedIcmlSource(
        kind=kind,
        url=url,
        data=data,
        source=SourceRef(
            name=f"PMLR Volume 267 {kind}",
            url=url,
            retrieved_at=datetime.now(UTC),
            sha256=hashlib.sha256(data).hexdigest(),
        ),
    )


def collect_pmlr_scope(
    request: VenueRequest,
    root: Path,
    *,
    client: httpx.Client | None = None,
) -> CollectionResult:
    if request.track != "main" or set(request.source_urls) != {"volume", "metadata"}:
        raise ValueError("PMLR request does not declare the exact final source set")
    paths = ScopePaths.for_request(Path(root), request)
    owns_client = client is None
    active_client = client or httpx.Client()
    try:
        sources = tuple(
            _persist_source(
                _fetched_pmlr(
                    kind,
                    str(request.source_urls[kind]),
                    fetch_bytes(str(request.source_urls[kind]), active_client),
                ),
                paths.snapshots,
            )
            for kind in ("volume", "metadata")
        )
    finally:
        if owns_client:
            active_client.close()
    return _normalize_pmlr_corpus(request, paths, sources)


def _normalize_pmlr_corpus(
    request: VenueRequest,
    paths: ScopePaths,
    sources: tuple[FetchedIcmlSource, ...],
) -> CollectionResult:
    source_by_kind = {source.kind: source for source in sources}
    if set(source_by_kind) != {"volume", "metadata"} or len(sources) != 2:
        raise ValueError("PMLR source set is incomplete")
    records = parse_pmlr_citeproc(
        source_by_kind["metadata"].data,
        request,
        source_by_kind["metadata"].source,
    )
    volume_ids = pmlr_volume_paper_ids(source_by_kind["volume"].data, request)
    record_ids = tuple(
        sorted(str(record.native_metadata["pmlr_id"]) for record in records)
    )
    if volume_ids != record_ids:
        raise ValueError("PMLR volume page and citeproc metadata paper IDs disagree")
    validation = validate_records(records, (), expected_included=len(records))
    normalized_bytes = _jsonl_bytes(
        [record.model_dump(mode="json") for record in records]
    )
    _atomic_write(paths.normalized, normalized_bytes)
    manifest = {
        "schema_version": "conference-collection-manifest-v1",
        "scope": {
            "venue": request.venue,
            "year": request.year,
            "track": request.track,
        },
        "publication_status": request.publication_status,
        "counts": {
            "discovered": len(records),
            "duplicate_candidates": validation.duplicate_candidate_count,
            "excluded": 0,
            "included": len(records),
            "unresolved": 0,
            "presentation_rows": 0,
        },
        "excluded_ids": [],
        "unresolved_ids": [],
        "normalized": {
            "path": paths.normalized.relative_to(paths.manifest.parents[3]).as_posix(),
            "record_set_sha256": validation.record_set_sha256,
            "sha256": hashlib.sha256(normalized_bytes).hexdigest(),
        },
        "sources": [
            _source_manifest(source, paths=paths, page_index=index)
            for index, source in enumerate(sources)
        ],
    }
    _atomic_write(paths.manifest, _json_bytes(manifest))
    return CollectionResult(paths.manifest, paths.normalized, validation)


def _source_manifest(
    source: FetchedIcmlSource,
    *,
    paths: ScopePaths,
    page_index: int,
) -> dict[str, object]:
    sha256 = source.source.sha256
    if sha256 is None:
        raise ValueError("persisted ICML source has no SHA-256")
    snapshot = paths.snapshots / "raw" / f"{sha256}.bin"
    return {
        "byte_size": len(source.data),
        "kind": source.kind,
        "name": source.source.name,
        "page_index": page_index,
        "retrieved_at": source.source.model_dump(mode="json")["retrieved_at"],
        "sha256": sha256,
        "snapshot_path": snapshot.relative_to(paths.manifest.parents[3]).as_posix(),
        "url": source.url,
    }


def _normalize_icml_corpus(
    request: VenueRequest,
    paths: ScopePaths,
    corpus: IcmlRawCorpus,
) -> CollectionResult:
    parsed = parse_icml_sources(corpus, request)
    validation = validate_records(
        [*parsed.included, *parsed.unresolved],
        parsed.excluded,
        expected_included=len(parsed.included) + len(parsed.unresolved),
    )
    records = sorted(
        (*parsed.excluded, *parsed.included, *parsed.unresolved),
        key=lambda record: record.paper_id,
    )
    normalized_bytes = _jsonl_bytes(
        [record.model_dump(mode="json") for record in records]
    )
    _atomic_write(paths.normalized, normalized_bytes)
    ordered_sources = [
        *corpus.event_pages,
        corpus.abstracts,
        *corpus.openreview_pages,
    ]
    manifest = {
        "schema_version": "conference-collection-manifest-v1",
        "scope": {
            "venue": request.venue,
            "year": request.year,
            "track": request.track,
        },
        "publication_status": request.publication_status,
        "counts": {
            "discovered": len(records),
            "duplicate_candidates": validation.duplicate_candidate_count,
            "excluded": len(parsed.excluded),
            "included": len(parsed.included),
            "unresolved": len(parsed.unresolved),
            "presentation_rows": parsed.presentation_row_count,
        },
        "excluded_ids": sorted(record.paper_id for record in parsed.excluded),
        "unresolved_ids": sorted(record.paper_id for record in parsed.unresolved),
        "normalized": {
            "path": paths.normalized.relative_to(paths.manifest.parents[3]).as_posix(),
            "record_set_sha256": validation.record_set_sha256,
            "sha256": hashlib.sha256(normalized_bytes).hexdigest(),
        },
        "sources": [
            _source_manifest(source, paths=paths, page_index=index)
            for index, source in enumerate(ordered_sources)
        ],
    }
    _atomic_write(paths.manifest, _json_bytes(manifest))
    return CollectionResult(paths.manifest, paths.normalized, validation)


def _load_icml_manifest(
    request: VenueRequest, root: Path
) -> tuple[ScopePaths, dict[str, object]]:
    paths = ScopePaths.for_request(Path(root), request)
    try:
        manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid collection manifest: {paths.manifest}") from exc
    expected_scope = {
        "venue": request.venue,
        "year": request.year,
        "track": request.track,
    }
    if manifest.get("schema_version") != "conference-collection-manifest-v1":
        raise ValueError("collection manifest schema is unsupported")
    if manifest.get("scope") != expected_scope:
        raise ValueError("collection manifest scope does not match the requested route")
    if manifest.get("publication_status") != request.publication_status:
        raise ValueError("collection manifest publication status differs from registry")
    return paths, manifest


def _load_manifest_sources(
    request: VenueRequest, paths: ScopePaths, manifest: Mapping[str, object]
) -> list[FetchedIcmlSource]:
    raw_sources = manifest.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ValueError("collection manifest has no source snapshots")
    loaded: list[FetchedIcmlSource] = []
    repository_root = paths.manifest.parents[3].resolve()
    for expected_index, raw in enumerate(raw_sources):
        if not isinstance(raw, Mapping) or raw.get("page_index") != expected_index:
            raise ValueError("collection source page order is invalid")
        relative = Path(str(raw.get("snapshot_path")))
        if relative.is_absolute():
            raise ValueError("snapshot path must be repository-relative")
        snapshot = (repository_root / relative).resolve()
        try:
            snapshot.relative_to(repository_root)
        except ValueError as exc:
            raise ValueError("snapshot path leaves repository root") from exc
        if not snapshot.is_file():
            raise ValueError("snapshot is missing or not a regular file")
        data = snapshot.read_bytes()
        if len(data) != raw.get("byte_size") or hashlib.sha256(
            data
        ).hexdigest() != raw.get("sha256"):
            raise ValueError("immutable source snapshot disagrees with its manifest")
        loaded.append(
            FetchedIcmlSource(
                kind=str(raw.get("kind")),
                url=str(raw.get("url")),
                data=data,
                source=SourceRef(
                    name=str(raw.get("name")),
                    url=str(raw.get("url")),
                    retrieved_at=raw.get("retrieved_at"),
                    sha256=str(raw.get("sha256")),
                ),
            )
        )
    if request.adapter == "pmlr":
        expected = [
            ("volume", str(request.source_urls["volume"])),
            ("metadata", str(request.source_urls["metadata"])),
        ]
        if [(source.kind, source.url) for source in loaded] != expected:
            raise ValueError("PMLR collection source set differs from registry")
        return loaded
    if loaded[0].url != str(request.source_urls["events"]):
        raise ValueError("first event source URL differs from registry")
    event_pages = [source for source in loaded if source.kind == "events"]
    abstracts = [source for source in loaded if source.kind == "abstracts"]
    openreview = [source for source in loaded if source.kind == "openreview"]
    if not event_pages or len(abstracts) != 1 or not openreview:
        raise ValueError("collection manifest source set is incomplete")
    if abstracts[0].url != str(request.source_urls["abstracts"]):
        raise ValueError("abstract source URL differs from registry")
    return loaded


def rebuild_scope_from_snapshots(request: VenueRequest, root: Path) -> CollectionResult:
    if request.adapter == "acl_anthology":
        return rebuild_acl_scope_from_snapshots(request, root)
    if request.adapter not in {"icml_virtual", "pmlr"}:
        raise UnsupportedPipelineRoute(
            "snapshot rebuild is not available for this route"
        )
    paths, manifest = _load_icml_manifest(request, root)
    loaded = _load_manifest_sources(request, paths, manifest)
    if request.adapter == "pmlr":
        return _normalize_pmlr_corpus(request, paths, tuple(loaded))
    corpus = IcmlRawCorpus(
        event_pages=tuple(source for source in loaded if source.kind == "events"),
        abstracts=next(source for source in loaded if source.kind == "abstracts"),
        openreview_pages=tuple(
            source for source in loaded if source.kind == "openreview"
        ),
    )
    return _normalize_icml_corpus(request, paths, corpus)


def load_scope_records(
    request: VenueRequest, root: Path
) -> tuple[list[PaperRecord], list[PaperRecord], tuple[SourceRef, ...]]:
    if request.adapter == "acl_anthology":
        return load_acl_scope_records(request, root)
    paths, manifest = _load_icml_manifest(request, root)
    sources = _load_manifest_sources(request, paths, manifest)
    normalized = manifest.get("normalized")
    if not isinstance(normalized, Mapping):
        raise TypeError("collection manifest has no normalized artifact")
    data = paths.normalized.read_bytes()
    if hashlib.sha256(data).hexdigest() != normalized.get("sha256"):
        raise ValueError("normalized JSONL hash does not match the collection manifest")
    records = [
        PaperRecord.model_validate_json(line)
        for line in data.decode("utf-8").splitlines()
        if line.strip()
    ]
    included = [
        record for record in records if record.status is not RecordStatus.EXCLUDED
    ]
    excluded = [record for record in records if record.status is RecordStatus.EXCLUDED]
    return included, excluded, tuple(source.source for source in sources)


def validate_scope(request: VenueRequest, root: Path) -> ValidationReport:
    if request.adapter not in {"icml_virtual", "pmlr"}:
        return validate_acl_scope(request, root)
    paths, manifest = _load_icml_manifest(request, root)
    included, excluded, _sources = load_scope_records(request, root)
    counts = manifest.get("counts")
    if not isinstance(counts, Mapping):
        raise TypeError("collection manifest has no counts")
    actual_included = sum(
        record.status in {RecordStatus.COMPLETE, RecordStatus.PARTIAL}
        for record in included
    )
    actual_unresolved = sum(
        record.status is RecordStatus.UNRESOLVED for record in included
    )
    expected_counts = {
        "discovered": len(included) + len(excluded),
        "included": actual_included,
        "excluded": len(excluded),
        "unresolved": actual_unresolved,
    }
    if any(counts.get(key) != value for key, value in expected_counts.items()):
        raise ValueError("collection manifest count does not match normalized records")
    report = validate_records(
        included,
        excluded,
        expected_included=actual_included + actual_unresolved,
    )
    if report.record_set_sha256 != manifest["normalized"]["record_set_sha256"]:  # type: ignore[index]
        raise ValueError("normalized record-set hash does not match the manifest")
    if counts.get("duplicate_candidates") != report.duplicate_candidate_count:
        raise ValueError("collection manifest duplicate count does not match records")
    _atomic_write(paths.analysis / "validation.json", _json_bytes(asdict(report)))
    return report


def build_preliminary_release(
    request: VenueRequest,
    root: Path,
    *,
    write_release: bool,
) -> dict[str, object]:
    if request.adapter not in {"acl_anthology", "icml_virtual", "pmlr"}:
        raise UnsupportedPipelineRoute(
            "papers-only release is not available for this route"
        )
    paths = ScopePaths.for_request(Path(root), request)
    report = validate_scope(request, root)
    assert_publishable(report)
    records, excluded, sources = load_scope_records(request, root)
    final = request.publication_status == "final_proceedings"
    track_label = {
        "findings": "Findings",
        "long": "Long Papers",
        "main": "Main Conference",
    }.get(request.track or "", request.track or "Unknown Track")
    source_label = f"{request.venue} {request.year} {track_label}"
    context = PublicationContext(
        status="final_proceedings" if final else "preliminary_official_program",
        final_source_status="available" if final else "not_published",
        final_source_url=request.final_source_url,
        notice=(
            f"来自官方论文集的 {source_label} 论文清单。"
            if final
            else f"来自官方会议程序的 {source_label} 论文清单，等待正式论文集对照。"
        ),
        analysis_availability=AnalysisAvailability(
            papers=True,
            distribution=False,
            trends=False,
            advances=False,
            awards=False,
        ),
    )
    note = (
        f"# {source_label} 论文集说明\n\n"
        f"- 收录论文：{report.included_count}\n"
        f"- 排除记录：{report.excluded_count}\n"
        f"- 待处理记录：{len(report.unresolved_record_ids)}\n"
        f"- 缺少英文摘要：{len(report.missing_abstract_ids)}\n"
        f"- 缺少 PDF：{len(report.missing_pdf_ids)}\n"
        f"- 缺少 DOI：{len(report.missing_doi_ids)}\n"
        f"- 官方来源：{request.final_source_url or request.volume_url}"
        f"（{'已正式发布' if final else '尚未发布'}）\n"
    ).encode()
    _atomic_write(paths.notes, note)
    if write_release:
        write_release_bundle = ReleaseBundle(
            records=records,
            excluded_records=excluded,
            validation=report,
            taxonomy_version="not-classified",
            generated_at=max(
                source.retrieved_at
                for source in sources
                if source.retrieved_at is not None
            ),
            sources=sources,
            publication_context=context,
        )
        publish_release(write_release_bundle, paths.release)
        generation = resolve_current_release(paths.release).name
    else:
        generation = None
    return {
        "generation": generation,
        "included_count": report.included_count,
        "excluded_count": report.excluded_count,
        "missing_abstract_count": len(report.missing_abstract_ids),
        "missing_pdf_count": len(report.missing_pdf_ids),
        "publication_status": context.status,
    }


def analyze_scope(
    request: VenueRequest,
    root: Path,
    *,
    write_release: bool,
) -> dict[str, object]:
    paths = ScopePaths.for_request(Path(root), request)
    assignments_exist = (paths.classification / "assignments.jsonl").exists()
    if assignments_exist:
        if request.adapter in {"icml_virtual", "pmlr"}:
            return analyze_classified_scope(request, root, write_release=write_release)
        if request.adapter == "acl_anthology":
            return analyze_acl_scope(request, root, write_release=write_release)
    if request.adapter in {"acl_anthology", "icml_virtual", "pmlr"}:
        return build_preliminary_release(request, root, write_release=write_release)
    raise UnsupportedPipelineRoute(
        f"unsupported pipeline route: {request.venue}/{request.year}/{request.track or '-'}"
    )


def analyze_classified_scope(
    request: VenueRequest,
    root: Path,
    *,
    write_release: bool,
) -> dict[str, object]:
    """Publish an audited single-year distribution without temporal metrics."""
    if (request.venue, request.year, request.track, request.adapter) != (
        "ICML",
        2025,
        "main",
        "pmlr",
    ):
        raise UnsupportedPipelineRoute(
            "classified single-year analysis is implemented only for ICML/2025/main"
        )
    paths, records, assignments, assignments_sha256 = _current_assignment_state(
        request, root
    )
    low_status, _queue_sha256 = _load_low_confidence_reviews(
        paths,
        assignments,
        assignments_sha256=assignments_sha256,
    )
    if low_status.pending_ids or low_status.rejected_ids:
        raise PublicationBlocked(
            "publication blocked: low-confidence semantic review is incomplete"
        )
    audits, disclosures, audit_summary = _load_theme_audits(
        paths, records, assignments, low_status
    )
    population_counts = Counter(item.primary_topic for item in assignments)
    for theme, audit in audits.items():
        assert_theme_publishable(
            audit,
            low_confidence_review_complete=True,
            rejected_low_confidence_count=0,
            complete_population_review=(audit.sample_size == population_counts[theme]),
        )
    if disclosures:
        raise PublicationBlocked(
            "publication blocked: one or more primary themes failed the audit"
        )
    taxonomy = load_taxonomy()
    taxonomy_topics = {
        str(item["name"])
        for item in taxonomy["topics"]  # type: ignore[index]
    }
    assigned_topics = {item.primary_topic for item in assignments}
    if assigned_topics != taxonomy_topics:
        raise PublicationBlocked(
            "publication blocked: classified release must cover every taxonomy topic"
        )
    awards = _load_award_records(paths)
    deep_reads = _load_award_deep_reads(paths)
    award_ids = {award.paper_id for award in awards}
    if (
        len(awards) != 8
        or len(deep_reads) != 8
        or {item.paper_id for item in deep_reads} != award_ids
    ):
        raise PublicationBlocked(
            "publication blocked: eight official ICML awards require eight deep reads"
        )
    counts = Counter(item.primary_topic for item in assignments)
    metrics: dict[str, Decimal | int] = {"paper_count": len(records)}
    for theme in sorted(counts):
        metrics[f"topic_count:{theme}"] = counts[theme]
        metrics[f"topic_share:{theme}"] = topic_share(counts[theme], len(records))
    advances = build_single_year_advances(records, assignments, audits)
    if len(advances) != 5:
        raise PublicationBlocked(
            "publication blocked: single-year synthesis requires five research lanes"
        )
    validation = validate_scope(request, root)
    assert_publishable(validation)
    loaded_records, excluded, sources = load_scope_records(request, root)
    if [item.paper_id for item in loaded_records] != [
        item.paper_id for item in records
    ]:
        raise PublicationBlocked(
            "publication blocked: classified records differ from normalized corpus"
        )
    context = PublicationContext(
        status="final_proceedings",
        final_source_status="available",
        final_source_url=request.final_source_url,
        notice=("ICML 2025 单年主题分布与研究热点；当前年份不足，暂不判断时间趋势。"),
        analysis_availability=AnalysisAvailability(
            papers=True,
            distribution=True,
            trends=False,
            advances=True,
            awards=True,
        ),
    )
    bundle = ReleaseBundle(
        records=records,
        excluded_records=excluded,
        validation=validation,
        taxonomy_version=str(taxonomy["version"]),
        generated_at=datetime.now(UTC),
        assignments=assignments,
        audits=audits,
        low_confidence_ids=low_status.queued_ids,
        reviewed_low_confidence_ids=low_status.reviewed_ids,
        rejected_low_confidence_ids=low_status.rejected_ids,
        metrics=metrics,
        awards=awards,
        award_deep_reads=deep_reads,
        advances=advances,
        claims=(
            EvidenceClaim(
                claim=("该主题分布来自 ICML 2025 PMLR Volume 267 的主主题分类。"),
                evidence_type=EvidenceType.CROSS_PAPER_SYNTHESIS,
                source_urls=[request.final_source_url],
                locator="PMLR Volume 267 complete proceedings",
            ),
        ),
        sources=sources,
        publication_context=context,
    )
    note_lines = [
        "# ICML 2025 主会论文分析",
        "",
        f"- 论文总数：{len(records)}",
        "- 分析范围：单年主题分布与研究热点，不判断时间趋势。",
        f"- 获奖论文：{len(awards)}",
        "",
        "## 主题分布",
        "",
        *[
            f"- {theme}：{counts[theme]}（{topic_share(counts[theme], len(records)):.2%}）"
            for theme in sorted(counts)
        ],
    ]
    _atomic_write(paths.notes, ("\n".join(note_lines) + "\n").encode())
    generation = None
    if write_release:
        publish_release(bundle, paths.release)
        generation = resolve_current_release(paths.release).name
    return {
        "audit": audit_summary,
        "award_count": len(awards),
        "generation": generation,
        "included_count": len(records),
        "language": "single_year_distribution_or_hotspot_not_trend",
        "theme_counts": dict(sorted(counts.items())),
    }


def reconcile_final_scope(
    request: VenueRequest,
    root: Path,
    *,
    client: httpx.Client | None = None,
) -> dict[str, object]:
    if request.adapter != "icml_virtual":
        raise UnsupportedPipelineRoute(
            "final reconciliation is not available for this route"
        )
    owns_client = client is None
    active_client = client or httpx.Client()
    try:
        fetched = fetch_final_source(request, active_client)
    finally:
        if owns_client:
            active_client.close()
    if fetched.status is FinalSourceStatus.NOT_PUBLISHED:
        return {"status": fetched.status.value}
    if fetched.data is None or fetched.source is None or fetched.source.sha256 is None:
        raise ValueError("available PMLR response has no verified source payload")
    report = validate_scope(request, root)
    assert_publishable(report)
    preliminary, _excluded, _sources = load_scope_records(request, root)
    final = parse_pmlr_volume(fetched.data, request, fetched.source)
    diff = reconcile_pmlr_records(preliminary, final)
    paths = ScopePaths.for_request(Path(root), request)
    output = paths.analysis / "pmlr-reconciliation" / fetched.source.sha256
    snapshot = output / "source.html"
    diff_path = output / "diff.json"
    payload = {
        "schema_version": "pmlr-reconciliation-v1",
        "scope": {
            "venue": request.venue,
            "year": request.year,
            "track": request.track,
        },
        "source": fetched.source.model_dump(mode="json"),
        **asdict(diff),
    }
    _atomic_write(snapshot, fetched.data)
    _atomic_write(diff_path, _json_bytes(payload))
    return {
        "status": fetched.status.value,
        "source_sha256": fetched.source.sha256,
        "output": str(diff_path),
        "matched_count": diff.matched_count,
        "final_count": diff.final_count,
        "unresolved_count": len(diff.unresolved_pairs),
    }
