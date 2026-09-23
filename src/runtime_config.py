"""Shared runtime configuration for DB-backed entry points.

Only a deliberately small ``config/.env`` subset is supported.  The same
file can therefore be consumed by systemd's ``EnvironmentFile=`` and by a
manual Python invocation without shell evaluation.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, MutableMapping, Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
UNSUPPORTED_SHELL_RE = re.compile(r"[`$]")


class RuntimeConfigError(ValueError):
    """Raised for a project-supported configuration contract violation."""


@dataclass(frozen=True)
class LoadedProjectEnv:
    path: Path
    file_values: Mapping[str, str]
    applied_keys: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedValue:
    value: str
    source: str

    @property
    def is_set(self) -> bool:
        return bool(self.value)


@dataclass(frozen=True)
class DatabaseRuntimeConfig:
    role: str
    host: ResolvedValue
    port: ResolvedValue
    database: ResolvedValue
    user: ResolvedValue
    password: ResolvedValue

    def connection_kwargs(self, *, autocommit: bool) -> dict[str, object]:
        return {
            "host": self.host.value,
            "port": parse_port(self.port),
            "user": self.user.value,
            "password": self.password.value,
            "database": self.database.value,
            "charset": "utf8mb4",
            "autocommit": autocommit,
        }


def parse_project_env_file(path: Path) -> dict[str, str]:
    """Parse the small, documented project .env subset without shell execution."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeConfigError(f"cannot read runtime env file: {path}") from exc

    parsed: dict[str, str] = {}
    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line.strip() or raw_line.startswith("#"):
            continue
        if "=" not in raw_line:
            raise RuntimeConfigError(f"invalid runtime env syntax at line {line_number}")
        key, value = raw_line.split("=", 1)
        if key != key.strip() or value != value.strip():
            raise RuntimeConfigError(f"whitespace is not supported around runtime env assignment at line {line_number}")
        if not ENV_KEY_RE.fullmatch(key) or key == "export":
            raise RuntimeConfigError(f"invalid runtime env key at line {line_number}")
        if key in parsed:
            raise RuntimeConfigError(f"duplicate runtime env key at line {line_number}: {key}")

        if value.startswith(("'", '"')):
            quote = value[0]
            if len(value) < 2 or not value.endswith(quote):
                raise RuntimeConfigError(f"unterminated quoted runtime env value at line {line_number}")
            value = value[1:-1]
            if quote in value:
                raise RuntimeConfigError(f"unsupported quote syntax in runtime env at line {line_number}")
        elif value.endswith(("'", '"')):
            raise RuntimeConfigError(f"invalid quoted runtime env value at line {line_number}")
        if UNSUPPORTED_SHELL_RE.search(value):
            raise RuntimeConfigError(f"unsupported shell syntax in runtime env at line {line_number}")
        parsed[key] = value
    return parsed


def load_project_env(
    project_root: Path | str | None = None,
    *,
    environ: Optional[MutableMapping[str, str]] = None,
) -> LoadedProjectEnv:
    """Load missing environment values from ``config/.env``.

    Values already supplied by systemd, a shell, or tests always win.
    A missing env file is valid: explicit process environment remains supported.
    """
    root = Path(project_root or PROJECT_ROOT).expanduser().resolve()
    path = root / "config" / ".env"
    file_values = parse_project_env_file(path) if path.is_file() else {}
    target = os.environ if environ is None else environ
    applied: list[str] = []
    for key, value in file_values.items():
        if key not in target:
            target[key] = value
            applied.append(key)
    return LoadedProjectEnv(path=path, file_values=file_values, applied_keys=tuple(applied))


def _first(env: Mapping[str, str], names: Sequence[str], default: str = "") -> ResolvedValue:
    for name in names:
        value = str(env.get(name, "") or "").strip()
        if value:
            return ResolvedValue(value=value, source=name)
    return ResolvedValue(value=default, source="default")


def resolve_log_reader_db_config(env: Optional[Mapping[str, str]] = None) -> DatabaseRuntimeConfig:
    values = os.environ if env is None else env
    return DatabaseRuntimeConfig(
        role="log_reader",
        host=_first(values, ("LOG_DB_HOST", "DB_HOST")),
        port=_first(values, ("LOG_DB_PORT", "DB_PORT"), "3306"),
        database=_first(values, ("LOG_DB_NAME", "DB_NAME"), "web_logs"),
        user=_first(values, ("LOG_DB_USER",), "log_reader"),
        password=_first(values, ("LOG_DB_PASSWORD",)),
    )


