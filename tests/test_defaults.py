"""Tests for itep.defaults — verifies no hardcoded paths."""
import importlib
from pathlib import Path


def test_defaults_physics_dir_is_path():
    from itep.defaults import DEF_ABS_PARENT_DIR
    assert isinstance(DEF_ABS_PARENT_DIR, Path)


def test_defaults_physics_dir_env_override(monkeypatch):
    monkeypatch.setenv("WORKFLOW_PHYSICS_DIR", "/tmp/test-physics")
    import itep.defaults
    importlib.reload(itep.defaults)
    assert str(itep.defaults.DEF_ABS_PARENT_DIR) == "/tmp/test-physics"
    # restore module state for subsequent tests
    monkeypatch.delenv("WORKFLOW_PHYSICS_DIR", raising=False)
    importlib.reload(itep.defaults)


def test_defaults_physics_dir_default_uses_home():
    import os
    import itep.defaults
    importlib.reload(itep.defaults)
    # Only test default if env var is not set
    if "WORKFLOW_PHYSICS_DIR" not in os.environ:
        assert str(Path.home()) in str(itep.defaults.DEF_ABS_PARENT_DIR)
