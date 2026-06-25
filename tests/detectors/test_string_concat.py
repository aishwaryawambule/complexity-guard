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
