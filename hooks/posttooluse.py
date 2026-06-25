#!/usr/bin/env python3
"""Claude Code PostToolUse hook: advisory algorithmic-complexity notes for written Python."""
import json
import sys

try:
    from complexity_guard.analyze import analyze
except Exception:
    analyze = None


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
    if analyze is None:
        return ""
    path = (payload.get("tool_input") or {}).get("file_path", "")
    if not path.endswith(".py"):
        return ""
    try:
        source = open(path, encoding="utf-8").read()
    except OSError:
        return ""
    findings = analyze(source)
    ranges = _edit_ranges(payload, source)
    if ranges:
        findings = [f for f in findings if any(lo <= f.lineno <= hi for lo, hi in ranges)]
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
            print(note)
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
