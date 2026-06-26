"""Guard: shipped plugin code must not change without a version bump.

A plugin update only reaches already-installed users when plugin.json's version
increases — the install cache is keyed by version (``…/complexity-guard/<version>/``)
and background auto-update is version-gated. So if ``plugin/`` changed since the
last released tag (``complexity-guard--v<version>``) but the version was *not*
bumped, every existing install stays pinned to stale code. This test turns that
"forgot to bump" footgun into a red test instead of a silent non-update.

Releases are cut with ``scripts/release.sh`` (which bumps + tags); the tag is the
baseline this guard compares against.
"""
import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_JSON = ROOT / "plugin" / ".claude-plugin" / "plugin.json"
PYPROJECT = ROOT / "pyproject.toml"
TAG_PREFIX = "complexity-guard--v"


def _git(*args):
    return subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, text=True
    )


def _semver(v: str) -> tuple:
    return tuple(int(p) for p in v.split(".") if p.isdigit())


def _plugin_version() -> str:
    return json.loads(PLUGIN_JSON.read_text())["version"]


def _pyproject_version() -> str | None:
    m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', PYPROJECT.read_text())
    return m.group(1) if m else None


def _release_tags():
    r = _git("tag", "--list", f"{TAG_PREFIX}*")
    tags = []
    if r.returncode == 0:
        n = len(TAG_PREFIX)
        for name in r.stdout.split():
            try:
                tags.append((_semver(name[n:]), name))
            except ValueError:
                pass
    return tags


def test_plugin_and_pyproject_versions_agree():
    # The two manifests must move together — release.sh bumps both.
    assert _pyproject_version() == _plugin_version(), (
        "pyproject.toml and plugin.json versions disagree — bump them together"
    )


def test_shipped_code_change_requires_version_bump():
    if _git("rev-parse", "--git-dir").returncode != 0:
        pytest.skip("not a git checkout — nothing to compare")
    tags = _release_tags()
    if not tags:
        pytest.skip("no release tags yet — cut one with scripts/release.sh")

    latest_semver, latest_tag = max(tags)
    # Did the shipped tree change since the most recent release?
    changed = _git("diff", "--quiet", latest_tag, "--", "plugin").returncode != 0
    if not changed:
        return  # plugin/ identical to the last release — no bump owed

    current = _plugin_version()
    assert _semver(current) > latest_semver, (
        f"plugin/ has changed since {latest_tag}, but plugin.json version is still "
        f"{current}. Bump it above {latest_tag[len(TAG_PREFIX):]} (use "
        f"scripts/release.sh) so already-installed users actually receive the "
        f"update — a same-version release serves stale cache and is skipped by "
        f"auto-update."
    )
