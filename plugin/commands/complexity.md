---
description: Analyze a file's algorithmic complexity (Big-O smells + LLM anti-patterns)
argument-hint: <path/to/file>
allowed-tools: Bash(PYTHONPATH=* * -m complexity_guard.cli *)
---

Run the bundled analyzer and summarize the findings — group by function, and for
each smell give the line, the estimated complexity, and the suggested fix.

The interpreter mirrors the hook: it launches under plain `python3`, then the CLI
re-execs into `COMPLEXITY_GUARD_PYTHON` when that's set (point it at a 3.11+ python
with tree-sitter, e.g. a venv). The override lives in the CLI rather than on the
command line on purpose — Claude Code's permission check blocks a Bash command that
contains a `${...}` shell expansion outside auto-accept mode, so the command must
stay static.

!`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/lib" python3 -m complexity_guard.cli $ARGUMENTS`
