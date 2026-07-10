"""Tests for `workflow notes migrate-relations` (ITEP-0013 F5).

LOCKED contract:
- No `relations:` key, or `relations: {}` -> SKIP, untouched.
- `relations:` is a str -> corrupted by Obsidian, FAIL LOUDLY (error, exit 1,
  file untouched). Other good notes in the same run still migrate.
- `relations:` is a nested dict -> parsed via `_parse_nested`, serialized via
  `relations_to_flat_fm`, and the `relations:` key is replaced in place by
  the flat keys. Body preserved byte-for-byte. Unrelated frontmatter keys
  preserved.
- Dropped weight/rationale reported to stderr, one line each.
- Idempotent: second run finds nothing to migrate, exit 0.
- --dry-run writes nothing, still reports the plan.
- --json emits a single JSON object on stdout, nothing else there.
- Exit 0 if nothing failed, 1 if any note failed.
"""

from __future__ import annotations

import json

from click.testing import CliRunner

from workflow.notes.cli import notes
from workflow.notes.discovery import parse_frontmatter


def _invoke(vault, args, *, catch_exceptions=True):
    runner = CliRunner()
    return runner.invoke(
        notes,
        args,
        env={"WORKFLOW_VAULT_ROOT": str(vault)},
        catch_exceptions=catch_exceptions,
    )


def _write(vault, name, fm_text, body="Body text.\n"):
    path = vault / name
    path.write_text(f"---\n{fm_text}\n---\n{body}", encoding="utf-8")
    return path


def _read_raw(path):
    fm, body = parse_frontmatter(path)
    text = path.read_text(encoding="utf-8")
    return fm, body, text


NESTED_FM = """id: aaaaaaaa1111
title: Nested Note
type: permanent
tags:
  - foo
relations:
  derived_from:
    - id: bbbbbbbb2222
      type: continuation
  links:
    - id: cccccccc3333
      type: supports"""


