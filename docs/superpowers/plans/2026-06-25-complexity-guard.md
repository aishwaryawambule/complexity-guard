# Complexity Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude Code plugin whose `PostToolUse` hook flags the *algorithmic* inefficiency (Big-O smells + LLM anti-patterns) of Python the model writes, the moment it's written.

**Architecture:** A standalone Python package (`complexity_guard`) parses source into an AST and runs a set of pure detector functions, each returning `Finding`s; `analyze()` orchestrates them; a CLI prints findings; a thin `PostToolUse` hook runs `analyze()` on written `.py` files and surfaces an advisory note; a plugin manifest + `/complexity` command package it for Claude Code.

**Tech Stack:** Python 3.11+, stdlib `ast` only (no third-party deps in the analyzer), pytest, Claude Code plugin/hook format.

## Global Constraints

- Python 3.11+; analyzer core uses **stdlib `ast` only** — no third-party runtime deps.
- Detectors are **pure**: `detect_x(tree: ast.Module) -> list[Finding]`, no I/O. They assume `annotate_parents(tree)` was already called.
- The `Finding` dataclass is the single output type, fields exactly: `detector: str`, `lineno: int`, `complexity: str`, `message: str`, `suggestion: str`, `function: str | None = None`, `severity: str = "warning"`.
- Complexity labels are **heuristic estimates with named evidence**, never claims of certainty (spec §2 honesty constraint).
- The hook is **advisory** — it prints findings and always exits 0; it never blocks.
- v1 is **Python only**.
- Commit after every task. Conventional Commits (`feat:`, `test:`, `chore:`).
- Package import name: `complexity_guard`. CLI entry point: `complexity-guard`.

## File Structure

```
complexity-guard/
  pyproject.toml
  src/complexity_guard/
    __init__.py
    models.py            # Finding dataclass
    parser.py            # parse(source) -> ast.Module
    astutils.py          # annotate_parents, enclosing_loops, loop_depth, enclosing_function(_name), iter_functions
    detectors/
      __init__.py        # DETECTORS registry
      nested_loop.py
      membership.py
      recursion.py
      string_concat.py
      repeated_sort.py
      loop_invariant.py
      bigo.py
    analyze.py           # analyze(source) -> list[Finding]
    cli.py               # complexity-guard CLI
  hooks/posttooluse.py   # Claude Code PostToolUse hook
  plugin/
    .claude-plugin/plugin.json
    hooks/hooks.json
    commands/complexity.md
  tests/                 # mirrors src for pure modules
```

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `src/complexity_guard/__init__.py`, `tests/test_smoke.py`

**Interfaces:**
- Produces: an installable package (`pip install -e .`) and a working `pytest`.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "complexity-guard"
version = "0.1.0"
description = "Flags algorithmic inefficiency of AI-written Python at write time"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
complexity-guard = "complexity_guard.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]
```

- [ ] **Step 2: Create `src/complexity_guard/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Create `tests/test_smoke.py`**

```python
def test_smoke():
    import complexity_guard
    assert complexity_guard.__version__ == "0.1.0"
```

- [ ] **Step 4: Install and test**

Run: `python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]" && pytest`
Expected: 1 passing test.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: scaffold complexity-guard package + pytest"
```

---

### Task 2: Finding model + parser

**Files:**
- Create: `src/complexity_guard/models.py`, `src/complexity_guard/parser.py`, `tests/test_parser.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Finding` with fields `detector, lineno, complexity, message, suggestion, function=None, severity="warning"`.
  - `parse(source: str) -> ast.Module` — wraps `ast.parse`; raises `SyntaxError` on bad input.

- [ ] **Step 1: Write the failing test**

`tests/test_parser.py`:
```python
import ast
import pytest
from complexity_guard.parser import parse
from complexity_guard.models import Finding

def test_parse_returns_module():
    tree = parse("x = 1\n")
    assert isinstance(tree, ast.Module)

def test_parse_raises_on_syntax_error():
    with pytest.raises(SyntaxError):
        parse("def (:\n")

def test_finding_defaults():
    f = Finding(detector="d", lineno=3, complexity="O(n)", message="m", suggestion="s")
    assert f.function is None
    assert f.severity == "warning"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_parser.py -q`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement `src/complexity_guard/models.py`**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    detector: str
    lineno: int
    complexity: str
    message: str
    suggestion: str
    function: str | None = None
    severity: str = "warning"
```

- [ ] **Step 4: Implement `src/complexity_guard/parser.py`**

```python
import ast


def parse(source: str) -> ast.Module:
    """Parse Python source into a module AST. Raises SyntaxError on bad input."""
    return ast.parse(source)
```

- [ ] **Step 5: Run to verify pass**

