#!/usr/bin/env python3
"""Claude Code PostToolUse hook: advisory algorithmic-complexity notes for written code.

Python gets the full native-ast analysis; other languages get structural + (high
confidence) semantic checks via tree-sitter when that optional dependency is
installed — otherwise non-Python edits are skipped (with a one-time install hint).
Project settings come from `.complexity-guard.toml` / pyproject `[tool.complexity-guard]`.
"""
import json
import os
import sys
import tempfile
from collections import Counter

try:
    from complexity_guard.analyze import analyze_lang
    from complexity_guard.langspec import lang_for_path
    from complexity_guard.config import load_config
    from complexity_guard.tsadapter import TS_AVAILABLE
except Exception:
    analyze_lang = None
    lang_for_path = None
    load_config = None
    TS_AVAILABLE = False


def _ts_hint_once() -> str:
    """Show the 'install tree-sitter' hint at most once per machine."""
    marker = os.path.join(tempfile.gettempdir(), "complexity-guard-tshint")
    try:
        if os.path.exists(marker):
            return ""
        open(marker, "w").close()
    except OSError:
        pass
    return (
        "ℹ️ Complexity Guard: multi-language analysis is inactive — tree-sitter "
        "isn't installed in this Python.\n"
        "   Enable it with:  pip install tree-sitter tree-sitter-language-pack\n"
        "   (Python files are still analyzed.)"
    )


def _finding_key(f):
    return (f.detector, f.function, f.complexity, f.message)


def _reconstruct_old(payload, source):
    ti = payload.get("tool_input") or {}
    if isinstance(ti.get("edits"), list):
        old = source
        for e in reversed(ti["edits"]):
            ns, os_ = e.get("new_string"), e.get("old_string")
            if ns is not None and os_ is not None:
                old = old.replace(ns, os_, 1)
        return old if old != source else None
    ns, os_ = ti.get("new_string"), ti.get("old_string")
    if ns is not None and os_ is not None:
        old = source.replace(ns, os_, 1)
        return old if old != source else None
    return None


def _net_new(old_source, findings, lang, config):
    old_counts = Counter(_finding_key(f) for f in analyze_lang(old_source, lang, config))
    kept = []
    for f in findings:
        k = _finding_key(f)
        if old_counts.get(k, 0) > 0:
            old_counts[k] -= 1
        else:
            kept.append(f)
    return kept


def _dedup(findings):
    bigo_funcs = {f.function for f in findings if f.detector == "bigo"}
    return [f for f in findings if not (f.detector == "nested-loop" and f.function in bigo_funcs)]


def _edit_ranges(payload, source):
    ti = payload.get("tool_input") or {}
    news = []
    if isinstance(ti.get("edits"), list):
        news = [e.get("new_string") for e in ti["edits"] if e.get("new_string")]
    elif ti.get("new_string"):
        news = [ti["new_string"]]
    ranges = []
    for new in news:
        idx = source.find(new)
        if idx == -1:
            continue
        start = source.count("\n", 0, idx) + 1
        end = start + new.count("\n")
        ranges.append((start, end))
    return ranges


def run(payload: dict) -> str:
    if analyze_lang is None:
        return ""
    path = (payload.get("tool_input") or {}).get("file_path", "")
    lang = lang_for_path(path)
    if lang is None:
        return ""
    config = load_config(path)
    if config.excludes(path) or not config.allows_language(lang):
        return ""
    # Supported non-Python file but tree-sitter isn't installed: nudge once, then
    # stay quiet (Python needs no extra dependency, so it's never affected).
    if lang != "python" and not TS_AVAILABLE:
        return _ts_hint_once()
    try:
        source = open(path, encoding="utf-8").read()
    except OSError:
        return ""
    findings = analyze_lang(source, lang, config)
    # Nothing flagged in the new source -> no need to reconstruct/re-analyze the
    # old source (the net-new / range filters can only ever shrink this list).
    if findings:
        old = _reconstruct_old(payload, source)
        if old is not None:
            findings = _net_new(old, findings, lang, config)
        else:
            ranges = _edit_ranges(payload, source)
            if ranges:
                findings = [f for f in findings if any(lo <= f.lineno <= hi for lo, hi in ranges)]
    findings = _dedup(findings)
    if not findings:
        return ""
    lines = ["⚠️ Complexity Guard:"]
    for f in findings:
        lines.append(f"  {path}:{f.lineno} [{f.detector}] {f.complexity} — {f.message}")
        lines.append(f"      ↳ {f.suggestion}")
    return "\n".join(lines)


def main() -> int:
    try:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            return 0
        note = run(payload)
        if note:
            # Emit Claude Code's hook JSON directly (no external `jq` dependency):
            # systemMessage -> shown to the user; additionalContext -> fed to the model.
            print(json.dumps({
                "systemMessage": note,
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": note,
                },
            }))
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
