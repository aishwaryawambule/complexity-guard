import ast
from complexity_guard.detectors.loop_invariant import detect_loop_invariant_call

def _tree(src):
    return ast.parse(src)

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

BARE_SIDE_EFFECT = """
def run(items):
    for x in items:
        emit()
"""

def test_bare_side_effect_call_not_flagged():
    assert detect_loop_invariant_call(_tree(BARE_SIDE_EFFECT)) == []

USES_BODY_ASSIGNED = """
def run(items):
    for x in items:
        val = transform(x)
        out = process(val)
"""

def test_call_uses_body_assigned_name_not_flagged():
    assert detect_loop_invariant_call(_tree(USES_BODY_ASSIGNED)) == []

DYNAMIC_DISPATCH = """
def apply_all(fns, x):
    out = []
    for fn in fns:
        out.append(fn(x))
    return out
"""

def test_dynamic_dispatch_not_flagged():
    # The callee `fn` is itself the loop variable, so it differs each
    # iteration — not loop-invariant.
    assert detect_loop_invariant_call(_tree(DYNAMIC_DISPATCH)) == []

INPLACE_MUTATION = """
def pick(scored, max_pages):
    chosen = []
    for score, p in scored:
        if len(chosen) >= max_pages:
            break
        chosen.append(p)
    return chosen
"""

def test_call_on_inplace_mutated_name_not_flagged():
    # `len(chosen)` is NOT invariant: chosen.append() grows it each iteration.
    assert detect_loop_invariant_call(_tree(INPLACE_MUTATION)) == []

FRESH_CONTAINER = """
def group(items):
    out = []
    for x in items:
        bucket = set()
        bucket.add(x)
        out.append(bucket)
    return out
"""

def test_fresh_container_constructor_not_flagged():
    # `set()` builds a new object each iteration; it can't be hoisted out.
    assert detect_loop_invariant_call(_tree(FRESH_CONTAINER)) == []
