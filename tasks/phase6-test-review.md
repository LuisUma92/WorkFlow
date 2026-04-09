# Phase 6 Test Review — Knowledge Graph

## CRITICAL Issues

### 1. dot_export and tikz_export tests use stubs instead of real domain types
**Files:** `test_dot_export.py`, `test_tikz_export.py`

Both test files define local stub dataclasses (`GraphNode.id` instead of `GraphNode.node_id`, `GraphEdge.source`/`.target` instead of `.source_id`/`.target_id`, `edge.rel_type` instead of `.edge_type`). The source files (`dot_export.py`, `tikz_export.py`) also use this legacy API (`node.id`, `edge.source`, `edge.target`, `edge.rel_type`), which differs from the actual domain types in `domain.py`.

This means:
- The export modules are **incompatible with the real domain types**. The CLI has to use `_adapt()` to bridge the gap.
- Tests pass but hide a real API mismatch. If someone calls `graph_to_dot(kg)` with a real `KnowledgeGraph`, it will fail at runtime.

**Fix:** Align `dot_export.py` and `tikz_export.py` to use the real domain API (`node_id`, `source_id`, `target_id`, `edge_type`), then rewrite tests to import from `workflow.graph.domain` directly. Remove the adapter in `cli.py`.

### 2. No test for `_adapt()` in cli.py
The adapter function `_adapt()` is critical glue but has zero test coverage.

**Fix:** Add unit tests for `_adapt()` or eliminate it (see item 1).

## HIGH Issues

### 3. collectors: no test for multiple citations/links on same note
Only single-citation and single-link cases are tested. Need a test with a note having 3+ citations and 2+ links to verify all edges are emitted.

### 4. collectors: no test for dangling link (label_to_note miss)
`collect_notes` silently skips links where `label_to_note.get(target_id)` returns None. This path is untested.

### 5. analysis: `find_hubs` with min_degree=1 not tested
Only min_degree=5 is tested. Testing with min_degree=1 or min_degree=0 would verify boundary behavior.

### 6. analysis: `neighbors` depth=0 not tested
Should return just the query node itself with no neighbors.

### 7. collectors: `collect_bibliography` label fallback not tested
Source uses `e.bibkey or e.title or f"bib:{e.id}"`. Tests only set `title`. Need test with `bibkey` set, and test with neither set (fallback to `f"bib:{id}"`).

### 8. clustering: no test for single-node graph
Only empty and multi-node graphs are tested.

## MEDIUM Issues

### 9. domain: `adjacency()` with dangling edge references not tested
The docstring says edges referencing missing node_ids are "silently included." There is no test for an edge whose source or target is not in the node set.

### 10. cli: `_build_graph` is never tested directly
All CLI tests mock it, which is correct for unit tests, but there is no integration test verifying the real DB session wiring.

### 11. cli: `export-dot --output` with non-writable path not tested
Error path when file write fails.

### 12. cli: no test for `--project` pointing to missing slipbox.db
Tests always mock `_build_graph`. The real fallback logic (global-only vs global+local) is untested.

### 13. analysis: no test with self-loop edge
What happens when source_id == target_id?

### 14. tikz_export: LaTeX special characters not tested
Labels containing `$`, `%`, `&`, `_`, `#` would break LaTeX output. Only `{` and `}` are escaped in source.

### 15. dot_export: `_escape_dot` and `_node_id` helper functions not unit-tested
They are tested indirectly but not in isolation.

## LOW Issues

### 16. No performance test for large graphs
No test with 1000+ nodes to verify algorithmic complexity is acceptable.

### 17. Test helpers duplicated across files
`_node()`, `_edge()`, `_graph()` are copy-pasted in test_analysis.py, test_clustering.py, test_cli.py. Extract to `conftest.py`.

### 18. clustering: `networkx_available` marker is evaluated at import time
Line 72 in test_clustering.py calls `pytest.importorskip` at module level outside a test, which may cause unexpected skip behavior.

## Suggested New Tests

```python
# test_domain.py
def test_adjacency_with_dangling_edge():
    """Edge referencing non-existent node_id should not crash."""
    ...

def test_adjacency_with_self_loop():
    ...

# test_collectors.py
def test_collect_notes_multiple_citations_same_note():
    ...

def test_collect_notes_dangling_link():
    """Link whose target label has no note_id."""
    ...

def test_collect_bibliography_bibkey_label():
    """bibkey should be preferred over title in label."""
    ...

def test_collect_bibliography_no_bibkey_no_title():
    """Label falls back to bib:{id}."""
    ...

# test_analysis.py
def test_find_hubs_min_degree_1():
    ...

def test_neighbors_depth_0():
    ...

def test_neighbors_self_loop():
    ...

# test_clustering.py
def test_single_node_graph():
    ...

# test_cli.py
def test_adapt_converts_field_names():
    ...

def test_stats_empty_graph():
    ...

def test_export_dot_title_option():
    ...
```

## Overall Rating

| Module        | Test Quality | Coverage Estimate | Verdict  |
|---------------|-------------|-------------------|----------|
| domain.py     | Good        | ~90%              | Pass     |
| collectors.py | Good        | ~80%              | Pass     |
| analysis.py   | Good        | ~85%              | Pass     |
| dot_export.py | Poor        | ~75% (stub API)   | **Fail** |
| tikz_export.py| Poor        | ~75% (stub API)   | **Fail** |
| clustering.py | Adequate    | ~80%              | Pass     |
| cli.py        | Good        | ~80%              | Pass     |

**Blocking:** The dot_export and tikz_export stub-API mismatch (CRITICAL #1) must be resolved before merge. Either unify the export modules to use the real domain API or add thorough tests for the adapter layer.