def test_nested_to_flat_conversion(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    path = _write(vault, "aaaaaaaa1111-nested.md", NESTED_FM)

    result = _invoke(vault, ["migrate-relations"])
    assert result.exit_code == 0, result.output

    raw, body, _ = _read_raw(path)
    assert "relations" not in raw
    assert raw["derived_from_continuation"] == ["bbbbbbbb2222"]
    assert raw["links_supports"] == ["cccccccc3333"]
    assert body == "Body text.\n"


def test_body_preserved_byte_for_byte(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    body = "Some *markdown* body.\n\nWith [[wikilinks]] and stuff.\n"
    path = _write(vault, "aaaaaaaa1111-nested.md", NESTED_FM, body=body)

    result = _invoke(vault, ["migrate-relations"])
    assert result.exit_code == 0, result.output

    _fm, got_body = parse_frontmatter(path)
    assert got_body == body


def test_unrelated_frontmatter_keys_preserved(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    path = _write(vault, "aaaaaaaa1111-nested.md", NESTED_FM)

    _invoke(vault, ["migrate-relations"])

    raw, _, _ = _read_raw(path)
    assert raw["id"] == "aaaaaaaa1111"
    assert raw["title"] == "Nested Note"
    assert raw["type"] == "permanent"
    assert raw["tags"] == ["foo"]


def test_idempotent_second_run_migrates_nothing(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    _write(vault, "aaaaaaaa1111-nested.md", NESTED_FM)

    result1 = _invoke(vault, ["migrate-relations", "--json"])
    assert result1.exit_code == 0
    data1 = json.loads(result1.stdout)
    assert len(data1["migrated"]) == 1

    result2 = _invoke(vault, ["migrate-relations", "--json"])
    assert result2.exit_code == 0
    data2 = json.loads(result2.stdout)
    assert data2["migrated"] == []
    assert data2["skipped"] == 1


def test_dry_run_writes_nothing_but_reports_plan(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    path = _write(vault, "aaaaaaaa1111-nested.md", NESTED_FM)
    before = path.read_text(encoding="utf-8")

    result = _invoke(vault, ["migrate-relations", "--dry-run", "--json"])
    assert result.exit_code == 0, result.output

    after = path.read_text(encoding="utf-8")
    assert after == before

    data = json.loads(result.stdout)
    assert len(data["migrated"]) == 1


DROPPED_FM = """id: aaaaaaaa1111
title: Dropped Note
type: permanent
relations:
  derived_from:
    - id: bbbbbbbb2222
      type: continuation
      weight: 0.9
      note: "some rationale"
"""


def test_dropped_weight_and_note_reported_to_stderr(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    _write(vault, "aaaaaaaa1111-dropped.md", DROPPED_FM)

    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["migrate-relations"],
        env={"WORKFLOW_VAULT_ROOT": str(vault)},
        catch_exceptions=True,
    )
    assert result.exit_code == 0, result.output
    assert "dropped weight=0.9 on aaaaaaaa1111 -> bbbbbbbb2222" in result.stderr
    assert "dropped note=" in result.stderr
    assert "bbbbbbbb2222" in result.stderr


CORRUPTED_FM = """id: aaaaaaaa1111
title: Corrupted Note
type: permanent
relations: "some-string-obsidian-wrote"
"""


def test_corrupted_str_relations_fails_loudly_others_still_migrate(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    bad_path = _write(vault, "aaaaaaaa1111-corrupt.md", CORRUPTED_FM)
    good_fm = """id: eeeeeeee4444
title: Good Note
type: permanent
relations:
  derived_from:
    - id: ffffffff5555
      type: continuation
"""
    good_path = _write(vault, "eeeeeeee4444-good.md", good_fm)

    before_bad = bad_path.read_text(encoding="utf-8")

    result = _invoke(vault, ["migrate-relations", "--json"])
    assert result.exit_code == 1, result.output

    data = json.loads(result.stdout)
    assert len(data["failed"]) == 1
    assert "restore" in data["failed"][0]["reason"].lower() or "git" in data["failed"][0]["reason"].lower()
    assert str(bad_path) == data["failed"][0]["path"]
    assert len(data["migrated"]) == 1

    # Bad file untouched
    assert bad_path.read_text(encoding="utf-8") == before_bad
    # Good file migrated
    raw, _, _ = _read_raw(good_path)
    assert "relations" not in raw
    assert raw["derived_from_continuation"] == ["ffffffff5555"]


def test_note_without_relations_key_skipped(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    fm = """id: aaaaaaaa1111
title: No Relations
type: permanent
"""
    path = _write(vault, "aaaaaaaa1111-norel.md", fm)
    before = path.read_text(encoding="utf-8")

    result = _invoke(vault, ["migrate-relations", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["migrated"] == []
    assert data["skipped"] == 1

    assert path.read_text(encoding="utf-8") == before


def test_empty_relations_dict_skipped(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    fm = """id: aaaaaaaa1111
title: Empty Relations
type: permanent
relations: {}
"""
    path = _write(vault, "aaaaaaaa1111-emptyrel.md", fm)

    result = _invoke(vault, ["migrate-relations", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["migrated"] == []
    assert data["skipped"] == 1


def test_json_shape_and_stdout_purity(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    _write(vault, "aaaaaaaa1111-nested.md", NESTED_FM)

    result = _invoke(vault, ["migrate-relations", "--json"])
    assert result.exit_code == 0, result.output

    # stdout must be pure JSON — exactly one json.loads call succeeds on
    # the whole output.
    data = json.loads(result.stdout)
    assert set(data.keys()) == {"scanned", "migrated", "skipped", "failed", "dropped"}
    assert isinstance(data["scanned"], int)
    assert isinstance(data["migrated"], list)
    assert isinstance(data["skipped"], int)
    assert isinstance(data["failed"], list)
    assert isinstance(data["dropped"], list)


# ---------------------------------------------------------------------------
# Regression (ITEP-0013 F5): a numeric timestamp-style id must NOT be dropped.
# YAML parses bare digits as int; the nested/flat parsers used to skip them,
# turning migration into permanent, silent edge deletion.
# ---------------------------------------------------------------------------

NUMERIC_MIX_FM = """id: aaaaaaaa1111
title: Mixed ids
type: permanent
relations:
  derived_from:
    - id: 0dJk2mPq91xA
      type: refines
  links:
    - id: 202604010900
      type: supports
"""


def test_numeric_id_edge_survives_migration(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    path = _write(vault, "aaaaaaaa1111-mix.md", NUMERIC_MIX_FM)

    result = _invoke(vault, ["migrate-relations", "--json"])
    assert result.exit_code == 0, result.output

    raw, _body, text = _read_raw(path)
    # BOTH keys must survive — the numeric id edge is NOT lost.
    assert raw["derived_from_refines"] == ["0dJk2mPq91xA"]
    assert raw["links_supports"] == ["202604010900"]
    # And the digit id must be a string in the file (quoted), not a bare int.
    assert "links_supports" in text
    assert "'202604010900'" in text

    data = json.loads(result.stdout)
    assert len(data["migrated"]) == 1
    assert data["failed"] == []
