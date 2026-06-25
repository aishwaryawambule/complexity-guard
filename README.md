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
3. **To check other languages too**, install tree-sitter into that same `python3`:
   ```bash
   pip install tree-sitter tree-sitter-language-pack
   ```
   That's the one and only thing a user does for multi-language support. Without
   it, Python is still analyzed and you get a one-time install hint on your first
   non-Python edit — nothing breaks. See
   [Multi-language support](#multi-language-support-tree-sitter) for which
   interpreter "that same `python3`" means.

### For local development

- `pip install -e ".[dev]"` (Python only) or `pip install -e ".[dev,multilang]"`
  (adds tree-sitter), then run `pytest`.

## Use
- Automatic: the `PostToolUse` hook prints advisory notes when Claude writes a
  supported file. Python is always covered; other languages are covered when
  `tree-sitter` is installed in the Python that runs the hook.
- On demand: `/complexity path/to/file`, or `complexity-guard path/to/file [--json]`.

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
