from .nested_loop import detect_nested_loop
from .membership import detect_membership_in_loop
from .recursion import detect_recursion_no_memo
from .string_concat import detect_string_concat_in_loop
from .repeated_sort import detect_repeated_sort_in_loop
from .loop_invariant import detect_loop_invariant_call
from .bigo import detect_bigo

DETECTORS = [
    detect_nested_loop,
    detect_membership_in_loop,
    detect_recursion_no_memo,
    detect_string_concat_in_loop,
    detect_repeated_sort_in_loop,
    detect_loop_invariant_call,
    detect_bigo,
]
