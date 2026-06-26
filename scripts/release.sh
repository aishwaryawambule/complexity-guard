#!/usr/bin/env bash
# Cut a Complexity Guard release.
#
# One command bumps the version in both manifests, re-bundles plugin/, runs the
# suite, commits, and tags `complexity-guard--v<version>`. ALWAYS release through
# this: plugin installs are keyed by version and auto-update is version-gated, so
# shipping changed code under the same version leaves existing users on stale
# code. tests/test_version_guard.py enforces that a plugin/ change since the last
# tag is accompanied by a bump.
#
# Usage: scripts/release.sh <X.Y.Z> [--push]
set -euo pipefail
VERSION="${1:?usage: scripts/release.sh X.Y.Z [--push]}"
PUSH="${2:-}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "version must be X.Y.Z, got: $VERSION" >&2
  exit 1
fi

# 1. Bump plugin.json + pyproject.toml in lockstep.
python3 - "$VERSION" <<'PY'
import json, re, sys, pathlib
v = sys.argv[1]
pj = pathlib.Path("plugin/.claude-plugin/plugin.json")
d = json.loads(pj.read_text()); d["version"] = v
pj.write_text(json.dumps(d, indent=2) + "\n")
pp = pathlib.Path("pyproject.toml")
pp.write_text(re.sub(r'(?m)^version\s*=\s*"[^"]+"', f'version = "{v}"', pp.read_text(), count=1))
print(f"bumped plugin.json + pyproject.toml -> {v}")
PY

# 2. Re-bundle the shipped tree and run the suite (guard included).
bash scripts/bundle.sh
python3 -m pytest -q

# 3. Commit + annotated tag (the version-guard baseline).
TAG="complexity-guard--v${VERSION}"
git add plugin pyproject.toml src hooks
git commit -m "release: v${VERSION}"
git tag -a "$TAG" -m "complexity-guard v${VERSION}"
echo "committed and tagged $TAG"

# 4. Publish (branch + tag) only when asked.
if [ "$PUSH" = "--push" ]; then
  git push origin HEAD
  git push origin "$TAG"
  echo "pushed branch + $TAG"
else
  echo "not pushed. publish with:  git push origin HEAD && git push origin $TAG"
fi
