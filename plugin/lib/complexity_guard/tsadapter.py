"""Tree-sitter -> normalized index for the structural detectors.

This walks a tree-sitter parse tree once and produces a ``NormalizedIndex`` whose
nodes carry the *same duck-typed attributes* the native (Python ``ast``) structural
detectors read — ``lineno``, ``name``, ``_func``, ``_scaling``, ``_sdepth``,
``_has_sloop_anc``, ``decorator_list`` — so ``_detect_nested_loop``,
``_detect_bigo`` and ``_detect_recursion_no_memo`` run over it unchanged.

Structural-only: every loop is treated as scaling (the signal we report is loop
*nesting*, which is language-agnostic). The per-language semantic detectors
(membership/sort/string-concat) are intentionally not ported here.

Tree-sitter is an optional dependency. If it (or a grammar) is unavailable,
``build_index`` returns None and the caller falls back to "no findings" — the
native Python path never depends on this module.
"""
from .langspec import (
    LOOP_TYPES, FUNC_TYPES, CALL_TYPES, MEMBER_TYPES,
    COUNTING_FOR_TYPES, INT_LITERAL_TYPES, DYNAMIC_BOUND_TYPES,
    COMPARE_TYPES, COMPARE_OPS, RANGE_TYPES, MEMO_NAMES,
    AUGASSIGN_TYPES, CONCAT_OPS, STRING_LIT_TYPES,
    VARDECL_TYPES, SET_TYPE_HINTS, LIST_TYPE_HINTS, SUBSCRIPT_TYPES,
)

# Loop types that re-check a condition rather than iterate a binding (while / until
# / do-while). They contribute a count, but their size identifiers live in the
# condition, not in an iterable.
_WHILE_TYPES = frozenset({
    "while_statement", "while_expression", "while", "do_statement",
    "until", "repeat_statement",
})
# Property / index access whose *base* (not the `.prop` / `[idx]`) is the real
# dimension: `points.length` -> points, `xs.size()` -> xs.
_PROP_BASE_TYPES = (
    MEMBER_TYPES | SUBSCRIPT_TYPES | frozenset({"field_access", "field_expression"})
)
# Wrappers that aren't themselves a dimension (a size accessor around the real one).
_NONDIM_NAMES = frozenset({"len", "range", "Math", "Number", "Array", "size", "length"})

try:
    from tree_sitter import Parser
    from tree_sitter_language_pack import get_language
    TS_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only when the extra is absent
    Parser = None
    get_language = None
    TS_AVAILABLE = False

_IDENT_LEAF = frozenset({
    "identifier", "name", "field_identifier", "type_identifier",
    "property_identifier", "constant",
})


class NNode:
    """A normalized function or loop node, shaped to satisfy the native detectors."""

    __slots__ = (
        "kind", "lineno", "name",
        "_scaling", "_func", "_has_sloop_anc", "_sdepth", "decorator_list",
        "_dim", "_dim_depth", "_has_samedim_anc",
    )

    def __init__(self, kind: str, lineno: int, name: str | None = None):
        self.kind = kind
        self.lineno = lineno
        self.name = name
        self._scaling = True          # structural-only: all loops count as scaling
        self._func = None             # enclosing NNode function (loops)
        self._has_sloop_anc = False   # a scaling loop encloses this loop
        self._sdepth = 0              # scaling-loop nesting depth incl. self, within func
        self.decorator_list = []      # no portable memo-decorator concept; always empty
        self._dim = None              # this loop's dimension id
        self._dim_depth = 0           # same-dimension nesting depth incl. self, within func
        self._has_samedim_anc = False  # a SAME-dimension scaling loop encloses this loop


class NormalizedIndex:
    """Mirror of astutils.TreeIndex, exposing only what the structural detectors use."""

    __slots__ = (
        "functions", "loops", "self_calls", "memoized", "loop_calls", "loop_augs",
        "var_types", "global_var_types",
    )

    def __init__(self):
        self.functions: list[NNode] = []
        self.loops: list[NNode] = []
        self.self_calls: dict[NNode, int] = {}
        self.memoized: set[NNode] = set()  # funcs that reference a memo/cache table
        # calls / `+=` string-concats that occur inside a *scaling* loop, for the
        # semantic detectors. Each entry: (name, receiver, lineno, func_node).
        self.loop_calls: list[tuple] = []
        self.loop_augs: list[tuple] = []  # (lineno, func_node)
        # variable name -> "list" | "set", per function and at file scope (fields).
        # Resolved after the full walk so declaration order doesn't matter.
        self.var_types: dict[NNode, dict] = {}
        self.global_var_types: dict = {}


