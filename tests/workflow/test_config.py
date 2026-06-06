"""Tests for workflow.config — config.yaml reader with env > config > default precedence."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_config(tmp_path: Path, data: dict) -> Path:
    """Write *data* as YAML to ``<tmp_path>/config.yaml`` and return the path."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.dump(data), encoding="utf-8")
    return cfg


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_missing_file_returns_empty_dict(self, tmp_path, monkeypatch):
        """Missing config.yaml → load_config() returns {}."""
        import workflow.paths as wp
        monkeypatch.setattr(wp, "config_dir", lambda: tmp_path)

        from workflow import config as cfg
        assert cfg.load_config() == {}

    def test_reads_known_keys(self, tmp_path, monkeypatch):
        """config.yaml with known keys is read correctly."""
        import workflow.paths as wp
        monkeypatch.setattr(wp, "config_dir", lambda: tmp_path)

        _write_config(tmp_path, {
            "vault_path": "/some/vault",
            "default_institution": "UCIMED",
            "default_timezone": "America/Costa_Rica",
        })

        from workflow import config as cfg
        data = cfg.load_config()
        assert data["vault_path"] == "/some/vault"
        assert data["default_institution"] == "UCIMED"
        assert data["default_timezone"] == "America/Costa_Rica"

    def test_unknown_keys_passed_through(self, tmp_path, monkeypatch):
        """Unknown keys are not dropped."""
        import workflow.paths as wp
        monkeypatch.setattr(wp, "config_dir", lambda: tmp_path)

        _write_config(tmp_path, {"vault_path": "/v", "extra_key": "hello"})

        from workflow import config as cfg
        data = cfg.load_config()
        assert data.get("extra_key") == "hello"

    def test_empty_file_returns_empty_dict(self, tmp_path, monkeypatch):
        """Empty config.yaml (null YAML) → {}."""
        import workflow.paths as wp
        monkeypatch.setattr(wp, "config_dir", lambda: tmp_path)

        (tmp_path / "config.yaml").write_text("", encoding="utf-8")

        from workflow import config as cfg
        assert cfg.load_config() == {}

    def test_malformed_yaml_raises_value_error(self, tmp_path, monkeypatch):
        """Invalid YAML → ValueError with clear message."""
        import workflow.paths as wp
        monkeypatch.setattr(wp, "config_dir", lambda: tmp_path)

        (tmp_path / "config.yaml").write_text("::: not yaml :::", encoding="utf-8")

        from workflow import config as cfg
        with pytest.raises(ValueError, match="Malformed config.yaml"):
            cfg.load_config()

    def test_top_level_list_raises_value_error(self, tmp_path, monkeypatch):
        """Top-level YAML list (not a mapping) → ValueError."""
        import workflow.paths as wp
        monkeypatch.setattr(wp, "config_dir", lambda: tmp_path)

        (tmp_path / "config.yaml").write_text("- item1\n- item2\n", encoding="utf-8")

        from workflow import config as cfg
        with pytest.raises(ValueError, match="Malformed config.yaml"):
            cfg.load_config()


# ---------------------------------------------------------------------------
# get_vault_path
# ---------------------------------------------------------------------------

class TestGetVaultPath:
    def test_returns_default_when_no_config_no_env(self, tmp_path, monkeypatch):
        """No env, no config → returns the built-in default."""
        import workflow.paths as wp
        monkeypatch.setattr(wp, "config_dir", lambda: tmp_path)
        monkeypatch.delenv("WORKFLOW_VAULT_ROOT", raising=False)

        from workflow import config as cfg
        result = cfg.get_vault_path("/default/vault")
        assert result == Path("/default/vault")

    def test_config_vault_path_beats_default(self, tmp_path, monkeypatch):
        """config.yaml vault_path overrides built-in default."""
        import workflow.paths as wp
        monkeypatch.setattr(wp, "config_dir", lambda: tmp_path)
        monkeypatch.delenv("WORKFLOW_VAULT_ROOT", raising=False)

        _write_config(tmp_path, {"vault_path": "/config/vault"})

        from workflow import config as cfg
        result = cfg.get_vault_path("/default/vault")
        assert result == Path("/config/vault")

    def test_env_beats_config(self, tmp_path, monkeypatch):
        """WORKFLOW_VAULT_ROOT env beats config.yaml vault_path."""
        import workflow.paths as wp
        monkeypatch.setattr(wp, "config_dir", lambda: tmp_path)
        monkeypatch.setenv("WORKFLOW_VAULT_ROOT", "/env/vault")

        _write_config(tmp_path, {"vault_path": "/config/vault"})

        from workflow import config as cfg
        result = cfg.get_vault_path("/default/vault")
        assert result == Path("/env/vault")

    def test_env_beats_default_no_config(self, tmp_path, monkeypatch):
        """WORKFLOW_VAULT_ROOT env beats default even when no config file."""
        import workflow.paths as wp
        monkeypatch.setattr(wp, "config_dir", lambda: tmp_path)
        monkeypatch.setenv("WORKFLOW_VAULT_ROOT", "/env/vault")

        from workflow import config as cfg
        result = cfg.get_vault_path("/default/vault")
        assert result == Path("/env/vault")


