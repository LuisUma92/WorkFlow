"""Tests for workflow.topic.import_formatters — TDD, no DB required."""
from __future__ import annotations

import json

import pytest

from workflow.topic.import_types import ImportResult, RowError
from workflow.topic.import_formatters import format_import_json, format_import_table


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def result_clean() -> ImportResult:
    """2 topics, 4 contents, 18 concepts, 0 skipped, 0 errors, real run."""
    return ImportResult(created_topics=2, created_contents=4, created_concepts=18)


@pytest.fixture
def result_with_error() -> ImportResult:
    """Result carrying one RowError."""
    err = RowError(entity="concept", row="FS01-X-001", reason="duplicate code")
    return ImportResult(
        created_topics=1,
        created_contents=2,
        created_concepts=5,
        skipped=1,
        errors=(err,),
    )


@pytest.fixture
def result_dry_run() -> ImportResult:
    """Dry-run result, 3 topics, 6 contents, 12 concepts, 2 skipped."""
    return ImportResult(
        created_topics=3,
        created_contents=6,
        created_concepts=12,
        skipped=2,
        dry_run=True,
    )


# ---------------------------------------------------------------------------
# format_import_json
# ---------------------------------------------------------------------------

class TestFormatImportJson:
    def test_clean_result_shape(self, result_clean: ImportResult) -> None:
        """JSON round-trip; exact created counts, zero skipped, empty errors."""
        raw = format_import_json(result_clean)
        data = json.loads(raw)

        assert data["created"] == {"topics": 2, "contents": 4, "concepts": 18}
        assert data["skipped"] == 0
        assert data["errors"] == []

    def test_error_list_shape(self, result_with_error: ImportResult) -> None:
        """errors list contains dicts with entity/row/reason keys."""
        raw = format_import_json(result_with_error)
        data = json.loads(raw)

        assert len(data["errors"]) == 1
        err = data["errors"][0]
        assert err["entity"] == "concept"
        assert err["row"] == "FS01-X-001"
        assert err["reason"] == "duplicate code"

    def test_skipped_count_included(self, result_with_error: ImportResult) -> None:
        """skipped field reflects ImportResult.skipped."""
        data = json.loads(format_import_json(result_with_error))
        assert data["skipped"] == 1

    def test_top_level_keys_only(self, result_clean: ImportResult) -> None:
        """Exactly three top-level keys: created, skipped, errors."""
        data = json.loads(format_import_json(result_clean))
        assert set(data.keys()) == {"created", "skipped", "errors"}

    def test_valid_json_string(self, result_clean: ImportResult) -> None:
        """Output must be parseable JSON."""
        raw = format_import_json(result_clean)
        assert isinstance(raw, str)
        json.loads(raw)  # raises if invalid


# ---------------------------------------------------------------------------
# format_import_table
# ---------------------------------------------------------------------------

class TestFormatImportTable:
    def test_dry_run_prefix(self, result_dry_run: ImportResult) -> None:
        """Dry-run output starts with [DRY-RUN] Would create."""
        out = format_import_table(result_dry_run)
        assert out.startswith("[DRY-RUN] Would create")

    def test_dry_run_counts(self, result_dry_run: ImportResult) -> None:
        """Dry-run summary includes all three counts and skipped."""
        out = format_import_table(result_dry_run)
        assert "3 topics" in out
        assert "6 contents" in out
        assert "12 concepts" in out
        assert "2 skipped" in out

    def test_real_run_prefix(self, result_clean: ImportResult) -> None:
        """Real run starts with 'Created', no [DRY-RUN] prefix."""
        out = format_import_table(result_clean)
        assert out.startswith("Created")
        assert "[DRY-RUN]" not in out

    def test_real_run_no_error_section(self, result_clean: ImportResult) -> None:
        """No [ERROR] lines when there are no errors."""
        out = format_import_table(result_clean)
        assert "[ERROR]" not in out

    def test_error_lines_present(self, result_with_error: ImportResult) -> None:
        """Each RowError produces an [ERROR] line with entity, row, reason."""
        out = format_import_table(result_with_error)
        assert "[ERROR] concept FS01-X-001:" in out
        assert "duplicate code" in out

    def test_error_lines_indented(self, result_with_error: ImportResult) -> None:
        """Error lines are indented with two spaces."""
        lines = format_import_table(result_with_error).splitlines()
        error_lines = [ln for ln in lines if "[ERROR]" in ln]
        assert len(error_lines) == 1
        assert error_lines[0].startswith("  [ERROR]")

    def test_returns_string(self, result_clean: ImportResult) -> None:
        """Return type is str (not None, not printed)."""
        out = format_import_table(result_clean)
        assert isinstance(out, str)
