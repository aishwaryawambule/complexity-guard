"""Language detection + tree-sitter node-type tables for multi-language analysis.

The structural detectors (nested-loop, bigo, recursion) only need to know which
nodes are *functions*, *loops*, and *calls*. Tree-sitter grammars name those
nodes consistently enough that a single union of type names covers most popular
languages — so a language we never special-cased often "just works" as long as
its grammar uses these common node names. Anything that doesn't simply yields no
findings (never a crash).
"""

# file extension -> tree-sitter-language-pack grammar id
EXT_TO_LANG = {
    ".py": "python",   # routed to the native ast engine, not tree-sitter
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".mts": "typescript", ".cts": "typescript", ".tsx": "tsx",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c", ".h": "c",
    ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp", ".hxx": "cpp",
    ".kt": "kotlin", ".kts": "kotlin",
    ".swift": "swift",
    ".scala": "scala", ".sc": "scala",
    ".lua": "lua",
}

# Named tree-sitter node types, unioned across grammars. Keyword *tokens* like the
# bare `for`/`while` are unnamed nodes and are filtered out via Node.is_named, so
# the ruby statement nodes (which really are named `while`/`for`) don't collide
# with C-style keyword tokens.
LOOP_TYPES = frozenset({
    "for_statement", "for_in_statement", "for_of_statement", "while_statement",
    "do_statement", "enhanced_for_statement", "foreach_statement",
    "for_expression", "while_expression", "loop_expression", "for_range_loop",
    "while", "for", "until", "while_modifier", "until_modifier", "repeat_statement",
})

FUNC_TYPES = frozenset({
    "function_declaration", "function_definition", "function_item",
    "function_expression", "arrow_function", "method_definition",
    "method_declaration", "constructor_declaration", "func_literal",
    "local_function_statement", "method", "singleton_method",
    "generator_function_declaration", "generator_function", "lambda",
})

CALL_TYPES = frozenset({
    "call_expression", "method_invocation", "invocation_expression", "call",
    "function_call_expression", "member_call_expression", "scoped_call_expression",
    "function_call",  # lua
})

# --- bounded-loop classification (scaling vs constant-bounded) ----------------
# A counting loop bounded by an integer literal (e.g. `for(i=0;i<3;i++)`) does NOT
# scale with input size, so it must not count toward O(n^k) nesting — matching the
# native engine, which treats `range(constant)` and literal iteration as bounded.

# Only `for_statement` is an ambiguous counting loop (C-style in most languages;
# C-style OR range in Go). Everything else — foreach / for-in / for-of / while /
# rust loop — is treated as scaling.
COUNTING_FOR_TYPES = frozenset({"for_statement"})

# Integer-literal bound -> bounded. (Floats/loops over them are unusual; ignored.)
INT_LITERAL_TYPES = frozenset({
    "number", "number_literal", "integer_literal", "decimal_integer_literal",
    "int_literal", "integer", "hex_integer_literal", "integer_literal_expression",
})

# A bound that depends on a collection's size -> scaling (e.g. xs.length, len(xs)).
DYNAMIC_BOUND_TYPES = frozenset({
    "member_expression", "field_access", "field_expression", "call_expression",
    "method_invocation", "invocation_expression", "call", "function_call",
    "function_call_expression", "selector_expression", "subscript_expression",
    "subscript", "element_access_expression", "index_expression",
    "member_access_expression",
})

COMPARE_TYPES = frozenset({
    "binary_expression", "relational_expression", "comparison_expression",
    "comparison_operator",
})
COMPARE_OPS = frozenset({"<", "<=", ">", ">=", "!="})

# Rust `for i in 0..K` — a constant range is bounded.
RANGE_TYPES = frozenset({"range_expression", "range"})

# Bracket/index access `container[key]` across grammars. An inner loop iterating
# one of these (`for v of graph[u]`) walks a single partition per outer step, so
# its work is amortized linear in the whole container, not multiplicative — it
# must not count as an O(n^k) nesting level (see tsadapter._iterates_partition).
SUBSCRIPT_TYPES = frozenset({
    "subscript_expression",        # js / ts
    "index_expression",            # go
    "array_access",                # java
    "element_access_expression",   # c#
    "subscript",                   # other grammars
})


# Callee shapes that mean "qualified / method call" (e.g. obj.foo()). A self-call
# for recursion only counts when the callee is an *unqualified* identifier, so we
# treat these as non-recursive — matching the native engine, which only counts
# ast.Name callees (not ast.Attribute).
MEMBER_TYPES = frozenset({
    "member_expression", "field_expression", "selector_expression",
    "scoped_identifier", "attribute", "member_access_expression",
    "navigation_expression", "scoped_call_expression", "qualified_name",
    "member_call_expression",
})


# --- recursion: memoization signal + language-appropriate advice --------------
# Conservative: a variable named like a memo table strongly implies the recursion
# is already memoized, so we suppress the warning. Kept tight to avoid hiding real
# exponential recursion behind a coincidental name.
MEMO_NAMES = frozenset({"memo", "dp", "cache", "cached", "memoized", "memos"})

