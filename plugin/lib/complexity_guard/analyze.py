from dataclasses import replace
from .parser import parse
from .astutils import index_tree
from .detectors import DETECTORS_IDX, STRUCTURAL_DETECTORS_IDX
from .models import Finding
from .langspec import lang_for_path, recursion_suggestion
from . import tsadapter
from .tsdetectors import SEMANTIC_DETECTORS
from .config import Config, DEFAULT, load_config


def _finalize(findings: list[Finding], source: str, config: Config = DEFAULT) -> list[Finding]:
    """Drop inline-ignored + config-disabled findings, then sort. Shared by every path."""
    lines = source.splitlines()

    def _ignored(f: Finding) -> bool:
        return 1 <= f.lineno <= len(lines) and "complexity: ignore" in lines[f.lineno - 1]

    findings = [f for f in findings if not _ignored(f)]
    findings = config.filter(findings)
    findings.sort(key=lambda f: (f.lineno, f.detector))
    return findings


def analyze(source: str, config: Config = DEFAULT) -> list[Finding]:
    """Full Python analysis (all detectors) via the native ast engine."""
    try:
        tree = parse(source)
    except SyntaxError:
        return []
    idx = index_tree(tree)
    findings: list[Finding] = []
    for detect in DETECTORS_IDX:
        findings.extend(detect(idx))
    return _finalize(findings, source, config)


def _localize_ts(findings: list[Finding], idx, lang: str) -> list[Finding]:
    """Drop recursion findings for memoized functions and give the rest
    language-appropriate advice (the native suggestion is Python-specific)."""
    memo_keys = {(fn.name, fn.lineno) for fn in idx.memoized}
    out: list[Finding] = []
    for f in findings:
        if f.detector == "recursion-no-memo":
            if (f.function, f.lineno) in memo_keys:
                continue  # already memoized -> not an exponential-recursion problem
            f = replace(f, suggestion=recursion_suggestion(lang))
        out.append(f)
    return out


def analyze_ts(source: str, lang: str, config: Config = DEFAULT) -> list[Finding]:
    """Structural + semantic analysis for a non-Python language via tree-sitter.

    Returns [] when tree-sitter / the grammar is unavailable (graceful fallback).
    """
    idx = tsadapter.build_index(source, lang)
    if idx is None:
        return []
    findings: list[Finding] = []
    for detect in STRUCTURAL_DETECTORS_IDX:
        findings.extend(detect(idx))
    findings = _localize_ts(findings, idx, lang)
    for detect in SEMANTIC_DETECTORS:
        findings.extend(detect(idx, lang))
    return _finalize(findings, source, config)


def analyze_lang(source: str, lang: str, config: Config = DEFAULT) -> list[Finding]:
    """Dispatch by language: Python -> native engine, everything else -> tree-sitter."""
    if lang == "python":
        return analyze(source, config)
    return analyze_ts(source, lang, config)


def analyze_path(path: str, source: str) -> list[Finding]:
    """Analyze ``source`` using the engine + project config appropriate for ``path``."""
    lang = lang_for_path(path)
    if lang is None:
        return []
    config = load_config(path)
    if config.excludes(path) or not config.allows_language(lang):
        return []
    return analyze_lang(source, lang, config)
