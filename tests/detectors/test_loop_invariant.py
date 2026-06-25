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
