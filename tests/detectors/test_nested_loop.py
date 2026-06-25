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

CONST_TUPLE = """
def fn():
    for a in (1, 2):
        for b in (3, 4):
            pass
"""

def test_constant_tuple_nested_loop_not_flagged():
    assert detect_nested_loop(_tree(CONST_TUPLE)) == []
