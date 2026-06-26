import ast
from complexity_guard.detectors.repeated_sort import detect_repeated_sort_in_loop

def _tree(src):
    return ast.parse(src)

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


# A `for x in sorted(a):` evaluates the sort ONCE in the enclosing scope, not per
# iteration — so a sort sitting in a *top-level* loop's iterable is not repeated.
ITER_ONCE = """
def process(a):
    for x in sorted(a):
        print(x)
"""

# ...but the same sort inside a loop that is itself nested DOES run once per outer
# iteration, so it must still be flagged.
ITER_NESTED = """
def process(a, n):
    for i in range(n):
        for x in sorted(a):
            print(x)
"""


def test_sort_in_top_level_loop_iterable_not_flagged():
    assert detect_repeated_sort_in_loop(_tree(ITER_ONCE)) == []


def test_sort_in_nested_loop_iterable_is_flagged():
    f = detect_repeated_sort_in_loop(_tree(ITER_NESTED))
    assert len(f) == 1
    assert f[0].detector == "repeated-sort-in-loop"
