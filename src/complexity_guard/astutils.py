import ast
from collections import deque

LOOP_TYPES = (ast.For, ast.While)
FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)

_MISSING = object()


def enclosing_loops(node: ast.AST) -> list[ast.AST]:
    loops = []
    cur = getattr(node, "parent", None)
    while cur is not None:
        if isinstance(cur, LOOP_TYPES):
            loops.append(cur)
        cur = getattr(cur, "parent", None)
    return loops


def loop_depth(node: ast.AST) -> int:
    d = getattr(node, "_loop_depth", _MISSING)
    if d is not _MISSING:
        return d
    return len(enclosing_loops(node))


def enclosing_function(node: ast.AST):
    f = getattr(node, "_func", _MISSING)
    if f is not _MISSING:
        return f
    cur = getattr(node, "parent", None)
    while cur is not None:
        if isinstance(cur, FUNC_TYPES):
            return cur
        cur = getattr(cur, "parent", None)
    return None


def enclosing_function_name(node: ast.AST):
    func = enclosing_function(node)
    return func.name if func is not None else None


def iter_functions(tree: ast.AST) -> list[ast.AST]:
    return [n for n in ast.walk(tree) if isinstance(n, FUNC_TYPES)]


def is_within(node, ancestor):
    cur = node
    while cur is not None:
        if cur is ancestor:
            return True
        cur = getattr(cur, "parent", None)
    return False


def is_scaling_loop(node):
    cached = getattr(node, "_scaling", _MISSING)
    if cached is not _MISSING:
        return cached
    result = _compute_scaling(node)
    node._scaling = result
    return result


def _compute_scaling(node):
    if isinstance(node, ast.While):
        return True
    it = node.iter
    if isinstance(it, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
        return False
    if (isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == "range"
            and not it.keywords
            and all(isinstance(a, ast.Constant) and isinstance(a.value, int) for a in it.args)):
        return False
    return True


def iter_is_partition(it) -> bool:
    """True if a for-loop iterable indexes into a container — ``graph[u]``,
    ``buckets[k]`` — seen through ``a or b`` / ``a if c else b`` wrappers.

    Such an inner loop walks one partition per outer step, so its total work is
    amortized linear in the whole container (O(V+E) for an adjacency list), not
    O(outer × inner). A slice (``arr[i:]``) is a real sub-sequence scan, not a
    partition, so it is excluded — those genuinely are O(n^2).
    """
    stack = [it]
    seen = 0
    while stack and seen < 8:
        cur = stack.pop()
        seen += 1
        if isinstance(cur, ast.Subscript):
            if not isinstance(cur.slice, ast.Slice):
                return True
        elif isinstance(cur, ast.BoolOp):
            stack.extend(cur.values)
        elif isinstance(cur, ast.IfExp):
            stack.extend((cur.body, cur.orelse))
    return False


class TreeIndex:
    """Result of a single tree walk: per-node context is stamped onto the nodes
    (``parent``, ``_func``, ``_loop_depth``, ``_scaling``, and on loops ``_sdepth``
    / ``_has_sloop_anc``) and nodes are bucketed by type in ``ast.walk`` (BFS)
    order so detectors iterate the same order they used to."""

    __slots__ = (
        "tree", "functions", "loops", "calls", "compares", "augassigns",
        "assigns", "list_names", "str_names", "self_calls",
    )

    def __init__(self, tree):
        self.tree = tree
        self.functions = []
        self.loops = []
        self.calls = []
        self.compares = []
        self.augassigns = []
        self.assigns = []
        # func node -> set of names assigned a list / str anywhere in its subtree
        self.list_names = {}
        self.str_names = {}
        # func node -> count of calls to its own name anywhere in its subtree
        self.self_calls = {}


def _is_list_value(v) -> bool:
    return isinstance(v, (ast.List, ast.ListComp)) or (
        isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "list"
    )


# queue entry layout: (node, enclosing_func, func_chain, loop_depth,
#                       scaling_depth_global, scaling_depth_in_func)


def index_tree(tree: ast.AST) -> TreeIndex:
    """Walk the tree once, stamping per-node context and bucketing nodes.

    Order matches ``ast.walk`` (breadth-first) so the buckets reproduce the exact
    iteration order the original per-detector walks used. Context (enclosing
    function, loop depth, scaling-loop depth) is propagated through the BFS queue
    so each node is touched a single time. The per-node work lives in
    ``_index_node`` so this driver stays a flat O(n) queue drain.
    """
    idx = TreeIndex(tree)
    tree.parent = None
    q = deque()
    q.append((tree, None, (), 0, 0, 0))
    while q:
        _index_node(idx, q.popleft(), q)
    return idx


def _index_node(idx: TreeIndex, item, q) -> None:
    """Stamp one node's context, bucket it, and enqueue its children."""
    node, func, fchain, ldepth, sg, sf = item
    node._func = func
    node._loop_depth = ldepth

    cfunc, cchain, cldepth, csg, csf = func, fchain, ldepth, sg, sf
    t = type(node)

    if t is ast.FunctionDef or t is ast.AsyncFunctionDef:
        idx.functions.append(node)
        idx.list_names.setdefault(node, set())
        idx.str_names.setdefault(node, set())
        idx.self_calls.setdefault(node, 0)
        cfunc = node
        cchain = fchain + (node,)
        csf = 0  # scaling-loop depth is measured within the enclosing function
    elif t is ast.For or t is ast.While:
        idx.loops.append(node)
        scaling = is_scaling_loop(node)
        # An inner `for x in container[key]` (adjacency list, bucket map, ...) walks
        # one partition per outer step — amortized linear over the whole container,
        # not multiplicative — so don't let it add a nesting level. Overwrite the
        # cached `_scaling` too, so the nested-loop detector (which re-reads it) agrees.
        if scaling and sg >= 1 and t is ast.For and iter_is_partition(node.iter):
            scaling = node._scaling = False
        node._sdepth = sf + (1 if scaling else 0)  # bigo: scaling depth incl. self
        node._has_sloop_anc = sg >= 1              # nested-loop: a scaling loop encloses it
        cldepth = ldepth + 1
        if scaling:
            csg = sg + 1
            csf = sf + 1
    elif t is ast.Call:
        idx.calls.append(node)
        _attr_self_call(idx, node, fchain)
    elif t is ast.Compare:
        idx.compares.append(node)
    elif t is ast.AugAssign:
        idx.augassigns.append(node)
    elif t is ast.Assign:
        idx.assigns.append(node)
        _attr_assigned_names(idx, node, fchain)

    for child in ast.iter_child_nodes(node):
        child.parent = node
        q.append((child, cfunc, cchain, cldepth, csg, csf))


def _attr_self_call(idx: TreeIndex, node: ast.Call, fchain) -> None:
    fn = node.func
    if not isinstance(fn, ast.Name):
        return
    name = fn.id
    for af in fchain:  # fchain holds enclosing functions; a call counts toward each that shares its name
        if af.name == name:
            idx.self_calls[af] += 1


def _attr_assigned_names(idx: TreeIndex, node: ast.Assign, fchain) -> None:
    if not fchain:
        return
    v = node.value
    is_list = _is_list_value(v)
    is_str = isinstance(v, ast.Constant) and isinstance(v.value, str)
    if not (is_list or is_str):
        return
    names = [tgt.id for tgt in node.targets if isinstance(tgt, ast.Name)]
    if not names:
        return
    for af in fchain:  # a name assigned in a function's subtree belongs to that function and every enclosing one
        if is_list:
            idx.list_names[af].update(names)
        if is_str:
            idx.str_names[af].update(names)
