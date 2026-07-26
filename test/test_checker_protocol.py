"""Behavior tests for the exact version-one checker process protocol."""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys

import pytest

from project_standards import checker_protocol


def test_request_accepts_exact_canonical_payload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The protocol preserves one exact sorted canonical request.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Pytest temporary directory.
    """

    payload = {
        "path_list": ["a.py", "nested/b.py"],
        "project_root": str(tmp_path.resolve()),
        "protocol_version": 1,
        "scope": "changed",
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

    assert checker_protocol._checker_request_get() == payload


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {
                "path_list": [],
                "project_root": "/tmp",
                "protocol_version": 1,
                "scope": "all",
                "unexpected": True,
            },
            "must contain exactly",
        ),
        (
            {
                "path_list": [],
                "project_root": "/tmp",
                "protocol_version": 2,
                "scope": "all",
            },
            "Unsupported checker protocol version",
        ),
        (
            {
                "path_list": ["b.py", "a.py"],
                "project_root": "/tmp",
                "protocol_version": 1,
                "scope": "all",
            },
            "sorted and unique",
        ),
        (
            {
                "path_list": ["../escape.py"],
                "project_root": "/tmp",
                "protocol_version": 1,
                "scope": "all",
            },
            "canonical relative POSIX path",
        ),
    ],
)
def test_request_rejects_unknown_version_unsorted_and_escaping_values(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
    message: str,
) -> None:
    """Every version-one request boundary rejects malformed input.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        payload: Invalid request payload.
        message: Expected diagnostic fragment.
    """

    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

    with pytest.raises(ValueError, match=message):
        checker_protocol._checker_request_get()


def test_result_sorts_findings_and_omits_optional_line(capsys: pytest.CaptureFixture[str]) -> None:
    """Findings are deterministic and a missing line stays absent.

    Args:
        capsys: Pytest output capture fixture.
    """

    exit_code = checker_protocol._checker_result_write(
        [
            {"line": 4, "message": "second", "path": "b.py"},
            {"message": "first", "path": "a.py"},
        ]
    )

    assert exit_code == 1
    output_line_list = capsys.readouterr().out.splitlines()
    assert [json.loads(line) for line in output_line_list] == [
        {"message": "first", "path": "a.py"},
        {"line": 4, "message": "second", "path": "b.py"},
    ]


def test_result_rejects_invalid_line_and_escaping_path() -> None:
    """Untrusted checker findings cannot escape or use invalid line numbers."""

    with pytest.raises(ValueError, match="positive integer"):
        checker_protocol._checker_result_write([{"line": 0, "message": "bad", "path": "a.py"}])
    with pytest.raises(ValueError, match="canonical and relative"):
        checker_protocol._checker_result_write([{"message": "bad", "path": "../a.py"}])
