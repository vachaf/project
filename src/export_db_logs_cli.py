#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MariaDB(web_logs)에서 시간 범위 기준으로 로그를 조회해 JSON 파일로 내보내는 CLI/CUI 전용 스크립트.

시간 처리 원칙:
- DB 저장 시각(log_time, created_at)은 UTC로 저장되어 있다고 가정
- 사용자는 KST(Asia/Seoul) 기준으로 시간 범위를 입력
- 조회 시에는 KST 범위를 UTC로 변환해서 DB를 조회
- 출력 JSON의 시간 필드는 KST ISO-8601(+09:00) 문자열로 변환

대상 테이블:
- apache_access_logs
- apache_security_logs
- apache_error_logs

예시:
  python3 export_db_logs_cli_kst.py --help

  python3 export_db_logs_cli_kst.py \
    --host "$LOG_DB_HOST" \
    --user log_writer \
    --password "$LOG_DB_PASSWORD" \
    --today \
    --table security \
    --pretty

  python3 export_db_logs_cli_kst.py \
    --host "$LOG_DB_HOST" \
    --user log_writer \
    --password "$LOG_DB_PASSWORD" \
    --date 2026-04-02 \
    --table security

  python3 export_db_logs_cli_kst.py \
    --host "$LOG_DB_HOST" \
    --user log_writer \
    --password "$LOG_DB_PASSWORD" \
    --start '2026-04-02 09:00:00' \
    --end   '2026-04-02 12:00:00' \
    --table security \
    --pretty
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import pymysql
from pymysql.cursors import DictCursor

DEFAULT_DB_NAME = "web_logs"
DEFAULT_DB_PORT = 3306
DEFAULT_QUERY_TIMEZONE = "Asia/Seoul"
DEFAULT_DB_TIMEZONE = "UTC"
DEFAULT_OUTPUT_DIR = os.path.join("data", "raw")

QUERY_TZ = ZoneInfo(DEFAULT_QUERY_TIMEZONE)
DB_TZ = timezone.utc if DEFAULT_DB_TIMEZONE == "UTC" else ZoneInfo(DEFAULT_DB_TIMEZONE)

TABLE_MAP = {
    "access": "apache_access_logs",
    "security": "apache_security_logs",
    "error": "apache_error_logs",
}

TABLE_ORDER = ["access", "security", "error"]
DEFAULT_TABLE_OPTION = "security"


@dataclass
class DBConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = "utf8mb4"
    connect_timeout: int = 5
    read_timeout: int = 30
    write_timeout: int = 30


