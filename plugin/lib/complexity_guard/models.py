from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    detector: str
    lineno: int
    complexity: str
    message: str
    suggestion: str
    function: str | None = None
    severity: str = "warning"