def _text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", "replace")


def _is_ident_leaf(node) -> bool:
    return node.child_count == 0 and ("identifier" in node.type or node.type in _IDENT_LEAF)


def _first_ident(node):
    """Breadth-first search for the first identifier-like leaf (declaration name)."""
    queue = [node]
    while queue:
        cur = queue.pop(0)
        if _is_ident_leaf(cur):
            return cur
        queue = list(cur.children) + queue
    return None


def _func_name(node, src: bytes) -> str | None:
    nm = node.child_by_field_name("name")
    if nm is None:
        decl = node.child_by_field_name("declarator")  # c / c++
        if decl is not None:
            nm = _first_ident(decl)
    if nm is None:
        # Grammars that expose the name positionally with no field (e.g. kotlin):
        # it's the first named child *only if* that child is a bare identifier.
        # An anonymous function (JS arrow) leads with its parameter list, not an
        # identifier, so this correctly yields None there.
        first = next((c for c in node.children if c.is_named), None)
        if first is not None and _is_ident_leaf(first):
            nm = first
    return _text(nm, src) if nm is not None else None  # anonymous -> None


def _find_comparison(node):
    """Find a relational comparison (`<`, `<=`, ...) with left/right operands."""
    stack = [node]
    while stack:
        cur = stack.pop()
        if cur.type in COMPARE_TYPES and cur.child_by_field_name("left") is not None:
            ops = {c.type for c in cur.children if c.child_count == 0}
            if ops & COMPARE_OPS:
                return cur
        stack.extend(cur.children)
    return None


def _const_bounded_comparison(cmp) -> bool:
    """True for `i < <int literal>` style bounds; False for size/length-dependent ones."""
    left = cmp.child_by_field_name("left")
    right = cmp.child_by_field_name("right")
    if left is None or right is None:
        return False
    types = {left.type, right.type}
    if any(t in DYNAMIC_BOUND_TYPES for t in types):  # i < xs.length / len(xs) / xs.size()
        return False
    return any(t in INT_LITERAL_TYPES for t in types)


def _counting_for_is_bounded(node) -> bool:
    cond = node.child_by_field_name("condition")
    if cond is None:
        # go: the init/condition/update live inside a positional for_clause;
        # a range loop has a range_clause (data-dependent) and no for_clause.
        cond = next((c for c in node.children if c.type == "for_clause"), None)
        if cond is None:
            return False
    cmp = _find_comparison(cond)
    return cmp is not None and _const_bounded_comparison(cmp)


def _rust_range_is_bounded(node) -> bool:
    rng = node.child_by_field_name("value")
    if rng is None or rng.type not in RANGE_TYPES:
        rng = next((c for c in node.children if c.type in RANGE_TYPES), None)
    if rng is None:
        return False
    ends = [c for c in rng.children if c.is_named]
    return len(ends) >= 2 and all(c.type in INT_LITERAL_TYPES for c in ends)


def _loop_is_scaling(node) -> bool:
    """Does this loop's iteration count grow with input size?

    Counting loops bounded by an integer literal don't (``for(i=0;i<3;i++)``,
    rust ``for i in 0..3``); foreach / for-in / while / infinite loops do.
    """
    if node.type in COUNTING_FOR_TYPES:
        return not _counting_for_is_bounded(node)
    if node.type == "for_expression":  # rust `for x in <iter>`
        return not _rust_range_is_bounded(node)
    return True


def _loop_iterable(node):
    """The expression a foreach / for-in / range loop iterates over, or None for
    C-style counting loops (which have no single iterable)."""
    it = node.child_by_field_name("right")        # js/ts for-of, java for-each, ...
    if it is not None:
        return it
    for c in node.children:                        # go: `for _, v := range <expr>`
        if c.type == "range_clause":
            return c.child_by_field_name("right") or c
    return node.child_by_field_name("value")       # rust: `for x in <value>`


