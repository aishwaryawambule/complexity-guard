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
