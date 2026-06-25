from .parser import parse
from .astutils import annotate_parents
from .detectors import DETECTORS
from .models import Finding


def analyze(source: str) -> list[Finding]:
    try:
        tree = parse(source)
    except SyntaxError:
        return []
    annotate_parents(tree)
    findings: list[Finding] = []
    for detect in DETECTORS:
        findings.extend(detect(tree))
    findings.sort(key=lambda f: (f.lineno, f.detector))
    return findings
