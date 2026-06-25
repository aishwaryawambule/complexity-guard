import ast

LOOP_TYPES = (ast.For, ast.While)
FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)


def annotate_parents(tree: ast.AST) -> None:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child.parent = parent


def enclosing_loops(node: ast.AST) -> list[ast.AST]:
    loops = []
    cur = getattr(node, "parent", None)
    while cur is not None:
        if isinstance(cur, LOOP_TYPES):
            loops.append(cur)
        cur = getattr(cur, "parent", None)
    return loops


def loop_depth(node: ast.AST) -> int:
    return len(enclosing_loops(node))


def enclosing_function(node: ast.AST):
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
