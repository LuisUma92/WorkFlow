"""Lecture project management for WorkFlow.

Provides:
- scanner: discover and register .tex files as notes
- linker: extract cross-references and citations; update Link/Citation tables
- note_splitter: split a notes file at %> markers into separate files
- eval_builder: build evaluation spec from taxonomy criteria
- cli: Click command group — scan, split, link, build-eval
"""
