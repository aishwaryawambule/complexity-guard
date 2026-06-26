---
description: Analyze a file's algorithmic complexity (Big-O smells + LLM anti-patterns)
argument-hint: <path/to/file>
allowed-tools: Bash(PYTHONPATH=* python3 -m complexity_guard.cli *)
---

Run the bundled analyzer and summarize the findings — group by function, and for
each smell give the line, the estimated complexity, and the suggested fix:

!`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/lib" python3 -m complexity_guard.cli $ARGUMENTS`