def _iterates_partition(node, src: bytes) -> bool:
    """True if the loop iterates a container index ``base[key]`` (adjacency list,
    bucket map), seen through ``a || b`` / ``a ?? b`` / ``a ? b : c`` / parens.

    Such an inner loop walks one partition per outer step, so its total work is
    amortized linear in the whole container — it must not add an O(n^k) nesting
    level. The key is required to be a bare identifier (``graph[u]``), which nails
    the adjacency/bucket pattern while leaving genuine quadratics untouched.
    """
    it = _loop_iterable(node)
    if it is None:
        return False
    stack = [it]
    seen = 0
    while stack and seen < 12:
        cur = stack.pop()
        seen += 1
        t = cur.type
        if t in SUBSCRIPT_TYPES:
            key = cur.child_by_field_name("index")
            if key is None:  # grammars without an `index` field: last named child
                named = [c for c in cur.children if c.is_named]
                key = named[-1] if named else None
            if key is not None and _is_ident_leaf(key):
                return True
        elif t == "parenthesized_expression":
            stack.extend(c for c in cur.children if c.is_named)
        elif t == "binary_expression":  # only logical defaults: `graph[u] || []`
            op = cur.child_by_field_name("operator")
            if op is not None and _text(op, src) in ("||", "??"):
                stack.extend(c for c in cur.children if c.is_named)
        elif t == "ternary_expression":
            stack.extend(c for c in cur.children if c.is_named)
    return False


def _base_idents(node, src: bytes) -> set:
    """Identifiers a size expression depends on, reducing `a.b` / `a[i]` / `a.b()`
    to their base `a` (the dimension), so `points.length` yields {points}."""
    out = set()
    if node is None:
        return out
    stack = [node]
    seen = 0
    while stack and seen < 256:
        cur = stack.pop()
        seen += 1
        if cur.type in _PROP_BASE_TYPES:
            base = None
            for field in ("object", "operand", "argument", "value", "array", "receiver"):
                base = cur.child_by_field_name(field)
                if base is not None:
                    break
            if base is None:
                named = [c for c in cur.children if c.is_named]
                base = named[0] if named else None
            if base is not None:
                stack.append(base)
            continue
        if _is_ident_leaf(cur):
            out.add(_text(cur, src))
            continue
        stack.extend(c for c in cur.children if c.is_named)
    return out


def _loop_dims(node, src: bytes):
    """(loopvars, idset) for a scaling loop: its iteration variable name(s) and the
    base identifiers its iteration count depends on (builtins / own vars removed)."""
    rc = next((c for c in node.children if c.type == "range_clause"), None)

    # C-style counting for (no range_clause): vars from the init, size from the cond.
    if node.type in COUNTING_FOR_TYPES and rc is None:
        loopvars = set()
        init = node.child_by_field_name("initializer") or node.child_by_field_name("init")
        cond = node.child_by_field_name("condition")
        if cond is None:
            fc = next((c for c in node.children if c.type == "for_clause"), None)
            if fc is not None:
                init = init or fc.child_by_field_name("initializer") or fc.child_by_field_name("init")
                cond = fc.child_by_field_name("condition")
        if init is not None:
            lid = _first_ident(init)
            if lid is not None:
                loopvars.add(_text(lid, src))
        ids = _base_idents(cond, src)
        return frozenset(loopvars), frozenset(ids - loopvars - _NONDIM_NAMES)

    # while / until / do-while: size identifiers live in the re-checked condition.
    if node.type in _WHILE_TYPES:
        cond = node.child_by_field_name("condition")
        ids = _base_idents(cond if cond is not None else node, src)
        return frozenset(), frozenset(ids - _NONDIM_NAMES)

    # foreach / for-of / for-in / go range / rust for: a binding over an iterable.
    loopvars = set()
    left = (node.child_by_field_name("left") or node.child_by_field_name("pattern")
            or node.child_by_field_name("name"))
    if left is None and rc is not None:
        left = rc.child_by_field_name("left")
    if left is not None:
        if _is_ident_leaf(left):
            loopvars.add(_text(left, src))
        else:
            for c in left.children:
                if _is_ident_leaf(c):
                    loopvars.add(_text(c, src))
    it = _loop_iterable(node)
    ids = _base_idents(it, src)
    return frozenset(loopvars), frozenset(ids - loopvars - _NONDIM_NAMES)


