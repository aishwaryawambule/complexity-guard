# Complexity Guard

A Claude Code plugin that flags the *algorithmic* inefficiency of code the model
writes — Big-O smells and documented LLM anti-patterns — the moment it's written.

Python gets the full analysis. Other languages get structural checks (nested
loops, deep nesting, un-memoized recursion) **plus** high-confidence semantic
checks (membership / sort / string-concat in loops) when the optional tree-sitter
dependency is installed.

## Install

### As a Claude Code plugin (for users)

1. Add the marketplace and install the plugin (or do the same via the `/plugin`
   command inside Claude Code):
   ```bash
   claude plugin marketplace add aishwaryawambule/complexity-guard
   claude plugin install complexity-guard@complexity-guard-marketplace
   ```
2. **Python is ready immediately** — the only requirement is Python 3.11+ available
   as `python3` (that's what the hook runs). No extra dependencies.
3. **To check other languages too**, make tree-sitter importable from the
   `python3` the hook runs. On most modern systems `pip install` into the
   system interpreter is blocked by [PEP 668](https://peps.python.org/pep-0668/)
   (`externally-managed-environment` — pip tells you to use a venv), so the
   reliable approach is a dedicated venv that you point the hook at:
   ```bash
   python3 -m venv ~/.complexity-guard-venv
   ~/.complexity-guard-venv/bin/pip install tree-sitter tree-sitter-language-pack
   ```
   Then pin that interpreter so it's used regardless of what's on `PATH`, via
   Claude Code's settings `env` (so the hook subprocess always sees it):
   ```json
   // ~/.claude/settings.json — the python3.14 below MUST match your venv's version
   "env": { "COMPLEXITY_GUARD_PYTHON": "/Users/<you>/.complexity-guard-venv/bin/python3.14" }
   ```
   That trailing `python3.14` is **not** a leave-as-is placeholder — it must be the
   exact version your venv was built with (`python3.12`, `python3.13`, …), or the
   path won't exist and the interpreter won't launch. Check the real name with
   `ls ~/.complexity-guard-venv/bin/python*`. (Inside a venv, `python`, `python3`,
   and `python3.<minor>` all point to the *same* interpreter, so any works — but the
   version-specific name is the most explicit and least surprising.) This one
   variable drives **both** the auto-hook **and** the `/complexity` command — set it once.

   Quick alternative (installs into the system `python3` the hook already uses,
   at the cost of polluting it): `pip install --break-system-packages tree-sitter tree-sitter-language-pack`.

   Either way, Python is analyzed with no extra setup; without tree-sitter you
   just get a one-time install hint on your first non-Python edit — nothing
   breaks. See [Which `python3` runs the hook](#which-python3-runs-the-hook) for
   exactly which interpreter "that same `python3`" means.

### For local development

- `pip install -e ".[dev]"` (Python only) or `pip install -e ".[dev,multilang]"`
  (adds tree-sitter), then run `pytest`.

## Use
- Automatic: the `PostToolUse` hook prints advisory notes when Claude writes a
  supported file. Python is always covered; other languages are covered when
  `tree-sitter` is installed in the Python that runs the hook.
- On demand: `/complexity path/to/file`, or `complexity-guard path/to/file [--json]`.

## Which `python3` runs the hook

The hook never activates a virtualenv itself — it picks an interpreter at run
time (see [`cc_hook.sh`](plugin/hooks/cc_hook.sh)):

1. `$COMPLEXITY_GUARD_PYTHON` if set, else
2. the first `python3` on `PATH`, else
3. `python`.

So "that same `python3`" means *whichever interpreter that resolution lands on
in the environment Claude Code launches the hook in* — **not** necessarily a
venv. A venv only matters if it's the interpreter the hook ends up running:

- If you develop inside an **activated venv** and launch Claude Code from that
  shell, `python3` resolves to the venv — so tree-sitter must live there.
- If Claude Code runs **without** a venv active, the hook uses the **system**
  `python3`, and tree-sitter must be installed there instead (or blocked by
  PEP 668 — see [Install](#install)).
- To remove the ambiguity entirely, set `COMPLEXITY_GUARD_PYTHON` to an absolute
  interpreter path — ideally the version-specific binary from your venv, e.g.
  `~/.complexity-guard-venv/bin/python3.14` — via Claude Code's settings `env`.
  Both the hook **and** the `/complexity` command then use it no matter what's on
  `PATH`. This is the recommended setup.

`COMPLEXITY_GUARD_PYTHON` is also the fix when the resolved `python3` is older
than 3.11: point it at a 3.11+ interpreter.

## What it flags

**Python (native `ast`)** — nested loops (O(n²)), `in list` inside a loop,
un-memoized recursion, `+=` string building in loops, sorting in loops,
loop-invariant calls, and a nesting-depth Big-O estimate.

**Other languages (tree-sitter)** — covers JavaScript/TypeScript, Go, Rust,
Java, C#, Ruby, PHP, C/C++, Kotlin, Lua, Scala, and more (any language whose
tree-sitter grammar uses the common node names works automatically):

- *Structural* (all languages): nested loops, a nesting-depth Big-O estimate,
  and un-memoized recursion. Constant-bounded loops (`for (i=0;i<3;i++)`,
  `0..3`) are not counted, and recursion that references a `memo`/`cache`/`dp`
  table is treated as already memoized.
- *Semantic* (high-confidence signals): a linear membership scan in a loop
  (`arr.includes` / `indexOf` / `in_array` / `include?`), `sort` inside a loop,
  and `+=` / `.=` string building inside a loop. Suggestions are tailored per
  language (e.g. Java → `StringBuilder`, Go → `strings.Builder`, JS → `Set`).
- *Type-tracked membership*: `list.contains()` / `Contains()` / `slices.Contains`
  inside a loop is flagged in Java, C#, Rust, and Go — but only when the receiver
  is a known list. A `HashSet`/`Set`/`map` receiver (O(1)) or an unknown type is
  left alone, so the check stays conservative.

Estimates are heuristics with named evidence, not proofs.

## Configuration (optional)

Drop a `.complexity-guard.toml` at your project root (or a
`[tool.complexity-guard]` table in `pyproject.toml`). It's discovered by walking
up from the file being analyzed; a missing or broken config just uses defaults.

```toml
disable = ["string-concat-in-loop"]   # detector names to turn off
exclude = ["*/migrations/*", "*_pb2.py"]   # globs matched on the full path / basename
disable_languages = ["c", "cpp"]      # skip these languages entirely
bigo_min_depth = 3                    # only report O(n^3)+ from the bigo estimate
```

Every key is optional. When a key is omitted (or there's no config file at all),
these defaults apply:

| key | default | meaning when unset |
| --- | --- | --- |
| `disable` | `[]` | every detector runs |
| `exclude` | `[]` | no files are skipped |
| `disable_languages` | `[]` | every supported language is analyzed |
| `bigo_min_depth` | `2` | the bigo estimate reports O(n²) and deeper |

Detector names: `bigo`, `nested-loop`, `recursion-no-memo`, `membership-in-loop`,
`repeated-sort-in-loop`, `string-concat-in-loop`, `loop-invariant-call`.

## Releasing

Plugin installs are **keyed by version**, and Claude Code's background
auto-update only pulls a new build when the version increases. Shipping changed
code under the same version leaves already-installed users on stale code, so
every change to the shipped tree needs a version bump — always cut releases with:

```bash
scripts/release.sh 0.1.2 --push
```

It bumps `plugin/.claude-plugin/plugin.json` and `pyproject.toml` together,
re-bundles `plugin/`, runs the suite, commits, and tags `complexity-guard--v0.1.2`.
`tests/test_version_guard.py` fails if `plugin/` changed since the latest release
tag without a bump, so a forgotten version can't slip through CI.
