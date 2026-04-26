#!/usr/bin/env python3
import argparse
import glob
import json
import logging
import os
import re
import signal
import time
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

import pymysql
from pymysql.cursors import DictCursor


CONFIG = {
    "db": {
        "host": os.getenv("LOG_DB_HOST", ""),
        "port": int(os.getenv("LOG_DB_PORT", "3306")),
        "user": os.getenv("LOG_DB_USER", "log_writer"),
        "password": os.getenv("LOG_DB_PASSWORD", ""),
        "database": os.getenv("LOG_DB_NAME", "web_logs"),
        "charset": "utf8mb4",
        "autocommit": False,
    },
    "logs": {
        "access": os.getenv("APACHE_ACCESS_LOG", "/var/log/apache2/app_access.log"),
        "security": os.getenv("APACHE_SECURITY_LOG", "/var/log/apache2/app_security.log"),
        "error": os.getenv("APACHE_ERROR_LOG", "/var/log/apache2/app_error.log"),
    },
    "state_dir": os.getenv("SHIPPER_STATE_DIR", "/var/lib/apache_log_shipper"),
    "spool_dir": os.getenv("SHIPPER_SPOOL_DIR", "/var/spool/apache_log_shipper"),
    "app_log": os.getenv("SHIPPER_APP_LOG", "/var/log/apache2/apache_log_shipper.log"),
    "scan_interval_sec": float(os.getenv("SHIPPER_SCAN_INTERVAL_SEC", "1.0")),
    "flush_interval_sec": float(os.getenv("SHIPPER_FLUSH_INTERVAL_SEC", "2.0")),
    "batch_size": int(os.getenv("SHIPPER_BATCH_SIZE", "100")),
    "spool_retry_interval_sec": float(os.getenv("SHIPPER_SPOOL_RETRY_INTERVAL_SEC", "10.0")),
    "connect_timeout_sec": int(os.getenv("SHIPPER_CONNECT_TIMEOUT_SEC", "5")),
    "read_timeout_sec": int(os.getenv("SHIPPER_READ_TIMEOUT_SEC", "10")),
    "write_timeout_sec": int(os.getenv("SHIPPER_WRITE_TIMEOUT_SEC", "10")),
}

RUNNING = True

# access_db_aligned
ACCESS_RE = re.compile(
    r'(?P<client_ip>\S+)\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)\]\s+'
    r'"(?P<raw_request>[^"]*)"\s+(?P<status>\d{3})\s+(?P<bytes>\S+)\s+'
    r'"(?P<referer>[^"]*)"\s+"(?P<ua>[^"]*)"\s+"(?P<host>[^"]*)"\s+(?P<vhost>\S+)'
)

# security_db_aligned key=value parser
KV_RE = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)')

# app_error.log parser aligned to ErrorLogFormat
ERROR_CUSTOM_RE = re.compile(
    r'^\[(?P<time>[^\]]+)\]\s+'
    r'\[error_link_id:(?P<error_link_id>[^\]]*)\]\s+'
    r'\[request_id:(?P<request_id>[^\]]*)\]\s+'
    r'\[module_name:(?P<module_name>[^\]]*)\]\s+'
    r'\[log_level:(?P<log_level>[^\]]*)\]\s+'
    r'\[src_ip:(?P<src_ip>[^\s\]]+)\s+peer_ip:(?P<peer_ip>[^\]]+)\]\s+'
    r'message=(?P<message>.*)$'
)


def setup_logging(log_path: str) -> None:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()],
    )


def ensure_dirs() -> None:
    os.makedirs(CONFIG["state_dir"], exist_ok=True)
    os.makedirs(CONFIG["spool_dir"], exist_ok=True)


def signal_handler(signum, frame) -> None:
    del frame
    global RUNNING
    logging.info("Received signal %s, shutting down.", signum)
    RUNNING = False


