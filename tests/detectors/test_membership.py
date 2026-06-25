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