Run: `pytest tests/test_parser.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: Finding model + source parser"
```

---

### Task 3: AST utilities

**Files:**
- Create: `src/complexity_guard/astutils.py`, `tests/test_astutils.py`

**Interfaces:**
- Consumes: stdlib `ast`.
- Produces:
  - `annotate_parents(tree: ast.AST) -> None` — sets `.parent` on every child node (idempotent).
  - `enclosing_loops(node: ast.AST) -> list[ast.AST]` — `For`/`While` ancestors, innermost-first.
  - `loop_depth(node: ast.AST) -> int` — `len(enclosing_loops(node))`.
  - `enclosing_function(node) -> ast.AST | None` — nearest `FunctionDef`/`AsyncFunctionDef` ancestor.
  - `enclosing_function_name(node) -> str | None`.
  - `iter_functions(tree) -> list[ast.AST]` — all `FunctionDef`/`AsyncFunctionDef` nodes.

- [ ] **Step 1: Write the failing test**

`tests/test_astutils.py`:
```python
import ast
from complexity_guard import astutils as A

SRC = """
def outer():
    for i in range(10):
        for j in range(10):
            x = i + j
"""

def _tree(src):
    t = ast.parse(src)
    A.annotate_parents(t)
    return t

def test_loop_depth_of_inner_body():
    t = _tree(SRC)
    assigns = [n for n in ast.walk(t) if isinstance(n, ast.Assign)]
    assert A.loop_depth(assigns[0]) == 2

def test_enclosing_function_name():
    t = _tree(SRC)
    assigns = [n for n in ast.walk(t) if isinstance(n, ast.Assign)]
    assert A.enclosing_function_name(assigns[0]) == "outer"

def test_iter_functions():
    t = _tree(SRC)
    assert [f.name for f in A.iter_functions(t)] == ["outer"]
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_astutils.py -q`
Expected: FAIL — `astutils` not found.

- [ ] **Step 3: Implement `src/complexity_guard/astutils.py`**

```python
import ast

LOOP_TYPES = (ast.For, ast.While)
FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)


def annotate_parents(tree: ast.AST) -> None:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child.parent = parent


def enclosing_loops(node: ast.AST) -> list[ast.AST]:
    loops = []
    cur = getattr(node, "parent", None)
    while cur is not None:
        if isinstance(cur, LOOP_TYPES):
            loops.append(cur)
        cur = getattr(cur, "parent", None)
    return loops


def loop_depth(node: ast.AST) -> int:
    return len(enclosing_loops(node))


def enclosing_function(node: ast.AST):
    cur = getattr(node, "parent", None)
    while cur is not None:
        if isinstance(cur, FUNC_TYPES):
            return cur
        cur = getattr(cur, "parent", None)
    return None


def enclosing_function_name(node: ast.AST):
    func = enclosing_function(node)
    return func.name if func is not None else None


def iter_functions(tree: ast.AST) -> list[ast.AST]:
    return [n for n in ast.walk(tree) if isinstance(n, FUNC_TYPES)]
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_astutils.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: AST utilities — parents, loops, enclosing function"
```

---

### Task 4: Detector — nested-loop (+ detectors package)

**Files:**
- Create: `src/complexity_guard/detectors/__init__.py`, `src/complexity_guard/detectors/nested_loop.py`, `tests/detectors/test_nested_loop.py`

**Interfaces:**
- Consumes: `Finding`, `astutils` (`loop_depth`, `enclosing_function_name`).
- Produces: `detect_nested_loop(tree: ast.Module) -> list[Finding]`. Establishes the detector signature all later detectors follow.

- [ ] **Step 1: Write the failing test**

`tests/detectors/test_nested_loop.py`:
```python
import ast
from complexity_guard import astutils as A
from complexity_guard.detectors.nested_loop import detect_nested_loop

def _tree(src):
    t = ast.parse(src); A.annotate_parents(t); return t

BAD = """
def dupes(items):
    out = []
    for a in items:
        for b in items:
            if a == b:
                out.append(a)
    return out
"""

CLEAN = """
def total(items):
    s = 0
    for a in items:
        s += a
    return s
"""

def test_flags_nested_loop():
    f = detect_nested_loop(_tree(BAD))
    assert len(f) == 1
    assert f[0].detector == "nested-loop"
    assert f[0].complexity == "O(n^2)"
    assert f[0].function == "dupes"

def test_clean_single_loop_not_flagged():
    assert detect_nested_loop(_tree(CLEAN)) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/detectors/test_nested_loop.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/complexity_guard/detectors/__init__.py`** (registry stub — filled in Task 11)

```python
DETECTORS = []
```

- [ ] **Step 4: Implement `src/complexity_guard/detectors/nested_loop.py`**

