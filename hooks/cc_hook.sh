#!/usr/bin/env bash
# Claude Code PostToolUse wrapper for Complexity Guard.
# Runs the analyzer on the written file and emits JSON Claude Code surfaces
# (systemMessage -> shown to user; additionalContext -> fed back to Claude).
# Always exits 0 — advisory, never blocks.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
payload="$(cat)"
out="$(printf '%s' "$payload" | PYTHONPATH="$ROOT/src" python3 "$ROOT/hooks/posttooluse.py" 2>/dev/null)"
[ -n "$out" ] && printf '%s' "$out" | jq -Rs '{systemMessage: ., hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: .}}'
exit 0
