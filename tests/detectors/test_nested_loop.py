import ast
from complexity_guard.detectors.nested_loop import detect_nested_loop

def _tree(src):
    return ast.parse(src)

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

CONST_TUPLE = """
def fn():
    for a in (1, 2):
        for b in (3, 4):
            pass
"""

def test_constant_tuple_nested_loop_not_flagged():
    assert detect_nested_loop(_tree(CONST_TUPLE)) == []

# Inner loop over an adjacency list (`graph[u]`) -> amortized linear, not O(n^2).
ADJACENCY = """
def bfs(graph, start):
    seen = set()
    queue = [start]
    while queue:
        u = queue.pop()
        for v in graph[u]:
            if v not in seen:
                seen.add(v)
                queue.append(v)
"""

def test_adjacency_traversal_not_flagged():
    assert detect_nested_loop(_tree(ADJACENCY)) == []

# `graph[u] or []` (default-empty guard) is still a partition traversal.
ADJACENCY_OR = """
def walk(graph, start):
    for u in graph:
        for v in graph[u] or []:
            use(u, v)
"""

def test_partition_with_or_default_not_flagged():
    assert detect_nested_loop(_tree(ADJACENCY_OR)) == []

# Inner loop ranges over an *independent* dimension (a per-row width), not the
# outer collection -> O(rows*width), not O(n^2). Must NOT be flagged.
INDEPENDENT_DIMS = """
def fit(points, dim):
    for p in points:
        for d in range(dim):
            work(p, d)
"""

def test_independent_dimensions_not_flagged():
    assert detect_nested_loop(_tree(INDEPENDENT_DIMS)) == []
