"""RED-phase CLI smoke test for `workflow notes sync`.

Verifies the CLI surface exists and exits zero for --dry-run.
This test MUST fail with ImportError until workflow/notes/cli.py
exposes the `sync` subcommand.
"""
from pathlib import Path

from click.testing import CliRunner

from workflow.notes.cli import notes  # noqa: F401 — RED import


def test_cli_sync_dry_run_exits_zero(tmp_path, monkeypatch):
    """Invoking `notes sync --dry-run` with a tmp vault exits 0 and prints a summary."""
    vault = tmp_path / "vault"
    vault.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    note = vault / "note.md"
    note.write_text(
        "---\nid: cli-test-note\ntitle: CLI Test\ntype: permanent\n---\nHello.\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        notes,
        ["sync", "--dry-run"],
        env={
            "WORKFLOW_VAULT_ROOT": str(vault),
            "WORKFLOW_DATA_DIR": str(data_dir),
        },
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    output_lower = result.output.lower()
    assert any(
        keyword in output_lower
        for keyword in ("dry", "scanned", "0 notes", "notes: 0", "report")
    ), f"Expected summary in output, got: {result.output!r}"
