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