```python
import ast
from ..models import Finding
from ..astutils import loop_depth, enclosing_function_name

LOOP_TYPES = (ast.For, ast.While)


def detect_nested_loop(tree: ast.Module) -> list[Finding]:
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, LOOP_TYPES) and loop_depth(node) >= 1:
            findings.append(Finding(
                detector="nested-loop",
                lineno=node.lineno,
                complexity="O(n^2)",
                message="loop nested inside another loop",
                suggestion="if you're matching items across the loops, a set/dict lookup can drop this to O(n)",
                function=enclosing_function_name(node),
            ))
    return findings
```

- [ ] **Step 5: Run to verify pass**

Run: `pytest tests/detectors/test_nested_loop.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: nested-loop detector + detectors package"
```

---

### Task 5: Detector — membership-in-loop

**Files:**
- Create: `src/complexity_guard/detectors/membership.py`, `tests/detectors/test_membership.py`

**Interfaces:**
- Consumes: `Finding`, `astutils` (`loop_depth`, `enclosing_function`, `enclosing_function_name`, `iter_functions`).
- Produces: `detect_membership_in_loop(tree) -> list[Finding]`. Flags `x in <name>` inside a loop where `<name>` is assigned a list within the enclosing function.

- [ ] **Step 1: Write the failing test**

`tests/detectors/test_membership.py`:
```python
import ast
from complexity_guard import astutils as A
from complexity_guard.detectors.membership import detect_membership_in_loop

def _tree(src):
    t = ast.parse(src); A.annotate_parents(t); return t

BAD = """
def common(a, b):
    seen = list(b)
    out = []
    for x in a:
        if x in seen:
            out.append(x)
    return out
"""

CLEAN = """
def common(a, b):
    seen = set(b)
    out = []
    for x in a:
        if x in seen:
            out.append(x)
    return out
"""

def test_flags_list_membership_in_loop():
    f = detect_membership_in_loop(_tree(BAD))
    assert len(f) == 1
    assert f[0].detector == "membership-in-loop"
    assert "seen" in f[0].message

def test_set_membership_not_flagged():
    assert detect_membership_in_loop(_tree(CLEAN)) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/detectors/test_membership.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/complexity_guard/detectors/membership.py`**

```python
import ast
from ..models import Finding
from ..astutils import loop_depth, enclosing_function, enclosing_function_name, iter_functions


def _list_names(func: ast.AST) -> set[str]:
    names: set[str] = set()
    for n in ast.walk(func):
        if isinstance(n, ast.Assign):
            v = n.value
            is_list = isinstance(v, (ast.List, ast.ListComp)) or (
                isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "list"
            )
            if is_list:
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        names.add(t.id)
    return names


def detect_membership_in_loop(tree: ast.Module) -> list[Finding]:
    list_names_by_func = {f: _list_names(f) for f in iter_functions(tree)}
    findings = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Compare) and len(node.ops) == 1
                and isinstance(node.ops[0], ast.In) and loop_depth(node) >= 1):
            comp = node.comparators[0]
            if isinstance(comp, ast.Name):
                func = enclosing_function(node)
                if func is not None and comp.id in list_names_by_func.get(func, set()):
                    findings.append(Finding(
                        detector="membership-in-loop",
                        lineno=node.lineno,
                        complexity="O(n^2)",
                        message=f"membership test `... in {comp.id}` inside a loop ({comp.id} is a list)",
                        suggestion=f"build `{comp.id}` as a set for O(1) lookups",
                        function=enclosing_function_name(node),
                    ))
    return findings
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/detectors/test_membership.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: membership-in-loop detector"
```

---

### Task 6: Detector — recursion-no-memo

**Files:**
- Create: `src/complexity_guard/detectors/recursion.py`, `tests/detectors/test_recursion.py`

**Interfaces:**
- Consumes: `Finding`, `astutils` (`iter_functions`).
- Produces: `detect_recursion_no_memo(tree) -> list[Finding]`. Flags a function that calls itself ≥2 times and has no `cache`/`lru_cache` decorator.

- [ ] **Step 1: Write the failing test**

`tests/detectors/test_recursion.py`:
```python
import ast
from complexity_guard import astutils as A
from complexity_guard.detectors.recursion import detect_recursion_no_memo

def _tree(src):
    t = ast.parse(src); A.annotate_parents(t); return t

BAD = """
def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)
"""

MEMOED = """
import functools
@functools.cache
def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)
"""

def test_flags_naive_recursion():
    f = detect_recursion_no_memo(_tree(BAD))
    assert len(f) == 1
    assert f[0].detector == "recursion-no-memo"
    assert f[0].function == "fib"

def test_cached_recursion_not_flagged():
    assert detect_recursion_no_memo(_tree(MEMOED)) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/detectors/test_recursion.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/complexity_guard/detectors/recursion.py`**

