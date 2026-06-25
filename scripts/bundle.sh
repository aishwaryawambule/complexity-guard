#!/usr/bin/env bash
# Sync the analyzer package and hook scripts into the self-contained plugin/ tree.
# Run this whenever src/ or hooks/ change, before committing a release — the
# shipped plugin must be self-contained (Claude Code copies only plugin/ on install).
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"

rm -rf "$HERE/plugin/lib/complexity_guard"
mkdir -p "$HERE/plugin/lib" "$HERE/plugin/hooks"
cp -R "$HERE/src/complexity_guard" "$HERE/plugin/lib/complexity_guard"
cp "$HERE/hooks/posttooluse.py" "$HERE/hooks/cc_hook.sh" "$HERE/plugin/hooks/"

# Drop bytecode caches so they don't ship.
find "$HERE/plugin/lib" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true

echo "bundled plugin/ from src/complexity_guard + hooks/"
