---
status: completed
---

# Phase 4c Test Review -- Coverage Gaps and Missing Tests

## CRITICAL

### 1. normalize() max_passes cap branch (test_normalize.py)
The multi-pass loop in `normalize()` has a `max_passes` guard (line 191) but no test
exercises the case where convergence is NOT reached before `max_passes`. Add:

```python
def test_normalize_respects_max_passes():
    """When max_passes=1, nested macros that need 2+ passes remain partial."""
    # Create a macro that expands to another custom macro
    custom_map = {
        r"\outer": MacroRule(1, r"\inner{{{0}}}"),
        r"\inner": MacroRule(1, "DONE({0})"),
    }
    result = normalize(r"\outer{x}", macro_map=custom_map, max_passes=1)
    # After 1 pass: \outer{x} -> \inner{x}, but \inner not yet expanded
    assert r"\inner{x}" in result or "DONE(x)" in result
    # With enough passes it should fully expand
    result2 = normalize(r"\outer{x}", macro_map=custom_map, max_passes=10)
    assert result2 == "DONE(x)"
```

### 2. normalize() with custom macro_map (test_normalize.py)
The `macro_map` parameter is never tested on `normalize()` directly. Add:

```python
def test_normalize_custom_macro_map():
    custom = {r"\foo": MacroRule(1, "BAR({0})")}
    assert normalize(r"\foo{x}", macro_map=custom) == "BAR(x)"
    # DEFAULT macros should NOT apply
    assert normalize(r"\vc{E}", macro_map=custom) == r"\vc{E}"
```

## HIGH

### 3. Malformed brace input (test_normalize.py)
```python
def test_expand_malformed_braces_skipped():
    result = _expand_one_macro(r"\vc{unclosed", r"\vc", DEFAULT_MACRO_MAP[r"\vc"])
    assert result == r"\vc{unclosed"  # left unchanged
```

### 4. Multiline math delimiters (test_normalize.py)
```python
def test_double_dollar_multiline():
    text = "$$\nE=mc^2\n$$"
    result = convert_math_delimiters(text)
    assert result == "\\[\nE=mc^2\n\\]"
```

### 5. Multiple correct multichoice (test_moodle.py)
```python
def test_multiple_correct_answers_fraction():
    from workflow.exercise.moodle import exercise_to_xml
    options = (
        ParsedOption(label="a", instruction="A", solution="", is_correct=True),
        ParsedOption(label="b", instruction="B", solution="", is_correct=True),
        ParsedOption(label="c", instruction="C", solution="", is_correct=False),
    )
    ex = ParsedExercise(
        stem="Pick all correct.",
        solution="A and B.",
        metadata=_make_metadata(type="multichoice"),
        options=options,
    )
    elem = exercise_to_xml(ex)
    answers = elem.findall("answer")
    correct = [a for a in answers if float(a.attrib["fraction"]) > 0]
    assert len(correct) == 2
    assert all(float(a.attrib["fraction"]) == 50.0 for a in correct)
```

### 6. truefalse question type (test_moodle.py)
```python
def test_truefalse_question():
    from workflow.exercise.moodle import exercise_to_xml
    options = (
        ParsedOption(label="true", instruction="True", solution="", is_correct=True),
        ParsedOption(label="false", instruction="False", solution="", is_correct=False),
    )
    ex = ParsedExercise(
        stem="Is the sky blue?",
        solution="Yes.",
        metadata=_make_metadata(type="truefalse"),
        options=options,
    )
    elem = exercise_to_xml(ex)
    assert elem.attrib["type"] == "truefalse"
    assert len(elem.findall("answer")) == 2
```

