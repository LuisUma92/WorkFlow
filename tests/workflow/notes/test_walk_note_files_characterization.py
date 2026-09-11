"""Characterization tests for `walk_note_files` (discovery.py).

Pins the CURRENT behaviour of every branch not already covered by the
existing test suite, ahead of a behaviour-preserving complexity refactor
(flake8 C901). These tests must pass against the UNCHANGED implementation
and continue to pass after the refactor.

Covers:
- root does not exist / is not a directory -> yields nothing.
- a subdirectory that raises PermissionError/OSError on iterdir() is
  skipped, but sibling directories still walk normally.
- a directory symlink encountered during recursion (not just at the
  top level) is skipped -- its contents are never yielded.
- a .md file whose resolved path escapes *root* is dropped silently
  (covers both the "escaped" branch and the OSError/ValueError guard
  around `entry.resolve()`).
- baseline recursive discovery + ordering sanity, to anchor the parts
  of the function that were already covered.
"""
from __future__ import annotations

import pathlib

import pytest

from workflow.notes.discovery import walk_note_files


def test_root_missing_yields_nothing(tmp_path):
    missing = tmp_path / "does-not-exist"
    assert list(walk_note_files(missing)) == []


def test_root_is_a_file_yields_nothing(tmp_path):
    a_file = tmp_path / "not-a-dir.md"
    a_file.write_text("---\n---\nbody")
    assert list(walk_note_files(a_file)) == []


def test_baseline_recursive_discovery_and_ordering(tmp_path):
    root = tmp_path / "vault"
    (root / "sub").mkdir(parents=True)
    (root / "note-b.md").write_text("b")
    (root / "note-a.md").write_text("a")
    (root / "sub" / "note-c.md").write_text("c")
    (root / "ignore.txt").write_text("not markdown")

    found = {p.name for p in walk_note_files(root)}
    assert found == {"note-a.md", "note-b.md", "note-c.md"}


def test_subdir_permission_error_is_skipped_siblings_still_walk(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    bad_dir = root / "bad"
    good_dir = root / "good"
    bad_dir.mkdir(parents=True)
    good_dir.mkdir(parents=True)
    (good_dir / "reachable.md").write_text("ok")
    (bad_dir / "unreachable.md").write_text("should not be yielded")

    original_iterdir = pathlib.Path.iterdir

    def flaky_iterdir(self):
        if self.name == "bad":
            raise PermissionError("simulated permission error")
        return original_iterdir(self)

    monkeypatch.setattr(pathlib.Path, "iterdir", flaky_iterdir)

    found = {p.name for p in walk_note_files(root)}
    assert found == {"reachable.md"}


def test_subdir_generic_oserror_is_skipped(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    bad_dir = root / "bad"
    bad_dir.mkdir(parents=True)
    (root / "top.md").write_text("top")

    original_iterdir = pathlib.Path.iterdir

    def flaky_iterdir(self):
        if self.name == "bad":
            raise OSError("simulated generic OSError")
        return original_iterdir(self)

    monkeypatch.setattr(pathlib.Path, "iterdir", flaky_iterdir)

    found = {p.name for p in walk_note_files(root)}
    assert found == {"top.md"}


def test_directory_symlink_during_recursion_is_skipped(tmp_path):
    root = tmp_path / "vault"
    sub = root / "sub"
    sub.mkdir(parents=True)
    target_dir = tmp_path / "outside-target"
    target_dir.mkdir()
    (target_dir / "hidden-by-symlink.md").write_text("should not appear")

    link = sub / "linked_dir"
    link.symlink_to(target_dir, target_is_directory=True)

    (sub / "visible.md").write_text("visible")

    found = {p.name for p in walk_note_files(root)}
    assert found == {"visible.md"}


def test_md_symlink_escaping_root_is_dropped(tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("outside content")

    escaping_link = root / "escapes.md"
    escaping_link.symlink_to(outside)

    (root / "inside.md").write_text("inside content")

    found = {p.name for p in walk_note_files(root)}
    assert found == {"inside.md"}


def test_resolve_oserror_on_md_file_is_dropped(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    (root / "good.md").write_text("good")
    (root / "boom.md").write_text("boom")

    original_resolve = pathlib.Path.resolve

    def flaky_resolve(self, *args, **kwargs):
        if self.name == "boom.md":
            raise OSError("simulated resolve failure")
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "resolve", flaky_resolve)

    found = {p.name for p in walk_note_files(root)}
    assert found == {"good.md"}


def test_resolve_valueerror_on_md_file_is_dropped(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    (root / "good.md").write_text("good")
    (root / "boom.md").write_text("boom")

    original_resolve = pathlib.Path.resolve

    def flaky_resolve(self, *args, **kwargs):
        if self.name == "boom.md":
            raise ValueError("simulated resolve failure")
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "resolve", flaky_resolve)

    found = {p.name for p in walk_note_files(root)}
    assert found == {"good.md"}


def test_hidden_and_skip_named_directories_are_pruned(tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    for name in (".git", ".obsidian", "images", "__pycache__", "node_modules", "templates"):
        d = root / name
        d.mkdir()
        (d / "should-not-appear.md").write_text("skip me")

    (root / "kept.md").write_text("kept")

    found = {p.name for p in walk_note_files(root)}
    assert found == {"kept.md"}


@pytest.fixture
def empty_dir(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    return d


def test_empty_root_yields_nothing(empty_dir):
    assert list(walk_note_files(empty_dir)) == []
