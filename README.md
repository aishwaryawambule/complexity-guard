# Complexity Guard

A Claude Code plugin that flags the *algorithmic* inefficiency of Python the
model writes — Big-O smells and the documented LLM anti-patterns — the moment
it's written.

## Install (local dev)
1. `pip install -e ".[dev]"`
2. Add this plugin directory to Claude Code as a plugin (see Claude Code plugin docs).

## Use
- Automatic: the `PostToolUse` hook prints advisory notes when Claude writes `.py` files.
- On demand: `/complexity path/to/file.py`, or `complexity-guard path/to/file.py [--json]`.

## What it flags
nested loops (O(n²)), `in list` inside a loop, un-memoized recursion, `+=` string
building in loops, sorting in loops, loop-invariant calls, and a nesting-depth
Big-O estimate. Estimates are heuristics with named evidence, not proofs.
