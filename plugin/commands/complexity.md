---
description: Analyze a file's algorithmic complexity (Big-O smells + LLM anti-patterns)
argument-hint: <path/to/file>
allowed-tools: Bash(PYTHONPATH=* * -m complexity_guard.cli *)
---

Run the bundled analyzer and summarize the findings — group by function, and for
each smell give the line, the estimated complexity, and the suggested fix.

The interpreter mirrors the hook: an explicit `COMPLEXITY_GUARD_PYTHON` wins (set
it to a 3.11+ python that has tree-sitter, e.g. a venv), otherwise plain `python3`.

!`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/lib" "${COMPLEXITY_GUARD_PYTHON:-python3}" -m complexity_guard.cli $ARGUMENTS`
