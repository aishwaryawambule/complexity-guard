"""Structural detectors over non-Python languages via tree-sitter.

Skipped entirely when the optional tree-sitter dependency isn't installed — the
plugin degrades to Python-only in that case, so there is nothing to assert.
"""
import pytest

pytest.importorskip("tree_sitter")
pytest.importorskip("tree_sitter_language_pack")

from complexity_guard.analyze import analyze_ts, analyze_lang, analyze_path


def _detectors(findings):
    return {f.detector for f in findings}


# --- nested loops / big-O across languages ------------------------------------

JS_NESTED = """\
function pairs(xs) {
  for (const x of xs) {
    for (const y of xs) {
      use(x, y);
    }
  }
}
"""

GO_NESTED = """\
func pairs(xs []int) {
    for _, x := range xs {
        for _, y := range xs {
            use(x, y)
        }
    }
}
"""

JAVA_NESTED = """\
class C {
  void pairs(int[] xs) {
    for (int i = 0; i < xs.length; i++) {
      for (int j = 0; j < xs.length; j++) {
        use(i, j);
      }
    }
  }
}
"""


@pytest.mark.parametrize("lang,src", [
    ("javascript", JS_NESTED),
    ("go", GO_NESTED),
    ("java", JAVA_NESTED),
])
def test_nested_loops_flagged(lang, src):
    dets = _detectors(analyze_ts(src, lang))
    # depth-2 nesting -> both nested-loop and bigo fire (dedup happens in the hook layer)
    assert "nested-loop" in dets
    assert "bigo" in dets


# --- adjacency-list / partition traversal: amortized linear, NOT O(n^2) -------

JS_ADJACENCY = """\
function bfs(graph, start) {
  const seen = new Set();
  const queue = [start];
  while (queue.length > 0) {
    const u = queue.pop();
    for (const v of graph[u] || []) {
      if (!seen.has(v)) { seen.add(v); queue.push(v); }
    }
  }
}
"""

GO_ADJACENCY = """\
func bfs(graph map[int][]int, start int) {
    queue := []int{start}
    for len(queue) > 0 {
        u := queue[len(queue)-1]
        queue = queue[:len(queue)-1]
        for _, v := range graph[u] {
            queue = append(queue, v)
        }
    }
}
"""

@pytest.mark.parametrize("lang,src", [
    ("javascript", JS_ADJACENCY),
    ("go", GO_ADJACENCY),
])
def test_partition_traversal_not_flagged(lang, src):
    # inner loop iterates `graph[u]` -> O(V+E), not O(V^2): no quadratic smell
    dets = _detectors(analyze_ts(src, lang))
    assert "bigo" not in dets
    assert "nested-loop" not in dets