# The native Python engine suggests `@functools.cache`; that's meaningless in other
# languages, so give each a fitting phrasing (with a generic fallback).
_RECURSION_SUGGESTIONS = {
    "javascript": "memoize it — cache results in a Map keyed by the arguments",
    "typescript": "memoize it — cache results in a Map keyed by the arguments",
    "tsx": "memoize it — cache results in a Map keyed by the arguments",
    "go": "memoize it — cache results in a map keyed by the arguments",
    "rust": "memoize it — cache results in a HashMap keyed by the arguments",
    "java": "memoize it — cache results in a Map (or a memo array)",
    "csharp": "memoize it — cache results in a Dictionary keyed by the arguments",
    "ruby": "memoize it — cache results in a Hash keyed by the arguments",
    "php": "memoize it — cache results in an array keyed by the arguments",
    "c": "memoize it — cache results in an array/table keyed by the arguments",
    "cpp": "memoize it — cache results in a std::unordered_map keyed by the arguments",
    "kotlin": "memoize it — cache results in a Map keyed by the arguments",
    "scala": "memoize it — cache results in a Map keyed by the arguments",
    "swift": "memoize it — cache results in a Dictionary keyed by the arguments",
    "lua": "memoize it — cache results in a table keyed by the arguments",
}
_RECURSION_SUGGESTION_DEFAULT = (
    "memoize it — cache each input's result to avoid recomputing subproblems"
)


def recursion_suggestion(lang: str) -> str:
    return _RECURSION_SUGGESTIONS.get(lang, _RECURSION_SUGGESTION_DEFAULT)


# --- semantic detectors (sort / membership / string-concat) -------------------
# These look at calls and augmented assignments that occur inside a scaling loop.

# Sort, by the simple invoked name (covers x.sort(), sorted(), Collections.sort(),
# usort(), v.sort(), std::sort()). Go calls it via the `sort` package, so we also
# match a `sort` receiver (sort.Slice / sort.Ints / sort.Sort).
SORT_NAMES = frozenset({
    "sort", "Sort", "sorted", "sort!", "sort_by", "sort_by!",
    "usort", "asort", "ksort", "rsort", "arsort", "krsort", "uasort", "uksort",
})
SORT_RECEIVERS = frozenset({"sort"})

# Linear membership tests with high confidence (the method name alone implies a
# linear scan — unlike `.contains()`, which is also O(1) on a hash set, so we omit
# it pending real type tracking).
MEMBERSHIP_NAMES = frozenset({"includes", "indexOf", "in_array", "include?"})

# `.contains()` is O(1) on a hash set but O(n) on a list, so it's only flagged
# when the receiver is known to be a list (see variable-type tracking below).
CONTAINS_NAMES = frozenset({"contains", "Contains"})
# Go scans a slice via the `slices` package — always linear, so flag it directly.
SLICE_SCAN_RECEIVERS = frozenset({"slices"})

# Variable-declaration node types whose declared type we classify as list vs set.
VARDECL_TYPES = frozenset({
    "local_variable_declaration", "field_declaration",      # java
    "variable_declaration",                                 # c#
    "short_var_declaration", "var_spec",                    # go
    "let_declaration",                                      # rust
})
# Substring hints on the declared type / initializer. Set/map checked first so
# `Map<K, List<V>>` classifies as a (non-flagged) map, not a list.
SET_TYPE_HINTS = (
    "HashSet", "TreeSet", "LinkedHashSet", "BTreeSet", "Set<", "ISet<",
    "HashMap", "TreeMap", "LinkedHashMap", "BTreeMap", "Dictionary", "Map<",
    "map[", "unordered_set", "unordered_map", "std::set", "std::map",
)
LIST_TYPE_HINTS = (
    "ArrayList", "LinkedList", "List<", "IList<", "Vec<", "vec!", "Vec::",
    "[]", "Array", "Slice", "std::vector", "vector<",
)

# Augmented-assignment node types across grammars, plus the `+=` / `.=` operators.
AUGASSIGN_TYPES = frozenset({
    "augmented_assignment_expression", "assignment_expression",
    "compound_assignment_expr", "assignment_statement", "augmented_assignment",
})
CONCAT_OPS = frozenset({"+=", ".="})

STRING_LIT_TYPES = frozenset({
    "string", "string_literal", "template_string", "encapsed_string",
    "interpreted_string_literal", "raw_string_literal", "char_literal",
    "simple_string", "string_content", "template_literal", "heredoc",
})

_MEMBERSHIP_SUGGESTIONS = {
    "javascript": "use a Set and .has() for O(1) lookups",
    "typescript": "use a Set and .has() for O(1) lookups",
    "tsx": "use a Set and .has() for O(1) lookups",
    "php": "index the array by key and use isset() for O(1) lookups",
    "ruby": "use a Set for O(1) lookups",
}
_MEMBERSHIP_SUGGESTION_DEFAULT = "use a hash set for O(1) lookups"

_CONCAT_SUGGESTIONS = {
    "javascript": "push pieces to an array and join('') after the loop",
    "typescript": "push pieces to an array and join('') after the loop",
    "tsx": "push pieces to an array and join('') after the loop",
    "java": "use a StringBuilder and append() inside the loop",
    "csharp": "use a StringBuilder and Append() inside the loop",
    "go": "use a strings.Builder and WriteString() inside the loop",
    "rust": "use String::push_str(), or collect into a String",
    "cpp": "reserve capacity and append, or build with a stringstream",
    "php": "collect pieces in an array and implode() after the loop",
}
_CONCAT_SUGGESTION_DEFAULT = "accumulate pieces in a list and join once after the loop"


def membership_suggestion(lang: str) -> str:
    return _MEMBERSHIP_SUGGESTIONS.get(lang, _MEMBERSHIP_SUGGESTION_DEFAULT)


def concat_suggestion(lang: str) -> str:
    return _CONCAT_SUGGESTIONS.get(lang, _CONCAT_SUGGESTION_DEFAULT)


def lang_for_path(path: str) -> str | None:
    """Return the grammar id for a file path, or None if the extension is unknown."""
    lower = path.lower()
    for ext, lang in EXT_TO_LANG.items():
        if lower.endswith(ext):
            return lang
    return None
