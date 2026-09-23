from __future__ import annotations

from pathlib import Path

import export_db_logs_cli
from web.services.analysis_job_repository import get_app_db_config
from web.services.live_log_repository import get_live_log_db_config


def test_repository_and_live_getters_do_not_reload_env_file(monkeypatch, tmp_path: Path) -> None:
    import src.runtime_config as runtime_config

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / ".env").write_text("BROKEN\n", encoding="utf-8")
    monkeypatch.setattr(runtime_config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("DB_HOST", "db-host")
    monkeypatch.setenv("DB_PORT", "3306")
    monkeypatch.setenv("DB_NAME", "web_logs")
    monkeypatch.setenv("APP_DB_USER", "analysis_app")
    monkeypatch.setenv("APP_DB_PASSWORD", "app-password")
    monkeypatch.delenv("LOG_DB_HOST", raising=False)
    monkeypatch.delenv("LOG_DB_PORT", raising=False)
    monkeypatch.delenv("LOG_DB_NAME", raising=False)
    monkeypatch.setenv("LOG_DB_USER", "log_reader")
    monkeypatch.setenv("LOG_DB_PASSWORD", "reader-password")

    assert get_app_db_config()["host"] == "db-host"
    assert get_live_log_db_config()["host"] == "db-host"


def test_export_interactive_uses_resolved_log_reader_port(monkeypatch) -> None:
    monkeypatch.setenv("DB_HOST", "db-host")
    monkeypatch.setenv("LOG_DB_PORT", "3311")
    monkeypatch.setenv("LOG_DB_USER", "log_reader")
    monkeypatch.setenv("LOG_DB_PASSWORD", "reader-password")
    defaults: dict[str, str | None] = {}

    def answer(prompt: str, default: str | None = None, secret: bool = False) -> str:
        del secret
        defaults[prompt] = default
        return default or ""

    monkeypatch.setattr(export_db_logs_cli, "ask_input", answer)
    args = export_db_logs_cli.build_args_from_interactive()

    assert defaults["DB port"] == "3311"
    assert args.port == 3311
