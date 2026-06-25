# Complexity Guard — Design Spec

**Date:** 2026-06-25
**Status:** Approved design, pre-implementation
**One-liner:** A Claude Code plugin that flags the *algorithmic* inefficiency of Python the model writes — Big-O smells and the documented LLM anti-patterns — the moment it's written.

## 1. Motive

LLM-generated code is reliably "correct but slow." Research is unambiguous:
LLM solutions average ~62% of human efficiency, with worst cases ~45× slower,
and the root cause is the models' *limited awareness of algorithmic complexity*
(EffiBench, ENAMEL; a published taxonomy of LLM code inefficiencies exists).

The fix belongs **in the loop, at write time** — not in a separate website you
paste into later. When Claude writes a function, you want to know *right then*
that it's an accidental O(n²).

## 2. Prior art & differentiation

The neighborhood is built up — be honest about it:

| Exists | What it does | What it lacks |
|---|---|---|
| Claude Code "code quality gate" hooks (Paul Duvall, ClaudeCodeOptimizer) | `PostToolUse` hooks that flag/block on **cyclomatic** complexity, nesting, length, duplication | Structural complexity only — **no algorithmic Big-O**, no LLM efficiency anti-patterns |
| Complexity Analyzer skills | Cyclomatic + cognitive complexity | Same — structure, not algorithmic efficiency |
| TimeComplexity.ai, AI Big-O analyzers | Paste code → AI estimates Big-O | A separate website; not in the write loop; not LLM-anti-pattern-aware |
| EffiBench / ENAMEL / COFFE | Academic benchmarks of LLM code efficiency | Score *models* on fixed problems; not a workflow tool |

**The gap we fill:** the hook mechanism and *structural* complexity gates exist,
but nothing does **algorithmic (Big-O) efficiency + the specific LLM
anti-patterns, automatically, in the Claude Code write loop.** That sliver is
narrow but real, and it's a genuinely meaty *algorithms* build.

**Honesty constraint (baked into the product):** exact Big-O is undecidable, so
Complexity Guard never *claims certainty*. It flags **patterns with named
evidence** and gives a heuristic estimate — "this *looks* O(n²) because of a loop
nested in a loop over the same data," not "this is O(n²)."

## 3. What it detects

### 3a. AST anti-pattern detectors (the core value)
Each detector walks the AST, matches a pattern, and emits a Finding with a
complexity smell + a concrete fix:

| Detector | AST pattern | Smell | Fix |
|---|---|---|---|
| `nested-loop` | a loop nested inside another loop iterating the same/related data | O(n²) | hash/set approach |
| `membership-in-loop` | `x in <list/tuple>` inside a loop | O(n²) | convert to `set`/`dict` |
| `recursion-no-memo` | function with ≥2 self-calls and no `@cache`/`@lru_cache`/memo | exponential | memoize (`functools.cache`) |
| `loop-invariant-call` | a call inside a loop whose args don't depend on the loop var | wasted O(n) factor | hoist out of the loop |
| `string-concat-in-loop` | `s += <str>` / `s = s + <str>` inside a loop | O(n²) | accumulate in a list + `"".join` |
| `repeated-sort-in-loop` | `sorted()` / `.sort()` called inside a loop | O(n² log n) | sort once, outside |

### 3b. Big-O heuristic
A whole-function estimate from **maximum loop-nesting depth over the inputs**:
depth 0 → `O(1)`, 1 → `O(n)`, 2 → `O(n²)`, 3 → `O(n³)`; recursion patterns are
reported via `recursion-no-memo` rather than the depth estimate. Stated
explicitly as a *structural upper-bound heuristic*, not a proof.

## 4. Integration with Claude Code

- **`PostToolUse` hook** matching `Write|Edit` on `*.py`. After Claude writes
  Python, the hook runs the analyzer on the touched file and surfaces an
  **advisory** note (it does **not** block). Findings are shown so both the user
  and Claude can act.
- **`/complexity` slash command** — analyze a file (or the current selection) on
  demand.
- **Packaged as a Claude Code plugin** bundling the hook config + the slash
  command + the analyzer, so it installs cleanly.

## 5. Architecture

The analyzer is a standalone Python package; the hook/plugin is a thin wrapper.

| Module | Responsibility | Depends on |
|---|---|---|
| `complexity_guard/models.py` | `Finding` dataclass (detector, function, lineno, severity, complexity, message, suggestion) | — |
| `complexity_guard/parser.py` | `parse(source) -> ast.Module` (thin wrapper, syntax-error handling) | stdlib `ast` |
| `complexity_guard/detectors/` | one pure function per detector: `(tree) -> list[Finding]` | `models`, `ast` |
| `complexity_guard/bigo.py` | `estimate(func_node) -> str` nesting-depth Big-O | `ast` |
| `complexity_guard/analyze.py` | run all detectors + bigo over a source string → `list[Finding]` | all of the above |
| `complexity_guard/cli.py` | `complexity-guard <file.py> [--json]` → human or JSON output | `analyze` |
| `hooks/posttooluse.py` | read Claude Code hook JSON from stdin, extract the written `.py` path, run `analyze`, print advisory note | `analyze` |
| plugin manifest + `commands/complexity.md` | plugin packaging + the slash command | the CLI |

Detectors and `bigo` are **pure and fully unit-testable** with pytest — no DOM,
no I/O, no Claude Code needed to test the core.

## 6. Tech

- **Python 3.11+**, stdlib **`ast`** only for the analyzer core (no third-party
  deps) — clean, fast, and your home turf.
- **pytest** for tests (TDD: each detector gets bad-code samples it must flag and
  clean-code samples it must NOT flag).
- The hook is a small Python script invoked by Claude Code; the plugin is
  packaged per Claude Code's plugin format (exact manifest finalized in the plan).

## 7. v1 scope / non-goals

**In v1:** Python only · the 6 detectors above · nesting-depth Big-O heuristic ·
`Finding` model · `analyze()` · CLI (human + `--json`) · advisory `PostToolUse`
hook · `/complexity` command · plugin packaging.

**Later:** JS/TS and other languages · empirical run-and-measure complexity ·
`--block` mode (fail the write until fixed) · auto-applied fixes · feeding
findings back to Claude as `additionalContext` for self-correction.

## 8. Success criteria

1. On known-bad samples (naive recursive Fibonacci, nested-loop dedupe,
   `in list` inside a loop, `+=` string build), the analyzer flags the right
   detector with the right complexity label.
2. On a curated set of clean/optimal equivalents, it emits **no** findings (low
   false-positive rate).
3. `complexity-guard file.py --json` returns a structured findings list; without
   `--json` it prints readable notes.
4. The `PostToolUse` hook runs on a Python Write/Edit and surfaces a note within
   the session, without blocking.

## 9. Non-goals

- Claiming exact/proven Big-O (heuristic + evidence only).
- Blocking Claude in v1 (advisory only).
- Languages other than Python in v1.
- Running the code (no empirical measurement in v1).

## 10. Open questions (for the implementation plan)

- Exact Claude Code plugin manifest + hook config format (verify against current
  docs at plan time).
- Analyze the whole written file vs. only the changed function (v1: whole file).
- Tuning `loop-invariant-call` and `nested-loop` to keep false positives low
  (the two trickiest detectors).
- Whether v1 also feeds findings back to Claude or only displays them to the user.