```python
import ast
from ..models import Finding
from ..astutils import iter_functions

CACHE_NAMES = {"cache", "lru_cache"}


def _has_cache_decorator(func: ast.AST) -> bool:
    for d in func.decorator_list:
        target = d.func if isinstance(d, ast.Call) else d
        if isinstance(target, ast.Name) and target.id in CACHE_NAMES:
            return True
        if isinstance(target, ast.Attribute) and target.attr in CACHE_NAMES:
            return True
    return False


def detect_recursion_no_memo(tree: ast.Module) -> list[Finding]:
    findings = []
    for func in iter_functions(tree):
        self_calls = sum(
            1 for n in ast.walk(func)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == func.name
        )
        if self_calls >= 2 and not _has_cache_decorator(func):
            findings.append(Finding(
                detector="recursion-no-memo",
                lineno=func.lineno,
                complexity="O(2^n)",
                message=f"`{func.name}` calls itself {self_calls}x with no memoization",
                suggestion="add @functools.cache (or a memo dict) to avoid recomputing subproblems",
                function=func.name,
            ))
    return findings
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/detectors/test_recursion.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: recursion-no-memo detector"
```

---

### Task 7: Detector — string-concat-in-loop

**Files:**
- Create: `src/complexity_guard/detectors/string_concat.py`, `tests/detectors/test_string_concat.py`

**Interfaces:**
- Consumes: `Finding`, `astutils` (`loop_depth`, `enclosing_function`, `enclosing_function_name`, `iter_functions`).
- Produces: `detect_string_concat_in_loop(tree) -> list[Finding]`. Flags `name += ...` inside a loop where `name` was initialized to a string literal in the enclosing function.

- [ ] **Step 1: Write the failing test**

`tests/detectors/test_string_concat.py`:
```python
import ast
from complexity_guard import astutils as A
from complexity_guard.detectors.string_concat import detect_string_concat_in_loop

def _tree(src):
    t = ast.parse(src); A.annotate_parents(t); return t

BAD = """
def join(items):
    s = ""
    for x in items:
        s += str(x)
    return s
"""

CLEAN = """
def join(items):
    parts = []
    for x in items:
        parts.append(str(x))
    return "".join(parts)
"""

def test_flags_string_concat_in_loop():
    f = detect_string_concat_in_loop(_tree(BAD))
    assert len(f) == 1
    assert f[0].detector == "string-concat-in-loop"

def test_join_pattern_not_flagged():
    assert detect_string_concat_in_loop(_tree(CLEAN)) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/detectors/test_string_concat.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/complexity_guard/detectors/string_concat.py`**

```python
import ast
from ..models import Finding
from ..astutils import loop_depth, enclosing_function, enclosing_function_name, iter_functions


def _str_names(func: ast.AST) -> set[str]:
    names: set[str] = set()
    for n in ast.walk(func):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
    return names


def detect_string_concat_in_loop(tree: ast.Module) -> list[Finding]:
    str_names_by_func = {f: _str_names(f) for f in iter_functions(tree)}
    findings = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add)
                and isinstance(node.target, ast.Name) and loop_depth(node) >= 1):
            func = enclosing_function(node)
            if func is not None and node.target.id in str_names_by_func.get(func, set()):
                findings.append(Finding(
                    detector="string-concat-in-loop",
                    lineno=node.lineno,
                    complexity="O(n^2)",
                    message=f"building string `{node.target.id}` with += inside a loop",
                    suggestion="append pieces to a list and ''.join() once after the loop",
                    function=enclosing_function_name(node),
                ))
    return findings
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/detectors/test_string_concat.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: string-concat-in-loop detector"
```

---

### Task 8: Detector — repeated-sort-in-loop

**Files:**
- Create: `src/complexity_guard/detectors/repeated_sort.py`, `tests/detectors/test_repeated_sort.py`

**Interfaces:**
- Consumes: `Finding`, `astutils` (`loop_depth`, `enclosing_function_name`).
- Produces: `detect_repeated_sort_in_loop(tree) -> list[Finding]`. Flags `sorted(...)` or `.sort(...)` calls inside a loop.

- [ ] **Step 1: Write the failing test**

