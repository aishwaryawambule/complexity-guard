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
