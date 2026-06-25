"""Semantic detectors for the tree-sitter path: sort / membership / string-concat.

Unlike the structural detectors (which are shared verbatim with the Python
engine), these read language-specific signals — method names and operators
collected into the NormalizedIndex while it's inside a *scaling* loop. They are
intentionally high-confidence: only call/operator shapes that imply linear or
super-linear work regardless of static types are flagged, to keep false
positives low across many languages.
"""
from .models import Finding
from .langspec import (
    SORT_NAMES, SORT_RECEIVERS, MEMBERSHIP_NAMES, CONTAINS_NAMES,
    SLICE_SCAN_RECEIVERS, membership_suggestion, concat_suggestion,
)


def _fname(func):
    return func.name if func is not None else None


def _detect_repeated_sort(idx, lang: str) -> list[Finding]:
    out = []
    for name, recv, lineno, func in idx.loop_calls:
        if name in SORT_NAMES or recv in SORT_RECEIVERS:
            out.append(Finding(
                detector="repeated-sort-in-loop",
                lineno=lineno,
                complexity="O(n^2 log n)",
                message="sorting inside a loop",
                suggestion="if the data doesn't change between iterations, sort once before the loop",
                function=_fname(func),
            ))
    return out


def _receiver_kind(idx, func, receiver):
    """'list' / 'set' / None for a call's receiver, using tracked variable types."""
    if receiver is None:
        return None
    if func is not None:
        kind = idx.var_types.get(func, {}).get(receiver)
        if kind:
            return kind
    return idx.global_var_types.get(receiver)


def _detect_membership_in_loop(idx, lang: str) -> list[Finding]:
    out = []
    for name, recv, lineno, func in idx.loop_calls:
        flagged = name in MEMBERSHIP_NAMES
        # `.contains()` only when the receiver is a known list (not a hash set)
        if not flagged and name in CONTAINS_NAMES:
            flagged = _receiver_kind(idx, func, recv) == "list"
        # go's slices.Contains(slice, x) is always a linear scan
        if not flagged and name == "Contains" and recv in SLICE_SCAN_RECEIVERS:
            flagged = True
        if flagged:
            out.append(Finding(
                detector="membership-in-loop",
                lineno=lineno,
                complexity="O(n^2)",
                message=f"linear membership scan `{name}(...)` inside a loop",
                suggestion=membership_suggestion(lang),
                function=_fname(func),
            ))
    return out


def _detect_string_concat_in_loop(idx, lang: str) -> list[Finding]:
    out = []
    for lineno, func in idx.loop_augs:
        out.append(Finding(
            detector="string-concat-in-loop",
            lineno=lineno,
            complexity="O(n^2)",
            message="building a string with += inside a loop",
            suggestion=concat_suggestion(lang),
            function=_fname(func),
        ))
    return out


SEMANTIC_DETECTORS = [
    _detect_repeated_sort,
    _detect_membership_in_loop,
    _detect_string_concat_in_loop,
]
