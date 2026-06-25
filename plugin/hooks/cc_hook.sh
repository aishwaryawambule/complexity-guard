#!/usr/bin/env bash
# Claude Code PostToolUse wrapper for Complexity Guard.
# Runs the hook with the bundled analyzer on the import path and passes its JSON
# output straight through (the hook emits its own JSON, so no `jq` is needed).
# CLAUDE_PLUGIN_ROOT is set by Claude Code for installed plugins; fall back to
# this script's parent directory for direct / development use.
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
exec env PYTHONPATH="$ROOT/lib:$ROOT/src" python3 "$ROOT/hooks/posttooluse.py"
