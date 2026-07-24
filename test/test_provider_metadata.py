"""Structural tests for the project-standards marketplace split."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_marketplace_exposes_one_local_project_standards_plugin() -> None:
    """Marketplace metadata points to the independently installable plugin."""

    payload = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))

    assert payload["name"] == "project-standards"
    assert len(payload["plugins"]) == 1
    assert payload["plugins"][0]["name"] == "project-standards"
    assert payload["plugins"][0]["source"] == {"source": "local", "path": "./plugins/project-standards"}


def test_plugin_manifest_uses_canonical_repository_identity() -> None:
    """Plugin metadata publishes the canonical provider and repository names."""

    payload = json.loads(
        (ROOT / "plugins" / "project-standards" / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )

    assert payload["name"] == "project-standards"
    assert payload["repository"] == "https://github.com/antonov-andrey/project-standards"
