from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from runtime_config import (
    RuntimeConfigError,
    db_config_diagnostic_lines,
    db_override_warnings,
    load_project_env,
    parse_project_env_file,
    resolve_app_db_config,
    resolve_log_reader_db_config,
    resolve_shipper_db_config,
    validate_database_config,
)


def write_env(root: Path, text: str) -> None:
    config = root / "config"
    config.mkdir()
    (config / ".env").write_text(text, encoding="utf-8")


def test_process_environment_wins_and_missing_value_is_loaded(tmp_path: Path) -> None:
    write_env(tmp_path, "DB_HOST=file-host\nLOG_DB_PASSWORD=a=b=c\n")
    env = {"DB_HOST": "process-host"}

    loaded = load_project_env(tmp_path, environ=env)

    assert env == {"DB_HOST": "process-host", "LOG_DB_PASSWORD": "a=b=c"}
    assert loaded.applied_keys == ("LOG_DB_PASSWORD",)


def test_parser_supports_first_equals_quotes_and_quoted_spaces(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "PASSWORD=a=b=c\nQUOTED=\"value\"\nSINGLE='other'\nSPACES=\"hello world\"\n# comment\n",
        encoding="utf-8",
    )

    assert parse_project_env_file(path) == {
        "PASSWORD": "a=b=c",
        "QUOTED": "value",
        "SINGLE": "other",
        "SPACES": "hello world",
    }


@pytest.mark.parametrize(
    "text",
    (
        "BROKEN\n",
        "DB_HOST =host\n",
        "DB_HOST= host\n",
        "DB_HOST = host\n",
        "export DB_HOST=host\n",
        "invalid-key=host\n",
        "DB_HOST=$VAR\n",
        "DB_HOST=$(hostname)\n",
        "DB_HOST=${HOST}\n",
        "DB_HOST=`hostname`\n",
        "DB_HOST=$1\n",
        "DB_HOST=$$\n",
        "DB_HOST=$?\n",
        "DB_HOST=$!\n",
        "DB_HOST=one\nDB_HOST=two\n",
    ),
)
def test_parser_rejects_unsupported_or_ambiguous_syntax(tmp_path: Path, text: str) -> None:
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(RuntimeConfigError):
        parse_project_env_file(path)


def test_database_resolution_records_fallback_provenance_and_keeps_credentials_separate() -> None:
    env = {
        "DB_HOST": "shared-host",
        "DB_PORT": "3307",
        "DB_NAME": "web_logs",
        "LOG_DB_HOST": "reader-host",
        "LOG_DB_USER": "log_reader",
        "LOG_DB_PASSWORD": "reader-secret",
        "APP_DB_USER": "analysis_app",
        "APP_DB_PASSWORD": "app-secret",
        "SHIPPER_DB_USER": "log_writer",
        "SHIPPER_DB_PASSWORD": "writer-secret",
    }

    reader = resolve_log_reader_db_config(env)
    app = resolve_app_db_config(env)
    shipper = resolve_shipper_db_config(env)

    assert (reader.host.value, reader.host.source) == ("reader-host", "LOG_DB_HOST")
    assert (reader.port.value, reader.port.source) == ("3307", "DB_PORT")
    assert (app.host.value, app.host.source) == ("shared-host", "DB_HOST")
    assert app.password.value == "app-secret"
    assert shipper.password.value == "writer-secret"
    assert db_override_warnings(env) == ["LOG_DB_HOST overrides DB_HOST"]


def test_app_password_never_falls_back_to_reader_password() -> None:
    app = resolve_app_db_config({"DB_HOST": "host", "APP_DB_USER": "analysis_app", "LOG_DB_PASSWORD": "reader"})

    assert app.password.value == ""
    with pytest.raises(RuntimeConfigError, match="password"):
        validate_database_config(app)


def test_shipper_rejects_reader_account_before_write() -> None:
    shipper = resolve_shipper_db_config(
        {"DB_HOST": "host", "SHIPPER_DB_USER": "log_reader", "SHIPPER_DB_PASSWORD": "secret"}
    )

    with pytest.raises(RuntimeConfigError, match="must not be log_reader"):
        validate_database_config(shipper, require_writer=True)


def test_diagnostics_do_not_include_password_values() -> None:
    config = resolve_log_reader_db_config(
        {"DB_HOST": "host", "LOG_DB_USER": "log_reader", "LOG_DB_PASSWORD": "not-for-output"}
    )

    output = "\n".join(db_config_diagnostic_lines((config,)))

    assert "not-for-output" not in output
    assert "password=<set>" in output


def test_db_environment_resolution_only_lives_in_runtime_config() -> None:
    root = Path(__file__).resolve().parents[1]
    forbidden = ('os.getenv("DB_', 'os.getenv("LOG_DB_', 'os.getenv("APP_DB_', 'os.getenv("SHIPPER_DB_')
    for path in list((root / "src").glob("*.py")) + list((root / "web").rglob("*.py")):
        if path == root / "src" / "runtime_config.py":
            continue
        source = path.read_text(encoding="utf-8")
        assert not any(token in source for token in forbidden), path


def test_worker_unit_is_an_always_on_restartable_service_template() -> None:
    root = Path(__file__).resolve().parents[1]
    unit = (root / "ops/systemd/web-log-analysis-worker.service.example").read_text(encoding="utf-8")

    assert "EnvironmentFile=/opt/web_log_analysis/config/.env" in unit
    assert "WorkingDirectory=/opt/web_log_analysis" in unit
    assert "--run-pipeline" in unit
    assert "--once" not in unit
    assert "Wants=network-online.target" in unit
    assert "After=network-online.target" in unit
    assert "Restart=on-failure" in unit
    assert "RestartPreventExitStatus=78" in unit
    assert "StartLimitIntervalSec=0" in unit


def test_web_module_import_does_not_load_project_env(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    for key in tuple(env):
        if key in {"KNOWN_ASSET_IPS"} or key.startswith(("DB_", "LOG_DB_", "APP_DB_", "SHIPPER_DB_")):
            env.pop(key)
    env["PYTHONPATH"] = str(root)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os; import web.app; "
            "print(any(k.startswith(('DB_', 'LOG_DB_', 'APP_DB_', 'SHIPPER_DB_')) or k == 'KNOWN_ASSET_IPS' for k in os.environ))",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        check=True,
        text=True,
    )

    assert result.stdout.strip() == "False"