def resolve_app_db_config(env: Optional[Mapping[str, str]] = None) -> DatabaseRuntimeConfig:
    values = os.environ if env is None else env
    return DatabaseRuntimeConfig(
        role="analysis_app",
        host=_first(values, ("APP_DB_HOST", "DB_HOST", "LOG_DB_HOST")),
        port=_first(values, ("APP_DB_PORT", "DB_PORT", "LOG_DB_PORT"), "3306"),
        database=_first(values, ("APP_DB_NAME", "DB_NAME", "LOG_DB_NAME"), "web_logs"),
        user=_first(values, ("APP_DB_USER",)),
        password=_first(values, ("APP_DB_PASSWORD",)),
    )


def resolve_shipper_db_config(env: Optional[Mapping[str, str]] = None) -> DatabaseRuntimeConfig:
    values = os.environ if env is None else env
    return DatabaseRuntimeConfig(
        role="shipper",
        host=_first(values, ("SHIPPER_DB_HOST", "DB_HOST", "LOG_DB_HOST")),
        port=_first(values, ("SHIPPER_DB_PORT", "DB_PORT", "LOG_DB_PORT"), "3306"),
        database=_first(values, ("SHIPPER_DB_NAME", "DB_NAME", "LOG_DB_NAME"), "web_logs"),
        user=_first(values, ("SHIPPER_DB_USER",), "log_writer"),
        password=_first(values, ("SHIPPER_DB_PASSWORD",)),
    )


def parse_port(value: ResolvedValue) -> int:
    try:
        port = int(value.value)
    except (TypeError, ValueError) as exc:
        raise RuntimeConfigError(f"{value.source} must be an integer") from exc
    if not 1 <= port <= 65535:
        raise RuntimeConfigError(f"{value.source} must be between 1 and 65535")
    return port


def positive_int_env(name: str, default: int, env: Optional[Mapping[str, str]] = None) -> int:
    values = os.environ if env is None else env
    raw = str(values.get(name, default) or "")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeConfigError(f"{name} must be an integer") from exc
    if value < 1:
        raise RuntimeConfigError(f"{name} must be positive")
    return value


def validate_database_config(config: DatabaseRuntimeConfig, *, require_writer: bool = False) -> None:
    missing = [
        field_name
        for field_name, setting in (
            ("host", config.host),
            ("user", config.user),
            ("password", config.password),
            ("database", config.database),
        )
        if not setting.is_set
    ]
    if missing:
        raise RuntimeConfigError(f"{config.role} DB config missing: {', '.join(missing)}")
    parse_port(config.port)
    if require_writer and config.user.value == "log_reader":
        raise RuntimeConfigError("shipper DB user must not be log_reader")


def db_config_diagnostic_lines(configs: Sequence[DatabaseRuntimeConfig]) -> list[str]:
    """Return safe effective-config lines: endpoint provenance, never secrets."""
    lines: list[str] = []
    for config in configs:
        prefix = config.role
        lines.extend(
            [
                f"{prefix}.host={config.host.value or '<missing>'} source={config.host.source}",
                f"{prefix}.port={config.port.value or '<missing>'} source={config.port.source}",
                f"{prefix}.database={config.database.value or '<missing>'} source={config.database.source}",
                f"{prefix}.user={config.user.value or '<missing>'} source={config.user.source}",
                f"{prefix}.password={'<set>' if config.password.is_set else '<missing>'}",
            ]
        )
    return lines


def db_override_warnings(env: Optional[Mapping[str, str]] = None) -> list[str]:
    values = os.environ if env is None else env
    warnings: list[str] = []
    for override, shared in (
        ("LOG_DB_HOST", "DB_HOST"),
        ("LOG_DB_PORT", "DB_PORT"),
        ("LOG_DB_NAME", "DB_NAME"),
        ("APP_DB_HOST", "DB_HOST"),
        ("APP_DB_PORT", "DB_PORT"),
        ("APP_DB_NAME", "DB_NAME"),
        ("SHIPPER_DB_HOST", "DB_HOST"),
        ("SHIPPER_DB_PORT", "DB_PORT"),
        ("SHIPPER_DB_NAME", "DB_NAME"),
    ):
        if values.get(override) and values.get(shared) and values[override] != values[shared]:
            warnings.append(f"{override} overrides {shared}")
    return warnings
