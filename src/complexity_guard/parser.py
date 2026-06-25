import ast


def parse(source: str) -> ast.Module:
    """Parse Python source into a module AST. Raises SyntaxError on bad input."""
    return ast.parse(source)