# ---------------------------------------------------------------------------
# get_default_institution
# ---------------------------------------------------------------------------

class TestGetDefaultInstitution:
    def test_returns_default_when_no_config(self, tmp_path, monkeypatch):
        """No config file → returns the built-in default string."""
        import workflow.paths as wp
        monkeypatch.setattr(wp, "config_dir", lambda: tmp_path)

        from workflow import config as cfg
        assert cfg.get_default_institution("UCR") == "UCR"

    def test_config_value_beats_default(self, tmp_path, monkeypatch):
        """config.yaml default_institution overrides built-in default."""
        import workflow.paths as wp
        monkeypatch.setattr(wp, "config_dir", lambda: tmp_path)

        _write_config(tmp_path, {"default_institution": "UCIMED"})

        from workflow import config as cfg
        assert cfg.get_default_institution("UCR") == "UCIMED"

    def test_empty_config_key_returns_default(self, tmp_path, monkeypatch):
        """Empty string value in config → returns built-in default."""
        import workflow.paths as wp
        monkeypatch.setattr(wp, "config_dir", lambda: tmp_path)

        _write_config(tmp_path, {"default_institution": ""})

        from workflow import config as cfg
        assert cfg.get_default_institution("UCR") == "UCR"


# ---------------------------------------------------------------------------
# get_default_timezone
# ---------------------------------------------------------------------------

class TestGetDefaultTimezone:
    def test_returns_default_when_no_config(self, tmp_path, monkeypatch):
        """No config file → returns the built-in default."""
        import workflow.paths as wp
        monkeypatch.setattr(wp, "config_dir", lambda: tmp_path)

        from workflow import config as cfg
        assert cfg.get_default_timezone("UTC") == "UTC"

    def test_config_value_beats_default(self, tmp_path, monkeypatch):
        """config.yaml default_timezone overrides built-in default."""
        import workflow.paths as wp
        monkeypatch.setattr(wp, "config_dir", lambda: tmp_path)

        _write_config(tmp_path, {"default_timezone": "America/Costa_Rica"})

        from workflow import config as cfg
        assert cfg.get_default_timezone("UTC") == "America/Costa_Rica"


# ---------------------------------------------------------------------------
# resolve_vault_root end-to-end precedence (via vault.paths)
# ---------------------------------------------------------------------------

class TestResolveVaultRootPrecedence:
    def test_env_set_returns_env(self, tmp_path, monkeypatch):
        """(a) WORKFLOW_VAULT_ROOT set → resolve_vault_root returns env value."""
        import workflow.paths as wp
        monkeypatch.setattr(wp, "config_dir", lambda: tmp_path)
        monkeypatch.setenv("WORKFLOW_VAULT_ROOT", str(tmp_path / "env_vault"))

        import workflow.vault.paths as vp
        assert vp.resolve_vault_root() == Path(str(tmp_path / "env_vault")).expanduser().resolve()

    def test_env_unset_config_set_returns_config(self, tmp_path, monkeypatch):
        """(b) Env unset + config vault_path set → resolve_vault_root returns config value."""
        import workflow.paths as wp
        monkeypatch.setattr(wp, "config_dir", lambda: tmp_path)
        monkeypatch.delenv("WORKFLOW_VAULT_ROOT", raising=False)

        config_vault = tmp_path / "config_vault"
        _write_config(tmp_path, {"vault_path": str(config_vault)})

        import workflow.vault.paths as vp
        assert vp.resolve_vault_root() == config_vault.resolve()

    def test_both_unset_returns_default(self, tmp_path, monkeypatch):
        """(c) Both unset → resolve_vault_root returns DEFAULT_VAULT_ROOT."""
        import workflow.paths as wp
        monkeypatch.setattr(wp, "config_dir", lambda: tmp_path)
        monkeypatch.delenv("WORKFLOW_VAULT_ROOT", raising=False)

        import workflow.vault.paths as vp
        assert vp.resolve_vault_root() == vp.DEFAULT_VAULT_ROOT

    def test_env_beats_config_in_vault_paths(self, tmp_path, monkeypatch):
        """Env wins even when config.yaml also has vault_path."""
        import workflow.paths as wp
        monkeypatch.setattr(wp, "config_dir", lambda: tmp_path)
        env_vault = tmp_path / "env_vault"
        monkeypatch.setenv("WORKFLOW_VAULT_ROOT", str(env_vault))

        _write_config(tmp_path, {"vault_path": str(tmp_path / "config_vault")})

        import workflow.vault.paths as vp
        assert vp.resolve_vault_root() == env_vault.resolve()