def _assign_dim(loopvars, idset, enclosing, fresh):
    """Dimension id for a loop: reuse an enclosing scaling loop's dimension when
    their identifier sets intersect (or one references the other's loop variable),
    else a fresh id. ``enclosing`` is (loopvars, idset, dim) tuples, outermost-first."""
    for lv, ids, dim in reversed(enclosing):
        if (idset & ids) or (lv & idset) or (loopvars & ids):
            return dim
    return fresh


def _last_ident(node, src: bytes) -> str | None:
    """The last identifier-like leaf under ``node`` (a call's method/function name)."""
    found = None
    stack = [node]
    while stack:
        cur = stack.pop(0)
        if _is_ident_leaf(cur):
            found = cur
        stack = list(cur.children) + stack
    return _text(found, src) if found is not None else None


def _call_target(node, src: bytes):
    """(invoked_name, receiver) for a call, e.g. ``sort.Slice`` -> ('Slice','sort')."""
    callee = None
    for field in ("function", "name", "method", "constructor"):
        callee = node.child_by_field_name(field)
        if callee is not None:
            break
    if callee is None:
        callee = next((c for c in node.children if c.is_named), None)
    if callee is None:
        return (None, None)
    name = _text(callee, src) if _is_ident_leaf(callee) else _last_ident(callee, src)
    receiver = None
    if not _is_ident_leaf(callee):
        receiver = _first_ident(callee)
        receiver = _text(receiver, src) if receiver is not None else None
    # java/ruby keep the receiver in an `object`/`receiver` field, not the callee
    if receiver is None:
        recv_node = node.child_by_field_name("object") or node.child_by_field_name("receiver")
        if recv_node is not None and _is_ident_leaf(recv_node):
            receiver = _text(recv_node, src)
    return (name, receiver)


def _aug_is_string_concat(node, src: bytes) -> bool:
    """True for `s += "..."` / `$s .= "..."` with a string-literal right-hand side."""
    ops = {_text(c, src) for c in node.children if c.child_count == 0}
    if not (ops & CONCAT_OPS):
        return False
    rhs = node.child_by_field_name("right") or node.child_by_field_name("value")
    if rhs is None:
        named = [c for c in node.children if c.is_named]
        rhs = named[-1] if named else None
    if rhs is None:
        return False
    if rhs.type == "expression_list":  # go wraps the rhs
        inner = [c for c in rhs.children if c.is_named]
        if len(inner) == 1:
            rhs = inner[0]
    return rhs.type in STRING_LIT_TYPES


def _classify_type(text: str | None) -> str | None:
    """Classify a declared type / initializer string as 'list', 'set', or None."""
    if not text:
        return None
    if any(h in text for h in SET_TYPE_HINTS):
        return "set"
    if any(h in text for h in LIST_TYPE_HINTS):
        return "list"
    return None


def _decl_kind(node, src: bytes) -> str | None:
    for field in ("type", "value", "right"):
        child = node.child_by_field_name(field)
        if child is not None:
            kind = _classify_type(_text(child, src))
            if kind:
                return kind
    return _classify_type(_text(node, src))


def _decl_names(node, src: bytes) -> list[str]:
    names = []
    for d in node.children:  # java / c#: variable_declarator(s)
        if d.type in ("variable_declarator", "init_declarator"):
            nm = d.child_by_field_name("name")
            if nm is not None:
                names.append(_text(nm, src))
    if names:
        return names
    left = node.child_by_field_name("left")  # go :=
    if left is not None:
        return [_text(c, src) for c in left.children if _is_ident_leaf(c)] or \
               ([_text(left, src)] if _is_ident_leaf(left) else [])
    for field in ("pattern", "name"):  # rust let / go var_spec
        nm = node.child_by_field_name(field)
        if nm is not None:
            leaf = nm if _is_ident_leaf(nm) else _first_ident(nm)
            if leaf is not None:
                return [_text(leaf, src)]
    return []


def _self_call_name(node, src: bytes) -> str | None:
    """Name of an *unqualified* callee, or None for method/qualified calls.

    Only unqualified self-calls count toward recursion, matching the native
    engine (which ignores ``self.f()`` / ``obj.f()`` style ast.Attribute calls).
    """
    if node.child_by_field_name("object") is not None:    # java / ruby receiver
        return None
    if node.child_by_field_name("receiver") is not None:
        return None
    callee = None
    for field in ("function", "name", "method", "constructor"):
        callee = node.child_by_field_name(field)
        if callee is not None:
            break
    if callee is None:
        # Grammars that expose the callee positionally rather than as a named
        # field (e.g. kotlin / swift call_expression): use the first named child.
        for child in node.children:
            if child.is_named:
                callee = child
                break
    if callee is None or callee.type in MEMBER_TYPES:
        return None
    if _is_ident_leaf(callee):
        return _text(callee, src)
    return None


