# NOTE: keep this module's top-level imports to the stdlib only, and keep the
# annotations import below. The slash command launches the CLI with a plain
# `python3`, then `_reexec_under_override()` may hand off to a newer/venv python.
# That hand-off must run *before* the analyzer (which uses 3.10+ syntax and pulls
# in tree-sitter) is imported, or an old `python3` would blow up on import first —
# so `analyze_path` is imported lazily inside `main()`, after the re-exec point.
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

from . import __version__


def _reexec_under_override() -> None:
    """Re-run under ``$COMPLEXITY_GUARD_PYTHON`` when it names a different interpreter.

    The slash command launches us with a plain ``python3`` on purpose: Claude Code's
    permission check refuses to auto-approve a Bash command that contains a shell
    expansion like ``${COMPLEXITY_GUARD_PYTHON:-python3}`` (it can't prove what the
    expansion resolves to), so it only runs in auto-accept mode. Keeping the command
    static fixes that; the interpreter override moves here instead. If the env var
    points at another python (e.g. a newer one, or a venv with tree-sitter), exec
    into it before any analysis runs. ``_CG_REEXEC`` guards against an exec loop.
    """
    override = os.environ.get("COMPLEXITY_GUARD_PYTHON")
    if not override or os.environ.get("_CG_REEXEC"):
        return
    target = shutil.which(override) or override
    if os.path.realpath(target) == os.path.realpath(sys.executable):
        return
    os.environ["_CG_REEXEC"] = "1"
    os.execvp(target, [target, "-m", "complexity_guard.cli", *sys.argv[1:]])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="complexity-guard")
    parser.add_argument("file")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--version",
        action="version",
        version=f"complexity-guard {__version__}",
    )
    args = parser.parse_args(argv)

    # Deferred — see module note above. Kept *after* parse_args so `--version`
    # (and `--help`) resolve without importing the analyzer, which needs 3.10+
    # syntax and tree-sitter; --version must work under a bare python3.
    from .analyze import analyze_path

    # Accept editor-style "@path" file mentions (e.g. from a slash command's
    # $ARGUMENTS) by treating a leading "@" as sugar for the bare path.
    file = args.file[1:] if args.file.startswith("@") else args.file

    source = Path(file).read_text()
    findings = analyze_path(file, source)

    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
        return 0

    if not findings:
        print(f"✓ {file}: no complexity smells found")
        return 0

    for f in findings:
        print(f"{file}:{f.lineno}  [{f.detector}] {f.complexity} — {f.message}")
        print(f"    ↳ {f.suggestion}")
    return 0


if __name__ == "__main__":
    _reexec_under_override()
    sys.exit(main())