`tests/detectors/test_repeated_sort.py`:
```python
import ast
from complexity_guard import astutils as A
from complexity_guard.detectors.repeated_sort import detect_repeated_sort_in_loop

def _tree(src):
    t = ast.parse(src); A.annotate_parents(t); return t

BAD = """
def process(rows):
    out = []
    for r in rows:
        ordered = sorted(r)
        out.append(ordered)
    return out
"""

CLEAN = """
def process(rows):
    return [r[0] for r in rows]
"""

def test_flags_sort_in_loop():
    f = detect_repeated_sort_in_loop(_tree(BAD))
    assert len(f) == 1
    assert f[0].detector == "repeated-sort-in-loop"
    assert f[0].complexity == "O(n^2 log n)"

def test_no_sort_not_flagged():
    assert detect_repeated_sort_in_loop(_tree(CLEAN)) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/detectors/test_repeated_sort.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/complexity_guard/detectors/repeated_sort.py`**

```python
import ast
from ..models import Finding
from ..astutils import loop_depth, enclosing_function_name


def detect_repeated_sort_in_loop(tree: ast.Module) -> list[Finding]:
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and loop_depth(node) >= 1:
            f = node.func
            is_sort = (isinstance(f, ast.Name) and f.id == "sorted") or (
                isinstance(f, ast.Attribute) and f.attr == "sort")
            if is_sort:
                findings.append(Finding(
                    detector="repeated-sort-in-loop",
                    lineno=node.lineno,
                    complexity="O(n^2 log n)",
                    message="sorting inside a loop",
                    suggestion="if the data doesn't change between iterations, sort once before the loop",
                    function=enclosing_function_name(node),
                ))
    return findings
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/detectors/test_repeated_sort.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: repeated-sort-in-loop detector"
```

---

### Task 9: Detector — loop-invariant-call

**Files:**
- Create: `src/complexity_guard/detectors/loop_invariant.py`, `tests/detectors/test_loop_invariant.py`

**Interfaces:**
- Consumes: `Finding`, `astutils` (`enclosing_loops`, `loop_depth`, `enclosing_function_name`).
- Produces: `detect_loop_invariant_call(tree) -> list[Finding]`. Flags a `name(...)` call inside a `for` loop whose arguments use none of the enclosing loop targets. Severity `"info"` (lower confidence).

- [ ] **Step 1: Write the failing test**

`tests/detectors/test_loop_invariant.py`:
```python
import ast
from complexity_guard import astutils as A
from complexity_guard.detectors.loop_invariant import detect_loop_invariant_call

def _tree(src):
    t = ast.parse(src); A.annotate_parents(t); return t

BAD = """
def run(items, cfg):
    out = []
    for x in items:
        base = compute(cfg)
        out.append(x + base)
    return out
"""

CLEAN = """
def run(items, cfg):
    out = []
    for x in items:
        out.append(transform(x))
    return out
"""

def test_flags_loop_invariant_call():
    f = detect_loop_invariant_call(_tree(BAD))
    assert len(f) == 1
    assert f[0].detector == "loop-invariant-call"
    assert f[0].severity == "info"

def test_call_using_loop_var_not_flagged():
    assert detect_loop_invariant_call(_tree(CLEAN)) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/detectors/test_loop_invariant.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/complexity_guard/detectors/loop_invariant.py`**

```python
import ast
from ..models import Finding
from ..astutils import enclosing_loops, loop_depth, enclosing_function_name


def _target_names(target: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}


def _names_used(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


def detect_loop_invariant_call(tree: ast.Module) -> list[Finding]:
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and loop_depth(node) >= 1:
            loop_vars: set[str] = set()
            for lp in enclosing_loops(node):
                if isinstance(lp, ast.For):
                    loop_vars |= _target_names(lp.target)
            if not loop_vars:
                continue
            used = _names_used(node) - {node.func.id}
            if used.isdisjoint(loop_vars):
                findings.append(Finding(
                    detector="loop-invariant-call",
                    lineno=node.lineno,
                    severity="info",
                    complexity="wasted O(n) factor",
                    message=f"call `{node.func.id}(...)` inside a loop uses none of the loop variables",
                    suggestion="if it returns the same value each iteration, compute it once before the loop",
                    function=enclosing_function_name(node),
                ))
    return findings
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/detectors/test_loop_invariant.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: loop-invariant-call detector (info severity)"
```

---

### Task 10: Big-O heuristic detector

**Files:**
- Create: `src/complexity_guard/detectors/bigo.py`, `tests/detectors/test_bigo.py`

**Interfaces:**
- Consumes: `Finding`, `astutils` (`iter_functions`).
- Produces: `detect_bigo(tree) -> list[Finding]`. Emits one `bigo` Finding per function whose max loop-nesting depth ≥ 2, labeled `O(n^<depth>)`.

- [ ] **Step 1: Write the failing test**

