"""Guard: the shipped plugin/ tree must stay in sync with the dev sources.

scripts/bundle.sh copies src/complexity_guard -> plugin/lib/complexity_guard and
the hook scripts -> plugin/hooks/. Nothing else enforces that copy, so a change to
src/ or hooks/ that forgets the bundle would ship a stale analyzer to users while
the suite (which imports from src/) stays green. These tests fail until the bundle
is re-run.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_PKG = ROOT / "src" / "complexity_guard"
LIB_PKG = ROOT / "plugin" / "lib" / "complexity_guard"
HOOKS = ROOT / "hooks"
PLUGIN_HOOKS = ROOT / "plugin" / "hooks"


def _rel_source_files(base: Path) -> set:
    """Relative paths of real source files under ``base`` (no bytecode caches)."""
    return {
        p.relative_to(base)
        for p in base.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    }


def test_plugin_lib_matches_src():
    src_files = _rel_source_files(SRC_PKG)
    lib_files = _rel_source_files(LIB_PKG)
    assert src_files == lib_files, (
        "plugin/lib/complexity_guard is out of sync with src/complexity_guard "
        "(file set differs) — run scripts/bundle.sh"
    )
    for rel in sorted(src_files):
        assert (SRC_PKG / rel).read_bytes() == (LIB_PKG / rel).read_bytes(), (
            f"{rel} differs between src/ and plugin/lib/ — run scripts/bundle.sh"
        )


def test_plugin_hooks_match_sources():
    for name in ("posttooluse.py", "cc_hook.sh"):
        assert (HOOKS / name).read_bytes() == (PLUGIN_HOOKS / name).read_bytes(), (
            f"hooks/{name} differs from plugin/hooks/{name} — run scripts/bundle.sh"
        )
