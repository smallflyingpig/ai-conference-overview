import pytest

from conference_overview.registry import (
    canonicalize_official_host,
    canonicalize_official_hosts,
    normalize_request,
)


def test_nips_alias_normalizes_to_neurips() -> None:
    request = normalize_request("NIPS", 2025, None)

    assert request.venue == "NEURIPS"


def test_acl_long_request_uses_official_source_routes() -> None:
    request = normalize_request("acl", 2026, "long")

    assert request.venue == "ACL"
    assert request.source_key == "2026.acl-long"
    assert str(request.bibtex_url) == (
        "https://aclanthology.org/volumes/2026.acl-long.bib"
    )
    assert str(request.volume_url) == "https://aclanthology.org/volumes/2026.acl-long/"
    assert request.awards_enabled is True


def test_acl_request_infers_the_only_configured_track() -> None:
    request = normalize_request("ACL", 2026, None)

    assert request.track == "long"
    assert request.source_key == "2026.acl-long"


def test_acl_findings_request_is_registered_as_non_default_track() -> None:
    request = normalize_request("ACL", 2026, "findings")

    assert request.track == "findings"
    assert request.adapter == "acl_anthology"
    assert request.source_key == "2026.findings-acl"
    assert request.default_track == "long"
    assert request.is_default_track is False
    assert request.awards_enabled is False
    assert str(request.bibtex_url) == (
        "https://aclanthology.org/volumes/2026.findings-acl.bib"
    )
    assert str(request.volume_url) == (
        "https://aclanthology.org/volumes/2026.findings-acl/"
    )


def test_acl_default_request_remains_long_after_findings_registration() -> None:
    request = normalize_request("ACL", 2026, None)

    assert request.track == "long"
    assert request.adapter == "acl_anthology"
    assert request.default_track == "long"
    assert request.is_default_track is True


def test_icml_main_request_uses_official_preliminary_sources() -> None:
    request = normalize_request("icml", 2026, None)

    assert request.venue == "ICML"
    assert request.track == "main"
    assert request.adapter == "icml_virtual"
    assert request.source_key == "icml-2026-main-preliminary"
    assert request.publication_status == "preliminary_official_program"
    assert str(request.source_urls["papers_page"]) == (
        "https://icml.cc/virtual/2026/papers.html"
    )
    assert str(request.source_urls["events"]) == (
        "https://icml.cc/static/virtual/data/icml-2026-orals-posters.json"
    )
    assert str(request.source_urls["abstracts"]) == (
        "https://icml.cc/static/virtual/data/icml-2026-abstracts.json"
    )
    assert str(request.source_urls["openreview_group"]) == (
        "https://openreview.net/group?id=ICML.cc/2026/Conference"
    )
    assert str(request.final_source_url) == "https://proceedings.mlr.press/v306/"
    assert request.official_award_hosts == ()


def test_icml_2025_defaults_to_final_pmlr_proceedings() -> None:
    request = normalize_request("ICML", 2025, None)

    assert request.track == "main"
    assert request.adapter == "pmlr"
    assert request.source_key == "pmlr-v267"
    assert request.publication_status == "final_proceedings"
    assert str(request.source_urls["volume"]) == "https://proceedings.mlr.press/v267/"
    assert str(request.source_urls["metadata"]) == (
        "https://proceedings.mlr.press/v267/assets/bib/citeproc.yaml"
    )
    assert request.awards_enabled is True


def test_icml_rejects_acl_track_name() -> None:
    request = normalize_request("ICML", 2026, "long")

    assert request.source_key is None


def test_official_hosts_are_canonicalized_and_deduplicated_once() -> None:
    assert canonicalize_official_hosts(
        [" Example.COM. ", "example.com", "BÜCHER.example.", "xn--bcher-kva.example"]
    ) == ("example.com", "xn--bcher-kva.example")


def test_official_hosts_use_nontransitional_uts46_idna2008() -> None:
    assert canonicalize_official_hosts(["faß.de", "xn--fa-hia.de"]) == (
        "xn--fa-hia.de",
    )
    assert canonicalize_official_hosts(["faß.de"]) != ("fass.de",)


@pytest.mark.parametrize("host", ["example.com.", "example.com。"])
def test_official_host_accepts_one_canonical_terminal_root_dot(host: str) -> None:
    assert canonicalize_official_host(host) == "example.com"


def test_official_host_rejects_double_terminal_dot_empty_label() -> None:
    with pytest.raises(ValueError, match="IDNA|hostname"):
        canonicalize_official_host("example.com..")