`tests/detectors/test_bigo.py`:
```python
import ast
from complexity_guard import astutils as A
from complexity_guard.detectors.bigo import detect_bigo

def _tree(src):
    t = ast.parse(src); A.annotate_parents(t); return t

TRIPLE = """
def cube(items):
    for a in items:
        for b in items:
            for c in items:
                pass
"""

SINGLE = """
def lin(items):
    for a in items:
        pass
"""

def test_triple_loop_is_n_cubed():
    f = detect_bigo(_tree(TRIPLE))
    assert len(f) == 1
    assert f[0].detector == "bigo"
    assert f[0].complexity == "O(n^3)"

def test_single_loop_not_reported():
    assert detect_bigo(_tree(SINGLE)) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/detectors/test_bigo.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/complexity_guard/detectors/bigo.py`**

```python
import ast
from ..models import Finding
from ..astutils import iter_functions

LOOP_TYPES = (ast.For, ast.While)


def _loop_depth_within(node: ast.AST, func: ast.AST) -> int:
    depth = 0
    cur = node
    while cur is not None and cur is not func:
        if isinstance(cur, LOOP_TYPES):
            depth += 1
        cur = getattr(cur, "parent", None)
    return depth


def detect_bigo(tree: ast.Module) -> list[Finding]:
    findings = []
    for func in iter_functions(tree):
        loops = [n for n in ast.walk(func) if isinstance(n, LOOP_TYPES)]
        max_depth = max((_loop_depth_within(n, func) for n in loops), default=0)
        if max_depth >= 2:
            findings.append(Finding(
                detector="bigo",
                lineno=func.lineno,
                complexity=f"O(n^{max_depth})",
                message=f"`{func.name}` has loops nested {max_depth} deep",
                suggestion="check whether the nesting is necessary — hashing often removes a level",
                function=func.name,
            ))
    return findings
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/detectors/test_bigo.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: Big-O nesting-depth heuristic detector"
```

---

### Task 11: analyze() orchestrator + registry

**Files:**
- Modify: `src/complexity_guard/detectors/__init__.py`
- Create: `src/complexity_guard/analyze.py`, `tests/test_analyze.py`

**Interfaces:**
- Consumes: all detectors, `parser.parse`, `astutils.annotate_parents`.
- Produces:
  - `detectors.DETECTORS` — the ordered list of all detector functions.
  - `analyze(source: str) -> list[Finding]` — parse (returns `[]` on `SyntaxError`), annotate, run every detector, return findings sorted by `(lineno, detector)`.

- [ ] **Step 1: Write the failing test**

`tests/test_analyze.py`:
```python
from complexity_guard.analyze import analyze

BAD = """
def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)

def dupes(items):
    out = []
    for a in items:
        for b in items:
            if a == b:
                out.append(a)
    return out
"""

def test_analyze_finds_multiple_detectors():
    findings = analyze(BAD)
    kinds = {f.detector for f in findings}
    assert "recursion-no-memo" in kinds
    assert "nested-loop" in kinds
    assert "bigo" in kinds

def test_analyze_sorted_by_line():
    findings = analyze(BAD)
    assert findings == sorted(findings, key=lambda f: (f.lineno, f.detector))

def test_syntax_error_returns_empty():
    assert analyze("def (:\n") == []
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_analyze.py -q`
Expected: FAIL — `analyze` not found.

- [ ] **Step 3: Fill in `src/complexity_guard/detectors/__init__.py`**

```python
from .nested_loop import detect_nested_loop
from .membership import detect_membership_in_loop
from .recursion import detect_recursion_no_memo
from .string_concat import detect_string_concat_in_loop
from .repeated_sort import detect_repeated_sort_in_loop
from .loop_invariant import detect_loop_invariant_call
from .bigo import detect_bigo

DETECTORS = [
    detect_nested_loop,
    detect_membership_in_loop,
    detect_recursion_no_memo,
    detect_string_concat_in_loop,
    detect_repeated_sort_in_loop,
    detect_loop_invariant_call,
    detect_bigo,
]
```

- [ ] **Step 4: Implement `src/complexity_guard/analyze.py`**

```python
from .parser import parse
from .astutils import annotate_parents
from .detectors import DETECTORS
from .models import Finding


def analyze(source: str) -> list[Finding]:
    try:
        tree = parse(source)
    except SyntaxError:
        return []
    annotate_parents(tree)
    findings: list[Finding] = []
    for detect in DETECTORS:
        findings.extend(detect(tree))
    findings.sort(key=lambda f: (f.lineno, f.detector))
    return findings
```

- [ ] **Step 5: Run to verify pass**