def build_index(source: str, lang: str):
    """Parse ``source`` as ``lang`` and return a NormalizedIndex, or None.

    None means tree-sitter or the grammar is unavailable; the caller treats that
    as "no findings" rather than an error.
    """
    if not TS_AVAILABLE:
        return None
    try:
        language = get_language(lang)
    except Exception:
        return None
    src = source.encode("utf-8")
    try:
        tree = Parser(language).parse(src)
    except Exception:
        return None

    idx = NormalizedIndex()
    # DFS carrying: enclosing-function chain, global *scaling*-loop depth,
    # scaling-loop depth within the current function, and the enclosing scaling
    # loops' (loopvars, idset, dim) for dimension tracking. Only scaling loops
    # increment these (constant-bounded loops don't), mirroring astutils.index_tree.
    # Global depth is NOT reset at function boundaries (nested-loop's "has scaling
    # ancestor"); per-function depth and the dimension chain ARE reset.
    stack = [(tree.root_node, (), 0, 0, ())]
    while stack:
        node, fchain, sg, sf, sloops = stack.pop()
        nfchain, nsg, nsf, nsloops = fchain, sg, sf, sloops

        if node.is_named:
            t = node.type
            if t in FUNC_TYPES:
                fn = NNode("func", node.start_point[0] + 1, _func_name(node, src))
                idx.functions.append(fn)
                idx.self_calls.setdefault(fn, 0)
                nfchain = fchain + (fn,)
                nsf = 0
                nsloops = ()
            elif t in LOOP_TYPES:
                scaling = _loop_is_scaling(node)
                # Inner `for v of graph[u]` traverses one partition per outer step:
                # amortized linear over the container, not multiplicative. Don't let
                # it add a nesting level (suppresses both bigo and nested-loop).
                if scaling and sg >= 1 and _iterates_partition(node, src):
                    scaling = False
                lp = NNode("loop", node.start_point[0] + 1)
                lp._scaling = scaling
                lp._func = fchain[-1] if fchain else None
                lp._has_sloop_anc = sg >= 1
                lp._sdepth = sf + (1 if scaling else 0)
                idx.loops.append(lp)
                if scaling:
                    # A loop only deepens O(n^k) when its dimension repeats one
                    # already enclosing it; independent sizes are a product.
                    lv, ids = _loop_dims(node, src)
                    fresh = (node.start_point[0], node.start_point[1])
                    dim = _assign_dim(lv, ids, sloops, fresh)
                    lp._dim = dim
                    lp._dim_depth = 1 + sum(1 for _, _, d in sloops if d == dim)
                    lp._has_samedim_anc = lp._dim_depth >= 2
                    nsg = sg + 1
                    nsf = sf + 1
                    nsloops = sloops + ((lv, ids, dim),)
            elif t in CALL_TYPES:
                name = _self_call_name(node, src)
                if name is not None:
                    for af in fchain:  # mirror native: count toward each enclosing fn of that name
                        if af.name == name:
                            idx.self_calls[af] += 1
                if sg >= 1:  # call inside a scaling loop -> candidate for sort/membership
                    inv, recv = _call_target(node, src)
                    func = fchain[-1] if fchain else None
                    idx.loop_calls.append((inv, recv, node.start_point[0] + 1, func))
            elif sg >= 1 and t in AUGASSIGN_TYPES and _aug_is_string_concat(node, src):
                func = fchain[-1] if fchain else None
                idx.loop_augs.append((node.start_point[0] + 1, func))
            elif t in VARDECL_TYPES:
                kind = _decl_kind(node, src)
                if kind:
                    bucket = idx.var_types.setdefault(fchain[-1], {}) if fchain else idx.global_var_types
                    for nm in _decl_names(node, src):
                        bucket[nm] = kind
            elif fchain and _is_ident_leaf(node) and _text(node, src) in MEMO_NAMES:
                # a memo/cache/dp table referenced in the function -> treat as memoized
                idx.memoized.add(fchain[-1])

        for child in node.children:
            stack.append((child, nfchain, nsg, nsf, nsloops))

    return idx
