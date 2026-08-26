"""Venue-neutral collection and validation dispatch."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path

import httpx

from conference_overview.adapters.icml import (
    FetchedIcmlSource,
    IcmlRawCorpus,
    fetch_icml_sources,
    parse_icml_sources,
)
from conference_overview.adapters.pmlr import FinalSourceStatus, check_final_source
from conference_overview.models import (
    AnalysisAvailability,
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
    _json_bytes,
    _jsonl_bytes,
    analyze_acl_scope,
    collect_acl_scope,
    validate_acl_scope,
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
from conference_overview.validate import (
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
    if (request.venue, request.year, request.track) == ("ACL", 2026, "long"):
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
            _persist_source(source, paths.snapshots)
            for source in fetched.event_pages
        ),
        abstracts=_persist_source(fetched.abstracts, paths.snapshots),
        openreview_pages=tuple(
            _persist_source(source, paths.snapshots)
            for source in fetched.openreview_pages
        ),
    )
    return _normalize_icml_corpus(request, paths, corpus)


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


def _load_icml_manifest(request: VenueRequest, root: Path) -> tuple[ScopePaths, dict[str, object]]:
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
        if len(data) != raw.get("byte_size") or hashlib.sha256(data).hexdigest() != raw.get("sha256"):
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


def rebuild_scope_from_snapshots(
    request: VenueRequest, root: Path
) -> CollectionResult:
    if request.adapter != "icml_virtual":
        raise UnsupportedPipelineRoute("snapshot rebuild is not available for this route")
    paths, manifest = _load_icml_manifest(request, root)
    loaded = _load_manifest_sources(request, paths, manifest)
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
    included = [record for record in records if record.status is not RecordStatus.EXCLUDED]
    excluded = [record for record in records if record.status is RecordStatus.EXCLUDED]
    return included, excluded, tuple(source.source for source in sources)


def validate_scope(request: VenueRequest, root: Path) -> ValidationReport:
    if request.adapter != "icml_virtual":
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
    if request.adapter != "icml_virtual":
        raise UnsupportedPipelineRoute("preliminary release is not available for this route")
    paths = ScopePaths.for_request(Path(root), request)
    report = validate_scope(request, root)
    assert_publishable(report)
    records, excluded, sources = load_scope_records(request, root)
    context = PublicationContext(
        status="preliminary_official_program",
        final_source_status="not_published",
        final_source_url=request.final_source_url,
        notice="来自 ICML 官方会议程序，等待 PMLR 最终对照。",
        analysis_availability=AnalysisAvailability(
            papers=True,
            distribution=False,
            trends=False,
            advances=False,
            awards=False,
        ),
    )
    note = (
        "# ICML 2026 Main Conference 预发布说明\n\n"
        f"- 收录论文：{report.included_count}\n"
        f"- 排除记录：{report.excluded_count}\n"
        f"- 待处理记录：{len(report.unresolved_record_ids)}\n"
        f"- 缺少英文摘要：{len(report.missing_abstract_ids)}\n"
        f"- 缺少 PDF：{len(report.missing_pdf_ids)}\n"
        f"- 最终对照：{request.final_source_url}（尚未发布）\n"
    ).encode()
    _atomic_write(paths.notes, note)
    if write_release:
        write_release_bundle = ReleaseBundle(
            records=records,
            excluded_records=excluded,
            validation=report,
            taxonomy_version="not-classified",
            generated_at=max(
                source.retrieved_at for source in sources if source.retrieved_at is not None
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
    if request.adapter == "icml_virtual":
        return build_preliminary_release(request, root, write_release=write_release)
    return analyze_acl_scope(request, root, write_release=write_release)


def reconcile_final_scope(
    request: VenueRequest,
    root: Path,
    *,
    client: httpx.Client | None = None,
) -> dict[str, object]:
    del root
    if request.adapter != "icml_virtual":
        raise UnsupportedPipelineRoute("final reconciliation is not available for this route")
    owns_client = client is None
    active_client = client or httpx.Client()
    try:
        status = check_final_source(request, active_client)
    finally:
        if owns_client:
            active_client.close()
    if status is FinalSourceStatus.NOT_PUBLISHED:
        return {"status": status.value}
    return {"status": status.value}
