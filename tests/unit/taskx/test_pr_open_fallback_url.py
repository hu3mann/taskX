"""Fallback URL parsing tests for PR open flow."""

from taskx.pr.open import _parse_owner_repo


def test_parse_owner_repo_https() -> None:
    assert _parse_owner_repo("https://github.com/acme/taskX.git") == "acme/taskX"


def test_parse_owner_repo_ssh() -> None:
    assert _parse_owner_repo("git@github.com:acme/taskX.git") == "acme/taskX"


def test_parse_owner_repo_invalid() -> None:
    assert _parse_owner_repo("https://example.com/acme/taskX.git") is None
