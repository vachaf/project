from __future__ import annotations

import pytest

from src.prepare.file_disclosure_hints import detect_file_disclosure_hints
from src.prepare.traversal_cmdi_hints import TRAVERSAL_PATTERNS


def traversal_pattern_names(text: str) -> set[str]:
    return {
        name
        for name, pattern, _points in TRAVERSAL_PATTERNS
        if pattern.search(text)
    }


def file_disclosure(text: str) -> tuple[int, list[str]]:
    return detect_file_disclosure_hints(
        combined_target=text,
        query_variants=[],
        raw_request_target_variants=[],
    )


@pytest.mark.parametrize(
    "text",
    [
        "../foo",
        "../../foo",
        "arg=../foo",
        "arg=..\\foo",
        "/path/../secret",
        "?x=../../foo",
        "&x=../foo",
    ],
)
def test_bounded_dotdot_path_escape_is_traversal(text: str) -> None:
    assert "dotdot_slash" in traversal_pattern_names(text)


@pytest.mark.parametrize(
    "text",
    [
        "..foo",
        "/..",
        "foo../bar",
        "foo..\\bar",
        "foo.../bar",
        "abc../def",
        "version..//something",
    ],
)
def test_embedded_or_incomplete_dotdot_is_not_traversal(text: str) -> None:
    assert not traversal_pattern_names(text)


def test_bounded_triple_dot_is_explicit_not_an_inner_dotdot_match() -> None:
    assert traversal_pattern_names(".../.../foo") == {"triple_dot_slash"}
    assert not traversal_pattern_names("foo.../bar")


@pytest.mark.parametrize(
    "text",
    [
        "%2e%2e%2fsecret",
        "%2e%2e/secret",
        "..%2fsecret",
        "%252e%252e%252fsecret",
        "arg=%2e%2e%2fsecret",
    ],
)
def test_existing_encoded_dotdot_forms_remain_traversal(text: str) -> None:
    assert "dotdot_slash" in traversal_pattern_names(text)


@pytest.mark.parametrize(
    "text",
    [
        "/etc/passwd",
        "op=/etc/passwd",
        "file=/etc/passwd%00",
        "x=WINDOWS/win.ini",
        "win.ini",
    ],
)
def test_direct_os_file_is_sensitive_resource_not_traversal(text: str) -> None:
    score, hints = file_disclosure(text)

    assert score == 5
    assert hints == ["file_disclosure:sensitive_resource:os_file"]
    assert not traversal_pattern_names(text)


@pytest.mark.parametrize("text", ["twin.ini", "win.ini.bak", "/etc/passwdish"])
def test_sensitive_os_file_names_require_a_resource_boundary(text: str) -> None:
    assert file_disclosure(text) == (0, [])


def test_explicit_traversal_and_sensitive_resource_are_orthogonal() -> None:
    text = "../../etc/passwd"
    score, hints = file_disclosure(text)

    assert "dotdot_slash" in traversal_pattern_names(text)
    assert score == 5
    assert hints == ["file_disclosure:sensitive_resource:os_file"]
