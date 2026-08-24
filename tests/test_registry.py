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
    assert str(request.bibtex_url) == "https://aclanthology.org/2026.acl-long.bib"
    assert str(request.volume_url) == "https://aclanthology.org/volumes/2026.acl-long/"


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
