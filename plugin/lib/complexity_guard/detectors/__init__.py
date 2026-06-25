from .nested_loop import detect_nested_loop, _detect_nested_loop
from .membership import detect_membership_in_loop, _detect_membership_in_loop
from .recursion import detect_recursion_no_memo, _detect_recursion_no_memo
from .string_concat import detect_string_concat_in_loop, _detect_string_concat_in_loop
from .repeated_sort import detect_repeated_sort_in_loop, _detect_repeated_sort_in_loop
from .loop_invariant import detect_loop_invariant_call, _detect_loop_invariant_call
from .bigo import detect_bigo, _detect_bigo

# Public, tree-based entry points (each parses an index internally) — kept for
# standalone / test use.
DETECTORS = [
    detect_nested_loop,
    detect_membership_in_loop,
    detect_recursion_no_memo,
    detect_string_concat_in_loop,
    detect_repeated_sort_in_loop,
    detect_loop_invariant_call,
    detect_bigo,
]

# Index-based detectors used by analyze(): they share one TreeIndex so the tree
# is walked a single time for the whole pipeline.
DETECTORS_IDX = [
    _detect_nested_loop,
    _detect_membership_in_loop,
    _detect_recursion_no_memo,
    _detect_string_concat_in_loop,
    _detect_repeated_sort_in_loop,
    _detect_loop_invariant_call,
    _detect_bigo,
]

# The language-agnostic subset: these read only loop nesting / function /
# self-call structure, so they run unchanged over a tree-sitter NormalizedIndex
# for any language (see tsadapter / analyze_lang). The semantic detectors
# (membership/sort/string-concat/loop-invariant) are Python-only.
STRUCTURAL_DETECTORS_IDX = [
    _detect_nested_loop,
    _detect_recursion_no_memo,
    _detect_bigo,
]
