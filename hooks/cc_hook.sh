#!/usr/bin/env bash
# Claude Code PostToolUse wrapper for Complexity Guard.
# Runs the hook with the bundled analyzer on the import path and passes its JSON
# output straight through (the hook emits its own JSON, so no `jq` is needed).
# CLAUDE_PLUGIN_ROOT is set by Claude Code for installed plugins; fall back to
# this script's parent directory for direct / development use.
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

# Interpreter selection: an explicit COMPLEXITY_GUARD_PYTHON wins (set this when
# your `python3` is older than 3.11), otherwise prefer `python3`, then `python`.
# If none is found there's nothing to run, so exit quietly.
PY="${COMPLEXITY_GUARD_PYTHON:-}"
if [ -z "$PY" ]; then
  if command -v python3 >/dev/null 2>&1; then PY=python3
  elif command -v python >/dev/null 2>&1; then PY=python
  else exit 0
  fi
fi

exec env PYTHONPATH="$ROOT/lib:$ROOT/src" "$PY" "$ROOT/hooks/posttooluse.py"
