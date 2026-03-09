"""Tests for itep.ioconfig — minimal config.yaml I/O."""

from itep.ioconfig import save_config, read_pointer


class TestSaveConfig:
    def test_save_and_read_pointer(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        save_config("lecture", 42, config_file)

        data = read_pointer(config_file)
        assert data["project_type"] == "lecture"
        assert data["project_id"] == 42

    def test_save_general(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        save_config("general", 7, config_file)

        data = read_pointer(config_file)
        assert data["project_type"] == "general"
        assert data["project_id"] == 7

    def test_config_file_content_is_minimal(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        save_config("lecture", 1, config_file)

        text = config_file.read_text()
        assert "project_type" in text
        assert "project_id" in text
        # Should NOT contain the old full config keys
        assert "abs_parent_dir" not in text
        assert "admin" not in text