### 7. Tag filtering in export-moodle CLI (test_cli.py)
```python
def test_export_moodle_filters_by_tag(self, runner, tmp_path):
    (tmp_path / "ex001.tex").write_text(COMPLETE_TEX)
    result = runner.invoke(
        exercise,
        ["export-moodle", str(tmp_path), "--tag", "physics"],
    )
    assert result.exit_code == 0
    assert "cli-test-001" in result.output

def test_export_moodle_tag_excludes_unmatched(self, runner, tmp_path):
    (tmp_path / "ex001.tex").write_text(COMPLETE_TEX)
    result = runner.invoke(
        exercise,
        ["export-moodle", str(tmp_path), "--tag", "nonexistent"],
    )
    assert "No exercises found" in result.output
```

### 8. Missing image file silent skip (test_moodle.py)
```python
def test_missing_image_skipped():
    from workflow.exercise.moodle import exercise_to_xml
    ex = ParsedExercise(
        stem="See image.",
        solution="None.",
        metadata=_make_metadata(type="essay"),
        image_refs=("/nonexistent/image.png",),
    )
    elem = exercise_to_xml(ex)
    file_elems = elem.findall(".//file")
    assert len(file_elems) == 0
```

### 9. Option feedback normalization (test_moodle.py)
```python
def test_option_feedback_macros_normalized():
    from workflow.exercise.moodle import exercise_to_xml
    options = (
        ParsedOption(label="a", instruction="A", solution=r"\vc{E}", is_correct=True),
    )
    ex = ParsedExercise(
        stem="Q", solution="S",
        metadata=_make_metadata(type="multichoice"), options=options,
    )
    elem = exercise_to_xml(ex)
    fb = elem.find(".//answer/feedback/text")
    assert fb is not None
    assert r"\vc{E}" not in fb.text
    assert r"\vec{\mathbf{E}}" in fb.text
```

## MEDIUM

### 10. Empty exercises list (test_moodle.py)
```python
def test_empty_exercises_quiz():
    from workflow.exercise.moodle import exercises_to_quiz_xml
    xml_str = exercises_to_quiz_xml([])
    assert "<quiz" in xml_str
```

### 11. source_dirs shorter than exercises (test_moodle.py)
```python
def test_source_dirs_shorter_than_exercises():
    from workflow.exercise.moodle import exercises_to_quiz_xml
    ex1 = ParsedExercise(stem="Q1", solution="A1", metadata=_make_metadata(id="e1"))
    ex2 = ParsedExercise(stem="Q2", solution="A2", metadata=_make_metadata(id="e2"))
    # source_dirs has only 1 entry for 2 exercises
    xml_str = exercises_to_quiz_xml([ex1, ex2], source_dirs=[Path("/tmp")])
    root = fromstring(xml_str.split("?>", 1)[1].strip())
    assert len(root.findall("question")) == 2
```

### 12. \mailto and \ifpause macros (test_normalize.py)
```python
def test_mailto_expansion():
    result = _expand_one_macro(r"\mailto{user@ex.com}", r"\mailto", DEFAULT_MACRO_MAP[r"\mailto"])
    assert result == "user@ex.com"

def test_ifpause_expansion():
    result = _expand_one_macro(r"a \ifpause b", r"\ifpause", DEFAULT_MACRO_MAP[r"\ifpause"])
    assert result == "a  b"
```

### 13. default_grade None omits element (test_moodle.py)
```python
def test_no_default_grade_element():
    from workflow.exercise.moodle import exercise_to_xml
    ex = ParsedExercise(stem="Q", solution="A", metadata=_make_metadata(type="essay"))
    elem = exercise_to_xml(ex)
    assert elem.find("defaultgrade") is None
```

### 14. Status default in export-moodle (test_cli.py)
```python
def test_export_moodle_default_status_is_complete(self, runner, tmp_path):
    """Without --status flag, only 'complete' exercises are exported."""
    (tmp_path / "ex001.tex").write_text(COMPLETE_TEX)   # status: complete
    (tmp_path / "ex002.tex").write_text(PLACEHOLDER_TEX)  # no status -> placeholder
    result = runner.invoke(exercise, ["export-moodle", str(tmp_path)])
    assert result.exit_code == 0
    assert "cli-test-001" in result.output
    assert "cli-test-002" not in result.output
```