@dataclass
class RangeConfig:
    mode: str
    query_tz_name: str
    db_tz_name: str
    start_query_tz: datetime
    end_exclusive_query_tz: datetime
    start_db_tz: datetime
    end_exclusive_db_tz: datetime


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat(timespec="milliseconds")
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class LogExporter:
    def __init__(self, db_config: DBConfig):
        self.db_config = db_config
        self.conn = None

    def connect(self) -> None:
        if self.conn is not None:
            try:
                self.conn.ping(reconnect=True)
                return
            except Exception:
                self.close()

        self.conn = pymysql.connect(
            host=self.db_config.host,
            port=self.db_config.port,
            user=self.db_config.user,
            password=self.db_config.password,
            database=self.db_config.database,
            charset=self.db_config.charset,
            connect_timeout=self.db_config.connect_timeout,
            read_timeout=self.db_config.read_timeout,
            write_timeout=self.db_config.write_timeout,
            autocommit=True,
            cursorclass=DictCursor,
        )

    def close(self) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    def fetch_rows(
        self,
        table_name: str,
        start_dt_db_tz: datetime,
        end_dt_exclusive_db_tz: datetime,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        self.connect()
        sql = f"""
        SELECT *
        FROM {table_name}
        WHERE log_time >= %s
          AND log_time < %s
        ORDER BY log_time ASC, id ASC
        """
        params: List[Any] = [
            to_mysql_datetime(start_dt_db_tz),
            to_mysql_datetime(end_dt_exclusive_db_tz),
        ]
        if limit is not None:
            sql += " LIMIT %s"
            params.append(limit)

        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return rows


# -------------------------
# 시간 처리
# -------------------------
def parse_datetime_text(text: str) -> datetime:
    text = text.strip()
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(
        f"잘못된 날짜/시간 형식입니다: {text} "
        f"(예: 2026-04-02 또는 2026-04-02 09:00:00 또는 2026-04-02T09:00:00+09:00)"
    )


def parse_date_text(text: str) -> datetime:
    try:
        return datetime.strptime(text.strip(), "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"잘못된 날짜 형식입니다: {text} (예: 2026-04-02)") from exc


def attach_tz(dt: datetime, tzinfo) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(tzinfo)
    return dt.replace(tzinfo=tzinfo)


def to_mysql_datetime(dt: datetime) -> str:
    if dt.tzinfo is not None:
        dt = dt.astimezone(DB_TZ).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def convert_naive_db_dt_to_output_text(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, datetime):
        return value
    if value.tzinfo is not None:
        aware_db = value.astimezone(DB_TZ)
    else:
        aware_db = value.replace(tzinfo=DB_TZ)
    aware_out = aware_db.astimezone(QUERY_TZ)
    return aware_out.isoformat(timespec="milliseconds")


def transform_row_datetimes(row: Dict[str, Any]) -> Dict[str, Any]:
    converted = dict(row)
    for key in ("log_time", "created_at"):
        if key in converted:
            converted[key] = convert_naive_db_dt_to_output_text(converted.get(key))
    return converted


def resolve_time_range(args: argparse.Namespace) -> RangeConfig:
    modes_used = sum(
        [
            1 if args.today else 0,
            1 if args.date else 0,
            1 if (args.start or args.end) else 0,
        ]
    )

    if modes_used == 0:
        raise ValueError("시간 조건이 없습니다. --today, --date, 또는 --start/--end 중 하나를 지정하세요.")
    if modes_used > 1:
        raise ValueError("시간 조건은 하나만 선택해야 합니다. --today / --date / --start --end 중 하나만 사용하세요.")

    now_query_tz = datetime.now(QUERY_TZ)

    if args.today:
        start_query_tz = datetime(now_query_tz.year, now_query_tz.month, now_query_tz.day, 0, 0, 0, tzinfo=QUERY_TZ)
        end_query_tz = start_query_tz + timedelta(days=1)
    elif args.date:
        start_query_tz = attach_tz(parse_date_text(args.date), QUERY_TZ)
        end_query_tz = start_query_tz + timedelta(days=1)
    else:
        if bool(args.start) ^ bool(args.end):
            raise ValueError("--start 와 --end 는 함께 지정해야 합니다.")
        start_query_tz = attach_tz(parse_datetime_text(args.start), QUERY_TZ)
        end_query_tz = attach_tz(parse_datetime_text(args.end), QUERY_TZ)
        if start_query_tz >= end_query_tz:
            raise ValueError("시작 시각은 종료 시각보다 앞서야 합니다.")

    start_db_tz = start_query_tz.astimezone(DB_TZ)
    end_db_tz = end_query_tz.astimezone(DB_TZ)

    mode = "today" if args.today else "date" if args.date else "custom"
    return RangeConfig(
        mode=mode,
        query_tz_name=DEFAULT_QUERY_TIMEZONE,
        db_tz_name=DEFAULT_DB_TIMEZONE,
        start_query_tz=start_query_tz,
        end_exclusive_query_tz=end_query_tz,
        start_db_tz=start_db_tz,
        end_exclusive_db_tz=end_db_tz,
    )


# -------------------------
# 출력 경로
# -------------------------
def ensure_parent_dir(file_path: str) -> None:
    parent = os.path.dirname(os.path.abspath(file_path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def auto_output_filename(table_option: str, range_cfg: RangeConfig) -> str:
    if range_cfg.mode in {"today", "date"}:
        date_text = range_cfg.start_query_tz.strftime("%Y-%m-%d")
        filename = f"{table_option}_{date_text}_kst.json"
    else:
        stamp_start = range_cfg.start_query_tz.strftime("%Y-%m-%d_%H-%M-%S")
        stamp_end = range_cfg.end_exclusive_query_tz.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{table_option}_{stamp_start}_to_{stamp_end}_kst.json"
    return os.path.abspath(os.path.join(DEFAULT_OUTPUT_DIR, filename))


# -------------------------
# Interactive CUI
# -------------------------
def ask_input(prompt: str, default: Optional[str] = None, secret: bool = False) -> str:
    shown = f"{prompt} [{default}]: " if default else f"{prompt}: "
    value = getpass.getpass(shown) if secret else input(shown).strip()
    if not value and default is not None:
        return default
    return value


def build_args_from_interactive() -> argparse.Namespace:
    parser = build_parser()

    host = ask_input("DB host", os.getenv("LOG_DB_HOST", "") or None)
    port = ask_input("DB port", str(DEFAULT_DB_PORT))
    user = ask_input("DB user", os.getenv("LOG_DB_USER", "log_writer"))
    password = os.getenv("LOG_DB_PASSWORD", "") or ask_input("DB password", secret=True)
    database = ask_input("DB name", DEFAULT_DB_NAME)

    table = ask_input("table 선택 (access/security/error/all)", DEFAULT_TABLE_OPTION).lower()

    print("시간 조건 선택:")
    print("  1) today (KST)")
    print("  2) date (KST)")
    print("  3) custom start/end (KST)")
    mode = ask_input("번호 입력", "1")

    raw_args = [
        "--host", host,
        "--port", port,
        "--user", user,
        "--password", password,
        "--database", database,
        "--table", table,
    ]

    if mode == "1":
        raw_args.append("--today")
    elif mode == "2":
        date_text = ask_input("날짜 입력 (YYYY-MM-DD, KST)")
        raw_args.extend(["--date", date_text])
    elif mode == "3":
        start = ask_input("시작 시각 (YYYY-MM-DD HH:MM:SS, KST)")
        end = ask_input("종료 시각 (YYYY-MM-DD HH:MM:SS, KST)")
        raw_args.extend(["--start", start, "--end", end])
    else:
        raise ValueError("잘못된 시간 조건 선택입니다.")

    limit = ask_input("limit (비우면 전체)", "")
    if limit:
        raw_args.extend(["--limit", limit])

    pretty = ask_input("pretty 출력 여부 (y/n)", "y").lower()
    if pretty in ("y", "yes"):
        raw_args.append("--pretty")

    return parser.parse_args(raw_args)


# -------------------------
# argparse
# -------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="MariaDB(web_logs)에서 KST 기준 시간 범위로 로그를 JSON으로 export 합니다.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "예시:\n"
            "  python3 export_db_logs_cli_kst.py --host \"$LOG_DB_HOST\" --user log_writer --today --table security\n"
            "  python3 export_db_logs_cli_kst.py --date 2026-04-02 --table security --pretty\n"
            "  python3 export_db_logs_cli_kst.py --start '2026-04-02 09:00:00' --end '2026-04-02 12:00:00' --table security\n"
            "  python3 export_db_logs_cli_kst.py --interactive"
        ),
    )

    parser.add_argument("--host", default=os.getenv("LOG_DB_HOST", ""), help="MariaDB host")
    parser.add_argument("--port", type=int, default=int(os.getenv("LOG_DB_PORT", str(DEFAULT_DB_PORT))), help="MariaDB port")
    parser.add_argument("--user", default=os.getenv("LOG_DB_USER", "log_writer"), help="MariaDB user")
    parser.add_argument("--password", default=os.getenv("LOG_DB_PASSWORD", ""), help="MariaDB password")
    parser.add_argument("--database", default=os.getenv("LOG_DB_NAME", DEFAULT_DB_NAME), help="DB name")

    parser.add_argument("--table", choices=["access", "security", "error", "all"], default=DEFAULT_TABLE_OPTION, help="조회할 테이블 (기본값: security)")

    parser.add_argument("--today", action="store_true", help="오늘 00:00:00부터 내일 00:00:00 전까지 (KST 기준)")
    parser.add_argument("--date", help="특정 날짜 하루치 (YYYY-MM-DD, KST)")
    parser.add_argument("--start", help="조회 시작 시각 (YYYY-MM-DD HH:MM:SS, KST)")
    parser.add_argument("--end", help="조회 종료 시각 (exclusive, KST)")

    parser.add_argument("--limit", type=int, default=None, help="테이블별 최대 조회 건수")
    parser.add_argument("--pretty", action="store_true", help="JSON pretty 출력")
    parser.add_argument("--interactive", action="store_true", help="터미널 프롬프트 기반 interactive 모드")
    parser.add_argument("--test-connection", action="store_true", help="DB 연결만 확인하고 종료")

    return parser


# -------------------------
# 핵심 로직
# -------------------------
def selected_tables(table_option: str) -> List[str]:
    return TABLE_ORDER[:] if table_option == "all" else [table_option]


def build_export_payload(
    db_name: str,
    table_option: str,
    range_cfg: RangeConfig,
    limit: Optional[int],
    fetched: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    counts = {name: len(fetched.get(name, [])) for name in TABLE_ORDER}
    payload = {
        "meta": {
            "database": db_name,
            "exported_at": datetime.now(QUERY_TZ).isoformat(timespec="milliseconds"),
            "query_timezone": range_cfg.query_tz_name,
            "db_timezone": range_cfg.db_tz_name,
            "range_mode": range_cfg.mode,
            "start": range_cfg.start_query_tz.isoformat(timespec="milliseconds"),
            "end_exclusive": range_cfg.end_exclusive_query_tz.isoformat(timespec="milliseconds"),
            "start_db_query": range_cfg.start_db_tz.isoformat(timespec="milliseconds"),
            "end_exclusive_db_query": range_cfg.end_exclusive_db_tz.isoformat(timespec="milliseconds"),
            "table_option": table_option,
            "limit_per_table": limit,
            "total_count": sum(counts.values()),
            "analysis_recommendation": {
                "primary_table_for_llm": "security",
                "use_error_for_correlation": True,
                "use_access_for_ops_baseline": True,
            },
        },
        "counts": counts,
        "data": {
            "access": fetched.get("access", []),
            "security": fetched.get("security", []),
            "error": fetched.get("error", []),
        },
    }
    return payload


def run_export(args: argparse.Namespace) -> str:
    if not args.host:
        raise ValueError("DB host가 없습니다. --host 또는 LOG_DB_HOST를 지정하세요.")
    if not args.password:
        args.password = getpass.getpass("DB password: ")
    if not args.password:
        raise ValueError("DB password가 없습니다. --password 또는 LOG_DB_PASSWORD를 지정하세요.")

    range_cfg = resolve_time_range(args)
    out_path = auto_output_filename(args.table, range_cfg)
    ensure_parent_dir(out_path)

    db_config = DBConfig(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
    )

    exporter = LogExporter(db_config)
    try:
        exporter.connect()

        if args.test_connection:
            print(f"[OK] DB 연결 성공: {args.host}:{args.port} / {args.database}")
            print(f"[INFO] query_timezone={DEFAULT_QUERY_TIMEZONE}, db_timezone={DEFAULT_DB_TIMEZONE}")
            return ""

        if args.table != "security":
            print("[WARN] 문서 기준 routine LLM 분석의 기본 입력은 security 테이블입니다.")
            if args.table == "all":
                print("[WARN] all export 는 원본 보존/운영 점검용에 적합하고, 분석 전처리에서는 security 중심 선택을 권장합니다.")

        fetched: Dict[str, List[Dict[str, Any]]] = {"access": [], "security": [], "error": []}
        for short_name in selected_tables(args.table):
            table_name = TABLE_MAP[short_name]
            rows = exporter.fetch_rows(
                table_name=table_name,
                start_dt_db_tz=range_cfg.start_db_tz,
                end_dt_exclusive_db_tz=range_cfg.end_exclusive_db_tz,
                limit=args.limit,
            )
            fetched[short_name] = [transform_row_datetimes(row) for row in rows]
            print(f"[INFO] {table_name}: {len(rows)} rows")

        payload = build_export_payload(
            db_name=args.database,
            table_option=args.table,
            range_cfg=range_cfg,
            limit=args.limit,
            fetched=fetched,
        )

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(
                payload,
                f,
                ensure_ascii=False,
                indent=2 if args.pretty else None,
                cls=DateTimeEncoder,
            )
            if args.pretty:
                f.write("\n")

        print(f"[OK] JSON export 완료: {out_path}")
        print(f"[OK] total_count={payload['meta']['total_count']}")
        return out_path
    finally:
        exporter.close()


def main() -> int:
    parser = build_parser()

    try:
        if len(sys.argv) == 1:
            parser.print_help()
            print("\n인자 없이 실행했습니다. interactive 모드를 쓰려면: --interactive")
            return 1

        args = parser.parse_args()
        if args.interactive:
            args = build_args_from_interactive()

        run_export(args)
        return 0
    except KeyboardInterrupt:
        print("\n[INFO] 사용자가 중단했습니다.")
        return 130
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