Run: `pytest tests/test_analyze.py -q`
Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: analyze() orchestrator + detector registry"
```

---

### Task 12: CLI

**Files:**
- Create: `src/complexity_guard/cli.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `analyze`, `Finding`.
- Produces: `main(argv: list[str] | None = None) -> int`. Usage: `complexity-guard <file.py> [--json]`. Human output prints one line per finding plus a suggestion line; `--json` prints a JSON list. Always returns 0 (advisory). No findings → prints a clean-bill line.

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:
```python
import json
from complexity_guard.cli import main

def _write(tmp_path, src):
    p = tmp_path / "sample.py"
    p.write_text(src)
    return str(p)

BAD = "def f(n):\n    return f(n-1) + f(n-2)\n"

def test_cli_human_output(tmp_path, capsys):
    rc = main([_write(tmp_path, BAD)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "recursion-no-memo" in out

def test_cli_json_output(tmp_path, capsys):
    rc = main([_write(tmp_path, BAD), "--json"])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert rc == 0
    assert any(d["detector"] == "recursion-no-memo" for d in data)

def test_cli_clean_file(tmp_path, capsys):
    rc = main([_write(tmp_path, "x = 1\n")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no complexity" in out.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_cli.py -q`
Expected: FAIL — `cli` not found.

- [ ] **Step 3: Implement `src/complexity_guard/cli.py`**

```python
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from .analyze import analyze


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="complexity-guard")
    parser.add_argument("file")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    source = Path(args.file).read_text()
    findings = analyze(source)

    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
        return 0

    if not findings:
        print(f"✓ {args.file}: no complexity smells found")
        return 0

    for f in findings:
        print(f"{args.file}:{f.lineno}  [{f.detector}] {f.complexity} — {f.message}")
        print(f"    ↳ {f.suggestion}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_cli.py -q`
Expected: PASS.

- [ ] **Step 5: Smoke-test the entry point**

Run: `printf 'def f(n):\n    return f(n-1)+f(n-2)\n' > /tmp/s.py && complexity-guard /tmp/s.py`
Expected: a line mentioning `recursion-no-memo`.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: complexity-guard CLI (human + --json)"
```

---

### Task 13: PostToolUse hook

**Files:**
- Create: `hooks/posttooluse.py`, `tests/test_hook.py`

**Interfaces:**
- Consumes: `analyze`.
- Produces: a hook script. Reads Claude Code's `PostToolUse` JSON from stdin (`{"tool_input": {"file_path": "..."}}`), and if the touched file is `.py`, runs `analyze` on its contents and prints an advisory block. Exits 0 always. A `run(payload: dict) -> str` function holds the logic so it is unit-testable without stdin.

> **Verification note for the implementer:** the exact stdin schema (`tool_input.file_path`) is Claude Code's current `PostToolUse` contract; confirm the field name against the installed Claude Code hooks docs and adjust the `payload["tool_input"]["file_path"]` access if it differs. The `run()` function isolates this so only one line changes.

- [ ] **Step 1: Write the failing test**

`tests/test_hook.py`:
```python
import importlib.util
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "posttooluse.py"

def _load():
    spec = importlib.util.spec_from_file_location("posttooluse", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_hook_reports_findings(tmp_path):
    f = tmp_path / "s.py"
    f.write_text("def g(n):\n    return g(n-1)+g(n-2)\n")
    mod = _load()
    out = mod.run({"tool_input": {"file_path": str(f)}})
    assert "recursion-no-memo" in out

def test_hook_ignores_non_python():
    mod = _load()
    assert mod.run({"tool_input": {"file_path": "README.md"}}) == ""

def test_hook_handles_missing_file():
    mod = _load()
    assert mod.run({"tool_input": {"file_path": "/nope/x.py"}}) == ""
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_hook.py -q`
Expected: FAIL — hook file not found.

- [ ] **Step 3: Implement `hooks/posttooluse.py`**

```python
#!/usr/bin/env python3
"""Claude Code PostToolUse hook: advisory algorithmic-complexity notes for written Python."""
import json
import sys
from complexity_guard.analyze import analyze


def run(payload: dict) -> str:
    path = (payload.get("tool_input") or {}).get("file_path", "")
    if not path.endswith(".py"):
        return ""
    try:
        source = open(path, encoding="utf-8").read()
    except OSError:
        return ""
    findings = analyze(source)
    if not findings:
        return ""
    lines = ["⚠️ Complexity Guard:"]
    for f in findings:
        lines.append(f"  {path}:{f.lineno} [{f.detector}] {f.complexity} — {f.message}")
        lines.append(f"      ↳ {f.suggestion}")
    return "\n".join(lines)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    note = run(payload)
    if note:
        print(note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_hook.py -q`
Expected: PASS.

- [ ] **Step 5: Smoke-test via stdin**

Run: `printf 'def g(n):\n    return g(n-1)+g(n-2)\n' > /tmp/s.py && echo '{"tool_input":{"file_path":"/tmp/s.py"}}' | python3 hooks/posttooluse.py`
Expected: a `⚠️ Complexity Guard:` block mentioning `recursion-no-memo`.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: PostToolUse hook (advisory complexity notes)"
```

---

### Task 14: Plugin packaging + /complexity command

**Files:**
- Create: `plugin/.claude-plugin/plugin.json`, `plugin/hooks/hooks.json`, `plugin/commands/complexity.md`, `README.md`

**Interfaces:**
- Consumes: the installed `complexity-guard` CLI and `hooks/posttooluse.py`.
- Produces: a Claude Code plugin that wires the `PostToolUse` hook and adds the `/complexity` slash command.

> **Verification note for the implementer:** plugin manifest and hook-config field names follow Claude Code's current plugin format. Before finalizing, confirm against the installed Claude Code plugin docs (the `plugins/README.md` in the claude-code repo) and adjust `plugin.json` / `hooks.json` keys if the schema differs. The hook command path uses `${CLAUDE_PLUGIN_ROOT}`.

- [ ] **Step 1: Create `plugin/.claude-plugin/plugin.json`**

```json
{
  "name": "complexity-guard",
  "version": "0.1.0",
  "description": "Flags algorithmic (Big-O) inefficiency of written Python at write time."
}
```

- [ ] **Step 2: Create `plugin/hooks/hooks.json`**

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          { "type": "command", "command": "python3 ${CLAUDE_PLUGIN_ROOT}/../hooks/posttooluse.py" }
        ]
      }
    ]
  }
}
```

- [ ] **Step 3: Create `plugin/commands/complexity.md`**

```markdown
---
description: Analyze a Python file's algorithmic complexity (Big-O smells + LLM anti-patterns)
argument-hint: <path/to/file.py>
---

