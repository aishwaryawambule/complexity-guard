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
