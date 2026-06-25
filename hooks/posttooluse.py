#!/usr/bin/env python3
"""Claude Code PostToolUse hook: advisory algorithmic-complexity notes for written Python."""
import json
import sys

try:
    from complexity_guard.analyze import analyze
except Exception:
    analyze = None


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
