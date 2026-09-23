from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

import apache_log_shipper
import runtime_config
from runtime_config import RuntimeConfigError


def test_shipper_import_does_not_resolve_db_config(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_resolved():
        raise AssertionError("DB config must not resolve at import time")

    monkeypatch.setattr(runtime_config, "resolve_shipper_db_config", fail_if_resolved)
    path = Path(apache_log_shipper.__file__)
    spec = importlib.util.spec_from_file_location("shipper_import_probe", path)
    assert spec is not None and spec.loader is not None
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)

    assert probe.CONFIG == {}


def test_shipper_uses_separate_writer_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHIPPER_DB_USER", "log_writer")
    monkeypatch.setenv("SHIPPER_DB_PASSWORD", "writer-secret")
    monkeypatch.setenv("DB_HOST", "shipper-host")

    assert apache_log_shipper.CONFIG == {}
    apache_log_shipper.configure_runtime()

    assert apache_log_shipper.CONFIG["db"]["user"] == "log_writer"
    assert apache_log_shipper.CONFIG["db"]["password"] == "writer-secret"
    assert apache_log_shipper.CONFIG["db"]["host"] == "shipper-host"


def test_shipper_rejects_reader_credential_before_insert(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHIPPER_DB_USER", "log_reader")
    monkeypatch.setenv("SHIPPER_DB_PASSWORD", "reader-secret")
    monkeypatch.setenv("DB_HOST", "shipper-host")

    with pytest.raises(RuntimeConfigError, match="must not be log_reader"):
        apache_log_shipper.configure_runtime()