def now_ts() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def strip_quotes(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def normalize_dash(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = strip_quotes(value)
    return None if v == "-" else v


def safe_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    v = strip_quotes(value).strip()
    if v in ("", "-"):
        return None
    try:
        return int(v)
    except ValueError:
        return None


def safe_nullable_tinyint(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    v = (strip_quotes(value) or "").strip().lower()
    if v in ("", "-", "null", "none"):
        return None
    if v in ("1", "true", "yes"):
        return 1
    if v in ("0", "false", "no"):
        return 0
    return None


def parse_apache_time(raw: str) -> Optional[datetime]:
    try:
        return datetime.strptime(raw, "%d/%b/%Y:%H:%M:%S %z")
    except Exception:
        return None


def parse_iso8601_msec(raw: str) -> Optional[datetime]:
    raw = strip_quotes(raw or "") or ""
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(raw, fmt)
        except Exception:
            continue
    return None


def parse_error_time(raw: str) -> Optional[datetime]:
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%a %b %d %H:%M:%S.%f %Y",
        "%a %b %d %H:%M:%S %Y",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except Exception:
            continue
    return None


def to_mysql_datetime(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    # Apache access/security 로그는 %z offset을 가진 aware datetime일 수 있다.
    # DB에는 항상 UTC naive datetime으로 저장한다.
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


class FileState:
    def __init__(self, name: str):
        self.name = name
        self.state_path = os.path.join(CONFIG["state_dir"], f"{name}.json")
        self.inode: Optional[int] = None
        self.offset = 0

    def load(self) -> None:
        if not os.path.exists(self.state_path):
            return
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.inode = data.get("inode")
            self.offset = data.get("offset", 0)
        except Exception as exc:
            logging.warning("Failed to load state for %s: %s", self.name, exc)

    def save(self, inode: int, offset: int) -> None:
        tmp_path = self.state_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump({"inode": inode, "offset": offset}, f)
        os.replace(tmp_path, self.state_path)
        self.inode = inode
        self.offset = offset

    def reset(self) -> None:
        self.inode = None
        self.offset = 0
        try:
            if os.path.exists(self.state_path):
                os.remove(self.state_path)
        except Exception as exc:
            logging.warning("Failed to reset state for %s: %s", self.name, exc)


class MariaDBWriter:
    def __init__(self):
        self.conn = None

    def connect(self) -> None:
        if self.conn:
            try:
                self.conn.ping(reconnect=True)
                return
            except Exception:
                self.close()

        db_cfg = CONFIG["db"]
        if not db_cfg["host"]:
            raise RuntimeError("LOG_DB_HOST is required.")
        if not db_cfg["password"]:
            raise RuntimeError("LOG_DB_PASSWORD is required.")
        self.conn = pymysql.connect(
            host=db_cfg["host"],
            port=db_cfg["port"],
            user=db_cfg["user"],
            password=db_cfg["password"],
            database=db_cfg["database"],
            charset=db_cfg["charset"],
            autocommit=db_cfg["autocommit"],
            connect_timeout=CONFIG["connect_timeout_sec"],
            read_timeout=CONFIG["read_timeout_sec"],
            write_timeout=CONFIG["write_timeout_sec"],
            cursorclass=DictCursor,
        )
        logging.info("Connected to MariaDB %s:%s", db_cfg["host"], db_cfg["port"])

    def close(self) -> None:
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    def insert_access_batch(self, rows: List[Dict]) -> None:
        sql = """
        INSERT INTO apache_access_logs (
            log_time, client_ip, method, raw_request, uri, query_string, protocol,
            status_code, response_body_bytes, referer, user_agent, host, vhost, raw_log
        ) VALUES (
            %(log_time)s, %(client_ip)s, %(method)s, %(raw_request)s, %(uri)s, %(query_string)s, %(protocol)s,
            %(status_code)s, %(response_body_bytes)s, %(referer)s, %(user_agent)s, %(host)s, %(vhost)s, %(raw_log)s
        )
        """
        with self.conn.cursor() as cur:
            cur.executemany(sql, rows)

    def insert_security_batch(self, rows: List[Dict]) -> None:
        sql = """
        INSERT INTO apache_security_logs (
            log_time, request_id, error_link_id, vhost, src_ip, peer_ip, method, raw_request,
            uri, query_string, protocol, status_code, response_body_bytes, in_bytes, out_bytes,
            total_bytes, duration_us, ttfb_us, keepalive_count, connection_status,
            req_content_type, req_content_length, resp_content_type, referer, user_agent,
            host, x_forwarded_for, attack_label, risk_score, matched_rule, is_suspicious,
            resp_html_norm_fingerprint, resp_html_fingerprint_version, resp_html_baseline_name,
            resp_html_baseline_match, resp_html_baseline_confidence, resp_html_features_json, raw_log
        ) VALUES (
            %(log_time)s, %(request_id)s, %(error_link_id)s, %(vhost)s, %(src_ip)s, %(peer_ip)s, %(method)s, %(raw_request)s,
            %(uri)s, %(query_string)s, %(protocol)s, %(status_code)s, %(response_body_bytes)s, %(in_bytes)s, %(out_bytes)s,
            %(total_bytes)s, %(duration_us)s, %(ttfb_us)s, %(keepalive_count)s, %(connection_status)s,
            %(req_content_type)s, %(req_content_length)s, %(resp_content_type)s, %(referer)s, %(user_agent)s,
            %(host)s, %(x_forwarded_for)s, %(attack_label)s, %(risk_score)s, %(matched_rule)s, %(is_suspicious)s,
            %(resp_html_norm_fingerprint)s, %(resp_html_fingerprint_version)s, %(resp_html_baseline_name)s,
            %(resp_html_baseline_match)s, %(resp_html_baseline_confidence)s, %(resp_html_features_json)s, %(raw_log)s
        )
        """
        with self.conn.cursor() as cur:
            cur.executemany(sql, rows)

    def insert_error_batch(self, rows: List[Dict]) -> None:
        sql = """
        INSERT INTO apache_error_logs (
            log_time, error_link_id, request_id, module_name, log_level,
            src_ip, peer_ip, message, raw_log
        ) VALUES (
            %(log_time)s, %(error_link_id)s, %(request_id)s, %(module_name)s, %(log_level)s,
            %(src_ip)s, %(peer_ip)s, %(message)s, %(raw_log)s
        )
        """
        with self.conn.cursor() as cur:
            cur.executemany(sql, rows)

    def flush_batches(self, batches: Dict[str, List[Dict]]) -> None:
        self.connect()
        try:
            if batches["access"]:
                self.insert_access_batch(batches["access"])
            if batches["security"]:
                self.insert_security_batch(batches["security"])
            if batches["error"]:
                self.insert_error_batch(batches["error"])
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise


class SpoolManager:
    def __init__(self):
        self.spool_dir = CONFIG["spool_dir"]

    def write_batch(self, batches: Dict[str, List[Dict]]) -> None:
        data = {"created_at": datetime.now().isoformat(), "batches": batches}
        path = os.path.join(self.spool_dir, f"spool_{now_ts()}_{int(time.time() * 1000)}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        logging.warning("Wrote failed batch to spool: %s", path)

    def replay(self, db_writer: MariaDBWriter) -> None:
        files = sorted(glob.glob(os.path.join(self.spool_dir, "spool_*.json")))
        for path in files:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                batches = data.get("batches", {})
                merged = {
                    "access": batches.get("access", []),
                    "security": batches.get("security", []),
                    "error": batches.get("error", []),
                }
                db_writer.flush_batches(merged)
                os.remove(path)
                logging.info("Replayed spool file: %s", path)
            except Exception as exc:
                logging.warning("Failed to replay spool %s: %s", path, exc)
                break


def parse_kv_line(line: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for match in KV_RE.finditer(line):
        result[match.group(1)] = match.group(2)
    return result


def parse_access_line(line: str) -> Optional[Dict]:
    line = line.rstrip("\n")
    m = ACCESS_RE.match(line)
    if not m:
        logging.warning("Failed to parse access line: %s", line)
        return None

    dt = parse_apache_time(m.group("time"))
    raw_req = normalize_dash(m.group("raw_request"))

    method = None
    uri = None
    protocol = None
    query_string = None

    if raw_req:
        parts = raw_req.split(" ", 2)
        if len(parts) == 3:
            method, full_uri, protocol = parts
            if "?" in full_uri:
                uri, qs = full_uri.split("?", 1)
                query_string = "?" + qs
            else:
                uri = full_uri
                query_string = ""
        elif len(parts) == 2:
            method, uri = parts

    return {
        "log_time": to_mysql_datetime(dt),
        "client_ip": normalize_dash(m.group("client_ip")),
        "method": method,
        "raw_request": raw_req,
        "uri": uri,
        "query_string": query_string,
        "protocol": protocol,
        "status_code": safe_int(m.group("status")),
        "response_body_bytes": safe_int(m.group("bytes")),
        "referer": normalize_dash(m.group("referer")),
        "user_agent": normalize_dash(m.group("ua")),
        "host": normalize_dash(m.group("host")),
        "vhost": normalize_dash(m.group("vhost")),
        "raw_log": line,
    }


def parse_security_line(line: str) -> Optional[Dict]:
    line = line.rstrip("\n")
    kv = parse_kv_line(line)
    if not kv:
        logging.warning("Failed to parse security line: %s", line)
        return None

    dt = parse_iso8601_msec(kv.get("log_time", ""))
    if dt is None:
        logging.warning("Failed to parse security timestamp: %s", kv.get("log_time"))

    return {
        "log_time": to_mysql_datetime(dt),
        "request_id": normalize_dash(kv.get("request_id")),
        "error_link_id": normalize_dash(kv.get("error_link_id")),
        "vhost": normalize_dash(kv.get("vhost")),
        "src_ip": normalize_dash(kv.get("src_ip")),
        "peer_ip": normalize_dash(kv.get("peer_ip")),
        "method": normalize_dash(kv.get("method")),
        "raw_request": normalize_dash(kv.get("raw_request")),
        "uri": normalize_dash(kv.get("uri")),
        "query_string": normalize_dash(kv.get("query_string")),
        "protocol": normalize_dash(kv.get("protocol")),
        "status_code": safe_int(kv.get("status_code")),
        "response_body_bytes": safe_int(kv.get("response_body_bytes")),
        "in_bytes": safe_int(kv.get("in_bytes")),
        "out_bytes": safe_int(kv.get("out_bytes")),
        "total_bytes": safe_int(kv.get("total_bytes")),
        "duration_us": safe_int(kv.get("duration_us")),
        "ttfb_us": safe_int(kv.get("ttfb_us")),
        "keepalive_count": safe_int(kv.get("keepalive_count")),
        "connection_status": normalize_dash(kv.get("connection_status")),
        "req_content_type": normalize_dash(kv.get("req_content_type")),
        "req_content_length": safe_int(kv.get("req_content_length")),
        "resp_content_type": normalize_dash(kv.get("resp_content_type")),
        "referer": normalize_dash(kv.get("referer")),
        "user_agent": normalize_dash(kv.get("user_agent")),
        "host": normalize_dash(kv.get("host")),
        "x_forwarded_for": normalize_dash(kv.get("x_forwarded_for")),
        "attack_label": "unknown",
        "risk_score": 0.00,
        "matched_rule": None,
        "is_suspicious": False,
        "resp_html_norm_fingerprint": normalize_dash(kv.get("resp_html_norm_fingerprint")),
        "resp_html_fingerprint_version": normalize_dash(kv.get("resp_html_fingerprint_version")),
        "resp_html_baseline_name": normalize_dash(kv.get("resp_html_baseline_name")),
        "resp_html_baseline_match": safe_nullable_tinyint(kv.get("resp_html_baseline_match")),
        "resp_html_baseline_confidence": normalize_dash(kv.get("resp_html_baseline_confidence")),
        "resp_html_features_json": normalize_dash(kv.get("resp_html_features_json")),
        "raw_log": line,
    }


def parse_error_line(line: str) -> Optional[Dict]:
    line = line.rstrip("\n")
    m = ERROR_CUSTOM_RE.match(line)
    if not m:
        logging.warning("Failed to parse error line: %s", line)
        return None

    dt = parse_error_time(m.group("time").strip())
    if dt is None:
        logging.warning("Failed to parse error timestamp: %s", m.group("time"))
        return None

    return {
        "log_time": to_mysql_datetime(dt),
        "error_link_id": normalize_dash(m.group("error_link_id")),
        "request_id": normalize_dash(m.group("request_id")),
        "module_name": normalize_dash(m.group("module_name")),
        "log_level": normalize_dash(m.group("log_level")),
        "src_ip": normalize_dash(m.group("src_ip")),
        "peer_ip": normalize_dash(m.group("peer_ip")),
        "message": normalize_dash(m.group("message")),
        "raw_log": line,
    }


class LogTailer:
    def __init__(self, name: str, path: str, parser_func: Callable[[str], Optional[Dict]]):
        self.name = name
        self.path = path
        self.parser_func = parser_func
        self.state = FileState(name)
        self.state.load()

    def read_new_lines(self) -> List[Dict]:
        rows: List[Dict] = []
        if not os.path.exists(self.path):
            return rows

        st = os.stat(self.path)
        inode = st.st_ino
        size = st.st_size

        if self.state.inode == inode:
            offset = self.state.offset
            if offset > size:
                offset = 0
        else:
            offset = 0

        with open(self.path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(offset)
            for line in f:
                parsed = self.parser_func(line)
                if parsed:
                    rows.append(parsed)
            new_offset = f.tell()

        self.state.save(inode, new_offset)
        return rows


def build_tailers(reset_state: bool) -> Dict[str, LogTailer]:
    tailers = {
        "access": LogTailer("access", CONFIG["logs"]["access"], parse_access_line),
        "security": LogTailer("security", CONFIG["logs"]["security"], parse_security_line),
        "error": LogTailer("error", CONFIG["logs"]["error"], parse_error_line),
    }
    if reset_state:
        for tailer in tailers.values():
            tailer.state.reset()
    return tailers


def test_db_connection() -> None:
    writer = MariaDBWriter()
    try:
        writer.connect()
        print("DB connection: OK")
    finally:
        writer.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Apache access/security/error log shipper for web_logs schema")
    parser.add_argument("--once", action="store_true", help="read current delta once, flush, and exit")
    parser.add_argument("--reset-state", action="store_true", help="reset saved offsets and read from beginning")
    parser.add_argument("--test-db", action="store_true", help="test database connection and exit")
    args = parser.parse_args()

    ensure_dirs()
    setup_logging(CONFIG["app_log"])

    if args.test_db:
        test_db_connection()
        return

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    tailers = build_tailers(reset_state=args.reset_state)
    db_writer = MariaDBWriter()
    spool = SpoolManager()
    buffers: Dict[str, List[Dict]] = {"access": [], "security": [], "error": []}

    last_flush = time.time()
    last_spool_retry = 0.0

    logging.info("Apache log shipper started.")
    logging.info(
        "Using logs: access=%s security=%s error=%s",
        CONFIG["logs"]["access"],
        CONFIG["logs"]["security"],
        CONFIG["logs"]["error"],
    )

    while RUNNING:
        try:
            for log_type, tailer in tailers.items():
                rows = tailer.read_new_lines()
                if rows:
                    buffers[log_type].extend(rows)

            now = time.time()
            need_flush = (
                sum(len(v) for v in buffers.values()) >= CONFIG["batch_size"]
                or (now - last_flush) >= CONFIG["flush_interval_sec"]
                or args.once
            )

            if need_flush and any(buffers.values()):
                try:
                    db_writer.flush_batches(buffers)
                    logging.info(
                        "Flushed: access=%d security=%d error=%d",
                        len(buffers["access"]),
                        len(buffers["security"]),
                        len(buffers["error"]),
                    )
                    buffers = {"access": [], "security": [], "error": []}
                    last_flush = now
                except Exception as exc:
                    logging.exception("DB flush failed: %s", exc)
                    spool.write_batch(buffers)
                    buffers = {"access": [], "security": [], "error": []}
                    db_writer.close()
                    last_flush = now

            if (now - last_spool_retry) >= CONFIG["spool_retry_interval_sec"]:
                try:
                    spool.replay(db_writer)
                except Exception as exc:
                    logging.warning("Spool replay failed: %s", exc)
                    db_writer.close()
                last_spool_retry = now

            if args.once:
                break

            time.sleep(CONFIG["scan_interval_sec"])

        except Exception as exc:
            logging.exception("Unexpected error in main loop: %s", exc)
            if args.once:
                break
            time.sleep(2)

    if any(buffers.values()):
        try:
            db_writer.flush_batches(buffers)
            logging.info("Final flush completed.")
        except Exception as exc:
            logging.exception("Final flush failed: %s", exc)
            spool.write_batch(buffers)

    db_writer.close()
    logging.info("Apache log shipper stopped.")


if __name__ == "__main__":
    main()