Run `complexity-guard $ARGUMENTS` and summarize the findings for me — group by
function, and for each smell give the line, the estimated complexity, and the
suggested fix.
```

- [ ] **Step 4: Create `README.md`**

```markdown
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
```

- [ ] **Step 5: Verify the suite still passes**

Run: `pytest -q`
Expected: all tests pass (packaging adds no Python under test, but confirm nothing broke).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: Claude Code plugin packaging + /complexity command"
```

---

## Self-Review

**Spec coverage:**
- Motive / write-time flagging (spec §1) → Task 13 hook + Task 14 plugin ✓
- Prior-art differentiation: algorithmic, not structural (§2) → the 6 detectors (Tasks 4–9) + Big-O (Task 10) ✓
- All 6 detectors (§3a) → Tasks 4,5,6,7,8,9 ✓
- Big-O heuristic (§3b) → Task 10 ✓
- Honesty constraint (heuristic, not proof) → wording in detector messages + Big-O suggestion + README ✓
- Integration: advisory hook + `/complexity` + plugin (§4) → Tasks 13, 14 ✓
- Architecture/modules (§5) → file structure matches; Tasks 2,3 (models/parser/astutils), 4–10 (detectors), 11 (analyze), 12 (cli) ✓
- Tech: Python 3.11+, stdlib ast only, pytest (§6) → Task 1 config, no third-party deps anywhere ✓
- v1 scope incl. CLI human+json, advisory hook (§7) → Tasks 12, 13 ✓
- Non-goals (no other langs, no blocking, no empirical) (§9) → honored; nothing runs user code, hook exits 0 ✓
- Success criteria (§8) → Task 4–10 bad/clean test pairs; Task 12 CLI tests; Task 13 hook test ✓

**Placeholder scan:** No TBD/TODO. Every code step has complete code. The two "verification notes" (Tasks 13, 14) are explicit, scoped pointers to confirm Claude Code's hook/plugin schema — with concrete best-known code provided and the single line to adjust named — not placeholders.

**Type consistency:** `Finding` fields identical across every detector, the CLI (`asdict`), and the hook. Every detector is `detect_*(tree) -> list[Finding]` and is registered in `DETECTORS` (Task 11) exactly as named in its task. `astutils` helpers (`loop_depth`, `enclosing_loops`, `enclosing_function`, `enclosing_function_name`, `iter_functions`, `annotate_parents`) are defined in Task 3 and consumed with matching signatures throughout. `analyze(source) -> list[Finding]` matches its consumers (CLI, hook).

## Notes for the implementer
- Every detector ships with a **bad sample it must flag** and a **clean sample it must not flag** — the false-positive guard is the point of this tool, so never weaken the clean-sample assertion to make a detector pass.
- `loop-invariant-call` is the highest-false-positive detector (spec open question); it's `info` severity by design. If real-world noise is high, the honest fix is to narrow it, not to silence other detectors.
- Deferred per spec §7/§9: JS/TS, empirical measurement, `--block` mode, auto-fix, feeding findings back to Claude as context.
```