def test_bigo_reports_depth():
    src = (
        "func f(xs []int) {\n"
        "    for _, a := range xs {\n"
        "        for _, b := range xs {\n"
        "            for _, c := range xs {\n"
        "                use(a, b, c)\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    bigo = [f for f in analyze_ts(src, "go") if f.detector == "bigo"]
    assert bigo and bigo[0].complexity == "O(n^3)"
    assert bigo[0].function == "f"


# --- recursion across languages -----------------------------------------------

@pytest.mark.parametrize("lang,src,name", [
    ("javascript", "function fib(n){ return fib(n-1) + fib(n-2); }", "fib"),
    ("rust", "fn fib(n: u64) -> u64 { fib(n-1) + fib(n-2) }", "fib"),
    ("java", "class C { int fib(int n){ return fib(n-1) + fib(n-2); } }", "fib"),
    ("php", "<?php function fib($n){ return fib($n-1) + fib($n-2); }", "fib"),
    # grammars where the callee/name is positional, not a named field:
    ("kotlin", "fun fib(n: Int): Int = fib(n-1) + fib(n-2)", "fib"),
    ("lua", "function fib(n)\n  return fib(n-1) + fib(n-2)\nend", "fib"),
])
def test_recursion_no_memo_flagged(lang, src, name):
    findings = [f for f in analyze_ts(src, lang) if f.detector == "recursion-no-memo"]
    assert findings and findings[0].function == name


def test_method_call_is_not_recursion():
    # this.fib() is a qualified call -> must NOT count as self-recursion
    src = "class C { int fib(int n){ return this.fib(n-1) + this.fib(n-2); } }"
    findings = [f for f in analyze_ts(src, "java") if f.detector == "recursion-no-memo"]
    assert findings == []


# --- clean code & dispatch ----------------------------------------------------

def test_clean_code_no_findings():
    assert analyze_ts("function f(x){ return x + 1; }", "javascript") == []


def test_single_loop_not_flagged():
    src = "func f(xs []int) { for _, x := range xs { use(x) } }"
    assert _detectors(analyze_ts(src, "go")) == set()


def test_inline_ignore_suppresses():
    src = (
        "function pairs(xs) {\n"
        "  for (const x of xs) {\n"
        "    for (const y of xs) {  // complexity: ignore\n"
        "      use(x, y);\n"
        "    }\n"
        "  }\n"
        "}\n"
    )
    assert "nested-loop" not in _detectors(analyze_ts(src, "javascript"))


def test_analyze_path_dispatches_by_extension():
    assert "bigo" in _detectors(analyze_path("pairs.js", JS_NESTED))
    assert "bigo" in _detectors(analyze_path("pairs.go", GO_NESTED))


def test_analyze_path_unknown_extension_returns_empty():
    assert analyze_path("notes.md", "anything") == []


def test_analyze_lang_python_routes_to_native():
    # python keeps the full native engine (semantic detectors included)
    findings = analyze_lang("def f(n):\n    return f(n-1) + f(n-2)\n", "python")
    assert "recursion-no-memo" in _detectors(findings)


def test_syntax_error_does_not_raise():
    # tree-sitter is error-tolerant; we just shouldn't crash on garbage
    assert isinstance(analyze_ts("func ( { { {", "go"), list)


# --- accuracy: constant-bounded loops must NOT be flagged ----------------------

@pytest.mark.parametrize("lang,src", [
    ("javascript", "function f(){for(let i=0;i<3;i++){for(let j=0;j<4;j++){g(i,j);}}}"),
    ("go", "func f(){for i:=0;i<3;i++{for j:=0;j<4;j++{g(i,j)}}}"),
    ("java", "class C{void f(){for(int i=0;i<3;i++){for(int j=0;j<4;j++){g(i,j);}}}}"),
    ("c", "void f(){for(int i=0;i<3;i++){for(int j=0;j<4;j++){g(i,j);}}}"),
    ("rust", "fn f(){for i in 0..3{for j in 0..4{g(i,j);}}}"),
])
def test_constant_bounded_nested_loops_not_flagged(lang, src):
    assert _detectors(analyze_ts(src, lang)) == set()


@pytest.mark.parametrize("lang,src", [
    ("javascript", "function f(xs){for(let i=0;i<xs.length;i++){for(let j=0;j<xs.length;j++){g(i,j);}}}"),
    ("c", "void f(int n){for(int i=0;i<n;i++){for(int j=0;j<n;j++){g(i,j);}}}"),
    ("rust", "fn f(n:u64){for i in 0..n{for j in 0..n{g(i,j);}}}"),
])
def test_dynamic_bounded_nested_loops_still_flagged(lang, src):
    assert "bigo" in _detectors(analyze_ts(src, lang))


def test_dynamic_outer_constant_inner_is_linear():
    # O(n * const) == O(n): must not be reported as O(n^2)
    src = "function f(xs){for(let i=0;i<xs.length;i++){for(let j=0;j<3;j++){g(i,j);}}}"
    assert _detectors(analyze_ts(src, "javascript")) == set()


# --- accuracy: suggestions are language-appropriate, memoized recursion is OK --

def test_recursion_suggestion_is_not_python_specific():
    f = [x for x in analyze_ts("function fib(n){return fib(n-1)+fib(n-2);}", "javascript")
         if x.detector == "recursion-no-memo"][0]
    assert "functools" not in f.suggestion
    assert "memoize" in f.suggestion.lower()


@pytest.mark.parametrize("lang,src", [
    ("javascript",
     "function fib(n, memo={}){ if(memo[n]) return memo[n]; return memo[n]=fib(n-1,memo)+fib(n-2,memo); }"),
    ("go",
     "func fib(n int, dp map[int]int) int { if v,ok:=dp[n];ok{return v}; dp[n]=fib(n-1,dp)+fib(n-2,dp); return dp[n] }"),
    ("java",
     "class C{ int fib(int n){ if(cache.containsKey(n))return cache.get(n); int r=fib(n-1)+fib(n-2); cache.put(n,r); return r; } }"),
])
def test_memoized_recursion_is_suppressed(lang, src):
    assert "recursion-no-memo" not in _detectors(analyze_ts(src, lang))


# --- semantic detectors: sort / membership / string-concat in a loop ----------

@pytest.mark.parametrize("lang,src", [
    ("javascript", "function f(xs,rows){for(const x of xs){rows.sort();}}"),
    ("go", "func f(xs []int, rows []int){for _,x:=range xs{sort.Slice(rows,nil)}}"),
    ("java", "class C{void f(java.util.List<Integer> xs,java.util.List<Integer> r){for(int x:xs){java.util.Collections.sort(r);}}}"),
    ("php", "<?php function f($xs,$r){foreach($xs as $x){usort($r,'cmp');}}"),
    ("rust", "fn f(xs:Vec<i32>,mut r:Vec<i32>){for x in &xs{r.sort();}}"),
])
def test_repeated_sort_in_loop_flagged(lang, src):
    assert "repeated-sort-in-loop" in _detectors(analyze_ts(src, lang))


def test_sort_outside_loop_not_flagged():
    assert "repeated-sort-in-loop" not in _detectors(
        analyze_ts("function f(rows){rows.sort();}", "javascript"))


@pytest.mark.parametrize("lang,src", [
    ("javascript", "function f(xs,big){for(const x of xs){if(big.includes(x)){g(x);}}}"),
    ("javascript", "function f(xs,big){for(const x of xs){if(big.indexOf(x)>=0){g(x);}}}"),
    ("php", "<?php function f($xs,$big){foreach($xs as $x){if(in_array($x,$big)){g($x);}}}"),
    ("ruby", "def f(xs,big)\n  for x in xs\n    if big.include?(x)\n      g(x)\n    end\n  end\nend"),
])
def test_membership_in_loop_flagged(lang, src):
    assert "membership-in-loop" in _detectors(analyze_ts(src, lang))


def test_set_membership_not_flagged():
    # `.has()` is O(1) on a Set -> must NOT be flagged (only linear scans are)
    assert "membership-in-loop" not in _detectors(
        analyze_ts("function f(xs,big){for(const x of xs){if(big.has(x)){g(x);}}}", "javascript"))


@pytest.mark.parametrize("lang,src", [
    ("javascript", "function f(xs){let s='';for(const x of xs){s+='a';}return s;}"),
    ("java", "class C{String f(int[] xs){String s=\"\";for(int x:xs){s+=\"a\";}return s;}}"),
    ("go", "func f(xs []int) string {s:=\"\";for _,x:=range xs{s+=\"a\"};return s}"),
    ("php", "<?php function f($xs){$s='';foreach($xs as $x){$s.='a';}return $s;}"),
])
def test_string_concat_in_loop_flagged(lang, src):
    assert "string-concat-in-loop" in _detectors(analyze_ts(src, lang))


def test_numeric_plus_equals_not_flagged():
    # += on a number is not string building -> must NOT be flagged
    assert "string-concat-in-loop" not in _detectors(
        analyze_ts("function f(xs){let s=0;for(const x of xs){s+=1;}return s;}", "javascript"))


def test_semantic_suggestions_are_language_appropriate():
    # the localized advice should not leak Python-isms
    f = [x for x in analyze_ts(
        "class C{String f(int[] xs){String s=\"\";for(int x:xs){s+=\"a\";}return s;}}", "java")
        if x.detector == "string-concat-in-loop"][0]
    assert "StringBuilder" in f.suggestion


# --- type-tracked .contains(): list flagged, set/map/unknown not ---------------

@pytest.mark.parametrize("lang,src", [
    ("java", "class C{void f(int[] xs){java.util.List<Integer> seen=new java.util.ArrayList<>();for(int x:xs){if(seen.contains(x))g(x);}}}"),
    ("csharp", "class C{void F(int[] xs){List<int> seen=new List<int>();foreach(var x in xs){if(seen.Contains(x))G(x);}}}"),
    ("rust", "fn f(xs:Vec<i32>){let seen:Vec<i32>=vec![];for x in &xs{if seen.contains(&x){g(x);}}}"),
    ("go", "func f(xs []int, seen []int){for _,x:=range xs{if slices.Contains(seen,x){g(x)}}}"),
])
def test_list_contains_in_loop_flagged(lang, src):
    assert "membership-in-loop" in _detectors(analyze_ts(src, lang))


@pytest.mark.parametrize("lang,src", [
    ("java", "class C{void f(int[] xs){java.util.Set<Integer> seen=new java.util.HashSet<>();for(int x:xs){if(seen.contains(x))g(x);}}}"),
    ("csharp", "class C{void F(int[] xs){HashSet<int> seen=new HashSet<int>();foreach(var x in xs){if(seen.Contains(x))G(x);}}}"),
    ("rust", "fn f(xs:Vec<i32>){let seen=HashSet::new();for x in &xs{if seen.contains(&x){g(x);}}}"),
])
def test_set_contains_in_loop_not_flagged(lang, src):
    assert "membership-in-loop" not in _detectors(analyze_ts(src, lang))


def test_unknown_type_contains_not_flagged():
    # a Collection<T> param could be a set -> conservative, do not flag
    src = "class C{void f(int[] xs, java.util.Collection<Integer> seen){for(int x:xs){if(seen.contains(x))g(x);}}}"
    assert "membership-in-loop" not in _detectors(analyze_ts(src, "java"))
