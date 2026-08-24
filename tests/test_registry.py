from conference_overview.registry import canonicalize_official_hosts, normalize_request


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
