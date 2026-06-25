import ast
from complexity_guard.detectors.bigo import detect_bigo

def _tree(src):
    return ast.parse(src)

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

NESTED_DEF = """
def outer(items):
    for a in items:
        pass
    def inner(items):
        for b in items:
            for c in items:
                pass
"""

def test_nested_function_depth_not_counted_in_outer():
    f = detect_bigo(_tree(NESTED_DEF))
    assert len(f) == 1
    assert f[0].function == "inner"
    assert f[0].complexity == "O(n^2)"

CONST_TUPLE_DOUBLE = """
def fn():
    for a in (1, 2):
        for b in (3, 4):
            pass
"""

def test_constant_tuple_double_nest_not_flagged():
    assert detect_bigo(_tree(CONST_TUPLE_DOUBLE)) == []

# Adjacency-list traversal: the inner loop walks one node's edge list per outer
# step, so total work is O(V+E) -- linear, not O(V^2). Must NOT be flagged.
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
    assert detect_bigo(_tree(ADJACENCY)) == []

# A slice (`arr[i:]`) is a genuine sub-sequence scan -> triangular O(n^2). The
# partition exclusion must NOT swallow this.
TRIANGULAR = """
def f(arr):
    for i in range(len(arr)):
        for x in arr[i:]:
            use(x)
"""

def test_slice_iteration_still_flagged():
    f = detect_bigo(_tree(TRIANGULAR))
    assert len(f) == 1 and f[0].complexity == "O(n^2)"
