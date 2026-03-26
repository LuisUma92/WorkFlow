"""Tests for workflow.tikz.builder — source discovery and hashing."""

from __future__ import annotations

from pathlib import Path

import pytest

from workflow.tikz.builder import compute_hash, find_tikz_sources


class TestFindTikzSources:
    def test_find_tikz_sources(self, tmp_path: Path) -> None:
        """find_tikz_sources returns .tex files from the directory."""
        (tmp_path / "a.tex").write_text("\\tikz{}")
        (tmp_path / "b.tex").write_text("\\tikz{}")
        (tmp_path / "readme.md").write_text("not tex")

        sources = find_tikz_sources(tmp_path)

        assert len(sources) == 2
        names = {p.name for p in sources}
        assert names == {"a.tex", "b.tex"}

    def test_find_tikz_sources_empty(self, tmp_path: Path) -> None:
        """Empty directory returns empty list."""
        sources = find_tikz_sources(tmp_path)
        assert sources == []

    def test_find_tikz_sources_nested(self, tmp_path: Path) -> None:
        """find_tikz_sources recurses into subdirectories."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.tex").write_text("\\tikz{}")
        (tmp_path / "top.tex").write_text("\\tikz{}")

        sources = find_tikz_sources(tmp_path)

        assert len(sources) == 2

    def test_find_tikz_sources_sorted(self, tmp_path: Path) -> None:
        """Results are sorted deterministically."""
        (tmp_path / "z.tex").write_text("")
        (tmp_path / "a.tex").write_text("")

        sources = find_tikz_sources(tmp_path)

        assert sources == sorted(sources)


class TestComputeHash:
    def test_compute_hash_deterministic(self, tmp_path: Path) -> None:
        """Same file contents produce the same hash."""
        f = tmp_path / "file.tex"
        f.write_bytes(b"hello world")

        h1 = compute_hash(f)
        h2 = compute_hash(f)

        assert h1 == h2

    def test_compute_hash_changes_with_content(self, tmp_path: Path) -> None:
        """Hash changes when file content changes."""
        f = tmp_path / "file.tex"
        f.write_bytes(b"original")
        h1 = compute_hash(f)

        f.write_bytes(b"modified")
        h2 = compute_hash(f)

        assert h1 != h2

    def test_compute_hash_is_sha256(self, tmp_path: Path) -> None:
        """Hash is a 64-character hex string (SHA-256)."""
        f = tmp_path / "file.tex"
        f.write_bytes(b"content")

        h = compute_hash(f)

        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)
