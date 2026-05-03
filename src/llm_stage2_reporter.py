#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prepare_llm_input.py / llm_stage1_classifier.py 산출물을 바탕으로
최종 Markdown 분석 보고서를 생성하는 2차 LLM 리포터.

주요 개선 사항
- request_id 단독 매칭을 제거하고 incident_ref 기반으로 안전하게 재매칭
- access/security 중복 row 를 incident 단위로 묶어 distinct incident 중심으로 요약
- known asset IP(웹서버/DB/LLM 서버 등) 목록을 받아 내부 테스트/자체 호출 가능성을 보고서에 반영
- filtered_out_breakdown 을 stage2 입력과 Markdown 에 보존해 후보 밖 저신호 요청 분포를 가시화
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib import error

from llm_client import SUPPORTED_PROVIDERS, call_llm_json, provider_api_key_error, resolve_llm_config

DEFAULT_TIMEOUT_SEC = 180
DEFAULT_MODE = "routine"
DEFAULT_ROUTINE_MODEL = "gpt-5.4-mini"
DEFAULT_MILESTONE_MODEL = "gpt-5.4"
DEFAULT_PRESENTATION_MODEL = "gpt-5.4"
ALLOWED_MODES = {"routine", "milestone", "presentation"}
SEVERITY_ORDER = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
CONFIDENCE_ORDER = {"high": 3, "medium": 2, "low": 1}
TABLE_PRIORITY = {"security": 3, "error": 2, "access": 1}
RECON_FILTERED_CATEGORIES = ("low_signal_fuzzing", "low_signal_dir_probe")
REFERENCE_BASELINE_FILTERED_CATEGORIES = ("benign_normal_search", "normal_search_baseline")
ENV_FILE_NAMES = ("config/llm.env", "llm.env", ".env")
IP_BEHAVIOR_CONTEXT_LIMIT = 10
IP_BEHAVIOR_LIST_LIMIT = 10
STATIC_BASELINE_CONTEXT_LIMIT = 10
CRAWLER_BASELINE_CONTEXT_LIMIT = 10
SENSITIVE_PATH_PROBE_CONTEXT_LIMIT = 10
MIXED_BASELINE_SCANNER_CONTEXT_LIMIT = 10
AUTH_BEHAVIOR_CONTEXT_LIMIT = 10
METHOD_BEHAVIOR_CONTEXT_LIMIT = 10
PROTOCOL_ANOMALY_CONTEXT_LIMIT = 10


@dataclass
class IncidentBrief:
    rank: int
    incident_ref: str
    dedup_key: str
    duplicate_count: int
    request_id: str
    src_ip: str
    verdict: str
    severity: str
    confidence: str
    source_table: str
    source_tables: List[str]
    method: str
    uri: str
    status_code: int
    score: int
    log_time: str
    response_body_bytes: int
    resp_content_type: str
    raw_request_target: str
    path_normalized_from_raw_request: bool
    likely_html_fallback_response: bool
    hpp_detected: bool
    hpp_param_names: List[str]
    embedded_attack_hint: str
    reasoning_summary: str
    evidence_fields: List[str]
    reason_hints: List[str]
    user_agent: str
    raw_request: str
    raw_log_excerpt: str
    recommended_actions: List[str]
    known_asset: bool


@dataclass
class LLMJsonParseResult:
    parsed: Dict[str, Any]
    json_text: str
    strategy: str


class LLMJsonParseError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        output_text: str,
        normalized_text: str,
        candidate_text: str,
        original_error: Exception,
    ) -> None:
        super().__init__(message)
        self.output_text = output_text
        self.normalized_text = normalized_text
        self.candidate_text = candidate_text
        self.original_error = original_error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM 2차 보고서 생성기 (OpenAI/Anthropic)")
    parser.add_argument("--stage1-results", required=True, help="llm_stage1_classifier.py 결과 <base>_stage1_results.json")
    parser.add_argument("--llm-input", default=None, help="prepare_llm_input.py 결과 <base>_llm_input.json")
    parser.add_argument("--stage1-errors", default=None, help="선택: <base>_stage1_errors.json")
    parser.add_argument("--out-dir", default=".", help="산출물 저장 디렉터리")
    parser.add_argument("--base-name", default=None, help="산출물 파일명 접두어")
    parser.add_argument("--mode", default=DEFAULT_MODE, choices=sorted(ALLOWED_MODES), help="모델 사용 모드")
    parser.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default=None, help="LLM provider (기본값: LLM_PROVIDER 또는 openai)")
    parser.add_argument("--model", default=None, help="명시적 모델 override")
    parser.add_argument("--top-incidents", type=int, default=12, help="모델에 전달할 상위 incident 수")
    parser.add_argument("--top-noise-groups", type=int, default=8, help="모델에 전달할 상위 noise group 수")
    parser.add_argument("--top-ips", type=int, default=8, help="모델에 전달할 상위 src_ip 수")
    parser.add_argument(
        "--known-asset-ips",
        default=None,
        help="쉼표 구분 known asset IP 목록 (.env 의 KNOWN_ASSET_IPS fallback 사용 가능)",
    )
    parser.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC, help="HTTP 타임아웃")
    parser.add_argument("--store", action="store_true", help="OpenAI Responses API 결과 저장 활성화 (Anthropic에서는 무시)")
    parser.add_argument("--reasoning-effort", choices=["none", "low", "medium", "high", "xhigh"], default="none", help="선택적 reasoning effort")
    parser.add_argument("--pretty", action="store_true", help="JSON pretty 출력")
    parser.add_argument("--dry-run", action="store_true", help="실제 API 호출 없이 요청 payload 와 markdown 초안만 생성")
    return parser.parse_args()


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: str, payload: Any, pretty: bool) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2 if pretty else None)


def write_text(path: str, text: str) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)


def strip_fenced_code_block(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if not lines:
        return stripped
    if lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def extract_outer_json_object(text: str) -> Optional[str]:
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:idx + 1].strip()

    return None


def safe_parse_llm_json(output_text: str) -> LLMJsonParseResult:
    normalized_text = strip_fenced_code_block(output_text)
    candidates: List[Tuple[str, str]] = [("direct", normalized_text)]
    extracted_text = extract_outer_json_object(normalized_text)
    if extracted_text and extracted_text != normalized_text:
        candidates.append(("outer_object", extracted_text))

    last_error: Exception = ValueError("no JSON object found")
    last_candidate = normalized_text
    for strategy, candidate in candidates:
        last_candidate = candidate
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as e:
            last_error = e
            continue
        if not isinstance(parsed, dict):
            last_error = ValueError("LLM output JSON root is not an object")
            continue
        return LLMJsonParseResult(parsed=parsed, json_text=candidate, strategy=strategy)

    raise LLMJsonParseError(
        str(last_error),
        output_text=output_text,
        normalized_text=normalized_text,
        candidate_text=last_candidate,
        original_error=last_error,
    )


def build_repair_messages(invalid_output_text: str) -> List[Dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You repair invalid LLM JSON output. Return only one pure JSON object. "
                "Do not include Markdown, prose, or explanations."
            ),
        },
        {
            "role": "user",
            "content": (
                "아래 텍스트를 동일 스키마를 만족하는 순수 JSON 객체 하나로만 다시 반환하라.\n\n"
                + invalid_output_text
            ),
        },
    ]


def log_llm_response_summary(label: str, provider: str, response_id: Optional[str], stop_reason: Optional[str]) -> None:
    print(
        f"[INFO] {label}: provider={provider} response_id={response_id or '-'} stop_reason={stop_reason or '-'}"
    )
    if provider == "anthropic" and stop_reason == "max_tokens":
        print("[WARN] Anthropic stop_reason=max_tokens: 응답 truncation 가능성이 있습니다.", file=sys.stderr)


def dump_stage2_parse_error(
    *,
    report_error_path: Path,
    raw_dump_path: Path,
    provider: str,
    model: str,
    response_id: Optional[str],
    stop_reason: Optional[str],
    output_text: str,
    raw_response: Dict[str, Any],
    parse_error: Exception,
    pretty: bool,
    repair_attempted: bool,
    repair_response: Optional[Dict[str, Any]] = None,
) -> None:
    payload = {
        "error_type": "json_decode_error",
        "provider": provider,
        "model": model,
        "response_id": response_id,
        "stop_reason": stop_reason,
        "parse_error": str(parse_error),
        "repair_attempted": repair_attempted,
        "raw_dump_path": str(raw_dump_path),
    }
    if provider == "anthropic" and stop_reason == "max_tokens":
        payload["diagnostic_hint"] = "Anthropic stop_reason=max_tokens 이므로 JSON 응답이 잘렸을 가능성이 있습니다. ANTHROPIC_MAX_TOKENS 증가를 검토하세요."

    raw_payload = {
        "provider": provider,
        "model": model,
        "response_id": response_id,
        "stop_reason": stop_reason,
        "output_text": output_text,
        "raw_response": raw_response,
        "parse_error": str(parse_error),
        "repair_attempted": repair_attempted,
        "repair_response": repair_response,
    }
    dump_json(str(raw_dump_path), raw_payload, pretty=pretty)
    dump_json(str(report_error_path), payload, pretty=pretty)


def normalize_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def iso_now() -> str:
    return datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="milliseconds")


def choose_model(provider: str, mode: str, override: Optional[str], dry_run: bool = False) -> str:
    if override:
        return override
    if provider == "anthropic":
        model = os.getenv("ANTHROPIC_MODEL", "").strip()
        if model:
            return model
        if dry_run:
            return "anthropic-model-required"
        raise ValueError("Anthropic provider는 --model 또는 ANTHROPIC_MODEL 설정이 필요합니다.")
    if mode == "routine":
        return DEFAULT_ROUTINE_MODEL
    if mode == "milestone":
        return DEFAULT_MILESTONE_MODEL
    if mode == "presentation":
        return DEFAULT_PRESENTATION_MODEL
    raise ValueError(f"unsupported mode: {mode}")


def derive_base_name(stage1_results_path: str, explicit_base_name: Optional[str]) -> str:
    if explicit_base_name:
        return explicit_base_name
    return Path(stage1_results_path).stem.replace("_stage1_results", "")


def infer_related_path(stage1_results_path: str, replacement_suffix: str) -> str:
    p = Path(stage1_results_path)
    return str(p.with_name(p.stem.replace("_stage1_results", replacement_suffix) + p.suffix))


def parse_known_asset_ips(raw: str) -> List[str]:
    return sorted({part.strip() for part in raw.split(",") if part.strip()})


def iter_env_file_candidates(extra_roots: Optional[Sequence[Path]] = None) -> List[Path]:
    roots = [Path.cwd(), Path(__file__).resolve().parent.parent]
    if extra_roots:
        roots.extend(extra_roots)
    candidates: List[Path] = []
    seen = set()
    for root in roots:
        for name in ENV_FILE_NAMES:
            path = (root / name).resolve()
            if path not in seen:
                candidates.append(path)
                seen.add(path)
    return candidates


def read_env_file_value(key: str, extra_roots: Optional[Sequence[Path]] = None) -> str:
    for path in iter_env_file_candidates(extra_roots=extra_roots):
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            name = name.strip()
            if name.startswith("export "):
                name = name[len("export "):].strip()
            if name != key:
                continue
            value = value.strip().strip("'\"")
            return value
    return ""


def resolve_known_asset_ips(cli_value: Optional[str], extra_env_roots: Optional[Sequence[Path]] = None) -> List[str]:
    if cli_value is not None:
        return parse_known_asset_ips(cli_value)
    raw = os.getenv("KNOWN_ASSET_IPS", "").strip() or read_env_file_value(
        "KNOWN_ASSET_IPS",
        extra_roots=extra_env_roots,
    )
    return parse_known_asset_ips(raw)


def parse_dt(text: str) -> Optional[datetime]:
    s = normalize_str(text)
    if not s:
        return None
    candidates = [s]
    if len(s) >= 6 and (s[-6] in {"+", "-"}) and s[-3] == ":":
        candidates.append(s[:-6] + s[-6:].replace(":", ""))
    for item in candidates:
        try:
            return datetime.fromisoformat(item)
        except ValueError:
            pass
    return None


def time_bucket_seconds(text: str) -> str:
    dt = parse_dt(text)
    if dt is None:
        return normalize_str(text)
    return dt.replace(microsecond=0).isoformat()


def sort_results(results: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        list(results),
        key=lambda x: (
            SEVERITY_ORDER.get(normalize_str(x.get("severity")), 0),
            CONFIDENCE_ORDER.get(normalize_str(x.get("confidence")), 0),
            safe_int(x.get("score"), 0),
            TABLE_PRIORITY.get(normalize_str(x.get("source_table")), 0),
            normalize_str(x.get("log_time")),
        ),
        reverse=True,
    )


def shorten_evidence_text(value: Any, max_len: int = 280) -> str:
    text = normalize_str(value)
    if not text:
        return ""
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def build_dedup_key(item: Dict[str, Any]) -> str:
    request_id = normalize_str(item.get("request_id"))
    if request_id and request_id != "-":
        return f"request_id:{request_id}"
    src_ip = normalize_str(item.get("src_ip")) or "-"
    method = normalize_str(item.get("method")) or "-"
    uri = normalize_str(item.get("uri")) or "-"
    status_code = safe_int(item.get("status_code"), 0)
    bucket = time_bucket_seconds(normalize_str(item.get("log_time"))) or "-"
    return f"fallback:{src_ip}|{method}|{uri}|{status_code}|{bucket}"


def build_incident_ref(item: Dict[str, Any], dedup_key: str) -> str:
    source_table = normalize_str(item.get("source_table")) or "-"
    log_id = normalize_str(item.get("log_id")) or "-"
    candidate_index = normalize_str(item.get("candidate_index")) or "-"
    return f"{dedup_key}|table:{source_table}|log_id:{log_id}|candidate:{candidate_index}"


def choose_best_representative(items: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return sorted(
        items,
        key=lambda x: (
            TABLE_PRIORITY.get(normalize_str(x.get("source_table")), 0),
            SEVERITY_ORDER.get(normalize_str(x.get("severity")), 0),
            CONFIDENCE_ORDER.get(normalize_str(x.get("confidence")), 0),
            safe_int(x.get("score"), 0),
            normalize_str(x.get("log_time")),
        ),
        reverse=True,
    )[0]


def dedup_stage1_results(results: List[Dict[str, Any]], known_asset_ips: Sequence[str]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in results:
        grouped[build_dedup_key(item)].append(item)

    deduped: List[Dict[str, Any]] = []
    known_asset_set = set(known_asset_ips)
    for dedup_key, items in grouped.items():
        representative = dict(choose_best_representative(items))
        source_tables = sorted({normalize_str(x.get("source_table")) or "-" for x in items})
        merged_actions: List[str] = []
        for entry in items:
            for action in entry.get("recommended_actions") or []:
                action_text = normalize_str(action)
                if action_text and action_text not in merged_actions:
                    merged_actions.append(action_text)
        representative["duplicate_count"] = len(items)
        representative["source_tables"] = source_tables
        representative["merged_request_ids"] = sorted({normalize_str(x.get("request_id")) or "-" for x in items})
        representative["dedup_key"] = dedup_key
        representative["incident_ref"] = build_incident_ref(representative, dedup_key)
        representative["recommended_actions"] = merged_actions or [normalize_str(x) for x in (representative.get("recommended_actions") or []) if normalize_str(x)]
        representative["known_asset"] = (normalize_str(representative.get("src_ip")) or "-") in known_asset_set
        deduped.append(representative)

    return sort_results(deduped)


def build_candidate_evidence_lookup(llm_input_payload: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    candidates = (llm_input_payload or {}).get("analysis_candidates") or []
    by_incident_group_key: Dict[str, Dict[str, Any]] = {}
    by_request_id: Dict[str, Dict[str, Any]] = {}
    by_source_log: Dict[str, Dict[str, Any]] = {}

    for candidate in candidates:
        incident_group_key = normalize_str(candidate.get("incident_group_key"))
        request_id = normalize_str(candidate.get("request_id"))
        source_table = normalize_str(candidate.get("source_table"))
        log_id = normalize_str(candidate.get("log_id"))
        if incident_group_key and incident_group_key not in by_incident_group_key:
            by_incident_group_key[incident_group_key] = candidate
        if request_id and request_id not in by_request_id:
            by_request_id[request_id] = candidate
        if source_table and log_id and log_id != "-":
            by_source_log.setdefault(f"{source_table}:{log_id}", candidate)

    return {
        "by_incident_group_key": by_incident_group_key,
        "by_request_id": by_request_id,
        "by_source_log": by_source_log,
    }


def resolve_incident_evidence(
    item: Dict[str, Any],
    candidate_lookup: Optional[Dict[str, Dict[str, Dict[str, Any]]]],
) -> Dict[str, Any]:
    if not candidate_lookup:
        return {}

    incident_group_key = normalize_str(item.get("incident_group_key"))
    if incident_group_key:
        candidate = candidate_lookup.get("by_incident_group_key", {}).get(incident_group_key)
        if candidate:
            return candidate

    request_id = normalize_str(item.get("request_id"))
    if request_id:
        candidate = candidate_lookup.get("by_request_id", {}).get(request_id)
        if candidate:
            return candidate

    source_table = normalize_str(item.get("source_table"))
    log_id = normalize_str(item.get("log_id"))
    if source_table and log_id and log_id != "-":
        candidate = candidate_lookup.get("by_source_log", {}).get(f"{source_table}:{log_id}")
        if candidate:
            return candidate

    return {}


def build_incident_briefs(
    results: List[Dict[str, Any]],
    top_n: int,
    known_asset_ips: Sequence[str],
    candidate_lookup: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
) -> List[IncidentBrief]:
    deduped = dedup_stage1_results(results, known_asset_ips=known_asset_ips)
    briefs: List[IncidentBrief] = []
    for idx, item in enumerate(deduped[:top_n], start=1):
        evidence_source = resolve_incident_evidence(item, candidate_lookup)
        briefs.append(
            IncidentBrief(
                rank=idx,
                incident_ref=normalize_str(item.get("incident_ref")),
                dedup_key=normalize_str(item.get("dedup_key")),
                duplicate_count=safe_int(item.get("duplicate_count"), 1),
                request_id=normalize_str(item.get("request_id")) or "-",
                src_ip=normalize_str(item.get("src_ip")) or "-",
                verdict=normalize_str(item.get("verdict")) or "inconclusive",
                severity=normalize_str(item.get("severity")) or "low",
                confidence=normalize_str(item.get("confidence")) or "low",
                source_table=normalize_str(item.get("source_table")) or "-",
                source_tables=[normalize_str(x) for x in (item.get("source_tables") or []) if normalize_str(x)],
                method=normalize_str(item.get("method")) or "-",
                uri=normalize_str(item.get("uri")) or "-",
                status_code=safe_int(item.get("status_code"), 0),
                score=safe_int(item.get("score"), 0),
                log_time=normalize_str(item.get("log_time")),
                response_body_bytes=safe_int(item.get("response_body_bytes"), 0),
                resp_content_type=normalize_str(item.get("resp_content_type")),
                raw_request_target=normalize_str(item.get("raw_request_target")),
                path_normalized_from_raw_request=bool(item.get("path_normalized_from_raw_request")),
                likely_html_fallback_response=bool(item.get("likely_html_fallback_response")),
                hpp_detected=bool(item.get("hpp_detected")),
                hpp_param_names=[normalize_str(x) for x in (item.get("hpp_param_names") or []) if normalize_str(x)],
                embedded_attack_hint=normalize_str(item.get("embedded_attack_hint")),
                reasoning_summary=normalize_str(item.get("reasoning_summary")),
                evidence_fields=[normalize_str(x) for x in (item.get("evidence_fields") or []) if normalize_str(x)],
                reason_hints=[normalize_str(x) for x in (evidence_source.get("reason_hints") or item.get("reason_hints") or []) if normalize_str(x)],
                user_agent=shorten_evidence_text(evidence_source.get("user_agent"), max_len=160),
                raw_request=shorten_evidence_text(evidence_source.get("raw_request"), max_len=180),
                raw_log_excerpt=shorten_evidence_text(evidence_source.get("raw_log"), max_len=280),
                recommended_actions=[normalize_str(x) for x in (item.get("recommended_actions") or []) if normalize_str(x)],
                known_asset=bool(item.get("known_asset")),
            )
        )
    return briefs


def summarize_ips(results: List[Dict[str, Any]], top_n: int, known_asset_ips: Sequence[str]) -> List[Dict[str, Any]]:
    deduped = dedup_stage1_results(results, known_asset_ips=known_asset_ips)
    known_asset_set = set(known_asset_ips)
    ip_buckets: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "count": 0,
            "raw_row_count": 0,
            "max_severity": "info",
            "max_confidence": "low",
            "verdicts": Counter(),
            "uris": Counter(),
            "actions": Counter(),
            "known_asset": False,
        }
    )

    raw_counts = Counter(normalize_str(x.get("src_ip")) or "-" for x in results)
    for item in deduped:
        ip = normalize_str(item.get("src_ip")) or "-"
        bucket = ip_buckets[ip]
        bucket["count"] += 1
        bucket["raw_row_count"] = raw_counts.get(ip, bucket["raw_row_count"])
        sev = normalize_str(item.get("severity")) or "info"
        conf = normalize_str(item.get("confidence")) or "low"
        verdict = normalize_str(item.get("verdict")) or "inconclusive"
        uri = normalize_str(item.get("uri")) or "-"
        bucket["verdicts"][verdict] += 1
        bucket["uris"][uri] += 1
        for action in item.get("recommended_actions") or []:
            action_text = normalize_str(action)
            if action_text:
                bucket["actions"][action_text] += 1
        if SEVERITY_ORDER.get(sev, 0) > SEVERITY_ORDER.get(bucket["max_severity"], 0):
            bucket["max_severity"] = sev
        if CONFIDENCE_ORDER.get(conf, 0) > CONFIDENCE_ORDER.get(bucket["max_confidence"], 0):
            bucket["max_confidence"] = conf
        bucket["known_asset"] = ip in known_asset_set

    rows: List[Dict[str, Any]] = []
    for ip, bucket in ip_buckets.items():
        rows.append(
            {
                "src_ip": ip,
                "incident_count": bucket["count"],
                "raw_row_count": bucket["raw_row_count"],
                "max_severity": bucket["max_severity"],
                "max_confidence": bucket["max_confidence"],
                "top_verdicts": [name for name, _ in bucket["verdicts"].most_common(3)],
                "top_uris": [name for name, _ in bucket["uris"].most_common(3)],
                "top_actions": [name for name, _ in bucket["actions"].most_common(3)],
                "known_asset": bucket["known_asset"],
            }
        )

    rows.sort(
        key=lambda x: (
            SEVERITY_ORDER.get(normalize_str(x.get("max_severity")), 0),
            CONFIDENCE_ORDER.get(normalize_str(x.get("max_confidence")), 0),
            safe_int(x.get("incident_count"), 0),
        ),
        reverse=True,
    )
    return rows[:top_n]


def normalize_counter_dict(raw: Any) -> Dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    normalized: Dict[str, int] = {}
    for key, value in raw.items():
        key_text = normalize_str(key)
        if not key_text:
            continue
        normalized[key_text] = safe_int(value, 0)
    return dict(sorted(normalized.items(), key=lambda kv: (-kv[1], kv[0])))


def build_filtered_category_rows(filtered_out_breakdown: Dict[str, int], total_filtered_out_rows: int, top_n: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if total_filtered_out_rows <= 0:
        total_filtered_out_rows = sum(filtered_out_breakdown.values())
    for category, count in sorted(filtered_out_breakdown.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]:
        share = round((count / total_filtered_out_rows) * 100, 1) if total_filtered_out_rows > 0 else 0.0
        rows.append(
            {
                "category": category,
                "count": count,
                "share_pct": share,
            }
        )
    return rows


def build_out_of_candidate_recon_rows(filtered_out_breakdown: Dict[str, int], total_filtered_out_rows: int, top_n: int) -> List[Dict[str, Any]]:
    recon_breakdown = {
        category: count
        for category, count in filtered_out_breakdown.items()
        if category in RECON_FILTERED_CATEGORIES and safe_int(count, 0) > 0
    }
    return build_filtered_category_rows(
        filtered_out_breakdown=recon_breakdown,
        total_filtered_out_rows=total_filtered_out_rows,
        top_n=top_n,
    )


def truncate_unique_strings(values: Any, max_items: int = IP_BEHAVIOR_LIST_LIMIT) -> List[str]:
    if not isinstance(values, list):
        return []
    items: List[str] = []
    for value in values:
        text = normalize_str(value)
        if not text or text in items:
            continue
        items.append(text)
        if len(items) >= max_items:
            break
    return items


def build_static_baseline_context_rows(
    summaries: List[Dict[str, Any]],
    known_asset_ips: Sequence[str],
    top_n: int = STATIC_BASELINE_CONTEXT_LIMIT,
) -> List[Dict[str, Any]]:
    known_asset_set = set(known_asset_ips)
    rows: List[Dict[str, Any]] = []
    for item in summaries:
        src_ip = normalize_str(item.get("src_ip")) or "-"
        rows.append(
            {
                "context_role": normalize_str(item.get("context_role")) or "static_baseline_context",
                "aggregate_scope": normalize_str(item.get("aggregate_scope")) or "same_src_ip_static_baseline_time_window",
                "should_promote_to_candidate": bool(item.get("should_promote_to_candidate")),
                "src_ip": src_ip,
                "window_start": normalize_str(item.get("window_start")),
                "window_end": normalize_str(item.get("window_end")),
                "burst_window_sec": safe_int(item.get("burst_window_sec"), 0),
                "request_count": safe_int(item.get("request_count"), 0),
                "status_counts": normalize_counter_dict(item.get("status_counts")),
                "asset_categories_observed": truncate_unique_strings(item.get("asset_categories_observed")),
                "path_counts": normalize_counter_dict(item.get("path_counts")),
                "sample_request_ids": truncate_unique_strings(item.get("sample_request_ids")),
                "reason_hints": truncate_unique_strings(item.get("reason_hints")),
                "interpretation_limit": normalize_str(item.get("interpretation_limit"))
                or "static_content_not_visible_no_attack_inference",
                "known_asset": src_ip in known_asset_set,
            }
        )

    rows.sort(
        key=lambda x: (
            safe_int(x.get("request_count"), 0),
            len(x.get("asset_categories_observed") or []),
            normalize_str(x.get("window_start")),
        ),
        reverse=True,
    )
    return rows[:top_n]


def build_crawler_baseline_context_rows(
    summaries: List[Dict[str, Any]],
    known_asset_ips: Sequence[str],
    top_n: int = CRAWLER_BASELINE_CONTEXT_LIMIT,
) -> List[Dict[str, Any]]:
    known_asset_set = set(known_asset_ips)
    rows: List[Dict[str, Any]] = []
    for item in summaries:
        src_ip = normalize_str(item.get("src_ip")) or "-"
        rows.append(
            {
                "context_role": normalize_str(item.get("context_role")) or "crawler_baseline_context",
                "aggregate_scope": normalize_str(item.get("aggregate_scope")) or "same_src_ip_crawler_like_time_window",
                "should_promote_to_candidate": bool(item.get("should_promote_to_candidate")),
                "src_ip": src_ip,
                "window_start": normalize_str(item.get("window_start")),
                "window_end": normalize_str(item.get("window_end")),
                "burst_window_sec": safe_int(item.get("burst_window_sec"), 0),
                "request_count": safe_int(item.get("request_count"), 0),
                "status_counts": normalize_counter_dict(item.get("status_counts")),
                "crawler_like_user_agent_families": truncate_unique_strings(item.get("crawler_like_user_agent_families")),
                "path_categories_observed": truncate_unique_strings(item.get("path_categories_observed")),
                "path_counts": normalize_counter_dict(item.get("path_counts")),
                "sample_request_ids": truncate_unique_strings(item.get("sample_request_ids")),
                "reason_hints": truncate_unique_strings(item.get("reason_hints")),
                "interpretation_limit": normalize_str(item.get("interpretation_limit"))
                or "crawler_ua_spoofable_no_content_or_page_existence_inference",
                "known_asset": src_ip in known_asset_set,
            }
        )

    rows.sort(
        key=lambda x: (
            safe_int(x.get("request_count"), 0),
            len(x.get("crawler_like_user_agent_families") or []),
            len(x.get("path_categories_observed") or []),
            normalize_str(x.get("window_start")),
        ),
        reverse=True,
    )
    return rows[:top_n]


def build_sensitive_path_probe_context_rows(
    summaries: List[Dict[str, Any]],
    known_asset_ips: Sequence[str],
    top_n: int = SENSITIVE_PATH_PROBE_CONTEXT_LIMIT,
) -> List[Dict[str, Any]]:
    known_asset_set = set(known_asset_ips)
    rows: List[Dict[str, Any]] = []
    for item in summaries:
        src_ip = normalize_str(item.get("src_ip")) or "-"
        rows.append(
            {
                "context_role": normalize_str(item.get("context_role")) or "sensitive_path_probe_context",
                "aggregate_scope": normalize_str(item.get("aggregate_scope")) or "same_src_ip_sensitive_path_time_window",
                "should_promote_to_candidate": bool(item.get("should_promote_to_candidate")),
                "src_ip": src_ip,
                "window_start": normalize_str(item.get("window_start")),
                "window_end": normalize_str(item.get("window_end")),
                "burst_window_sec": safe_int(item.get("burst_window_sec"), 0),
                "request_count": safe_int(item.get("request_count"), 0),
                "status_counts": normalize_counter_dict(item.get("status_counts")),
                "path_categories_observed": truncate_unique_strings(item.get("path_categories_observed")),
                "path_counts": normalize_counter_dict(item.get("path_counts")),
                "sample_request_ids": truncate_unique_strings(item.get("sample_request_ids")),
                "reason_hints": truncate_unique_strings(item.get("reason_hints")),
                "interpretation_limit": normalize_str(item.get("interpretation_limit"))
                or "sensitive_path_probe_no_file_or_app_exposure_inference",
                "known_asset": src_ip in known_asset_set,
            }
        )

    rows.sort(
        key=lambda x: (
            safe_int(x.get("request_count"), 0),
            len(x.get("path_categories_observed") or []),
            normalize_str(x.get("window_start")),
        ),
        reverse=True,
    )
    return rows[:top_n]


def build_mixed_baseline_scanner_context_rows(
    summaries: List[Dict[str, Any]],
    known_asset_ips: Sequence[str],
    top_n: int = MIXED_BASELINE_SCANNER_CONTEXT_LIMIT,
) -> List[Dict[str, Any]]:
    known_asset_set = set(known_asset_ips)
    rows: List[Dict[str, Any]] = []
    for item in summaries:
        src_ip = normalize_str(item.get("src_ip")) or "-"
        rows.append(
            {
                "context_role": normalize_str(item.get("context_role")) or "mixed_baseline_scanner_context",
                "aggregate_scope": normalize_str(item.get("aggregate_scope")) or "same_src_ip_mixed_baseline_scanner_time_window",
                "should_promote_to_candidate": bool(item.get("should_promote_to_candidate")),
                "src_ip": src_ip,
                "window_start": normalize_str(item.get("window_start")),
                "window_end": normalize_str(item.get("window_end")),
                "burst_window_sec": safe_int(item.get("burst_window_sec"), 0),
                "request_count": safe_int(item.get("request_count"), 0),
                "status_counts": normalize_counter_dict(item.get("status_counts")),
                "baseline_contexts_observed": truncate_unique_strings(item.get("baseline_contexts_observed")),
                "scanner_contexts_observed": truncate_unique_strings(item.get("scanner_contexts_observed")),
                "path_categories_observed": truncate_unique_strings(item.get("path_categories_observed")),
                "sample_request_ids": truncate_unique_strings(item.get("sample_request_ids")),
                "reason_hints": truncate_unique_strings(item.get("reason_hints")),
                "interpretation_limit": normalize_str(item.get("interpretation_limit"))
                or "mixed_context_no_success_or_single_attack_inference",
                "known_asset": src_ip in known_asset_set,
            }
        )

    rows.sort(
        key=lambda x: (
            safe_int(x.get("request_count"), 0),
            len(x.get("baseline_contexts_observed") or []),
            len(x.get("scanner_contexts_observed") or []),
            normalize_str(x.get("window_start")),
        ),
        reverse=True,
    )
    return rows[:top_n]


def build_ip_behavior_context_rows(
    aggregates: List[Dict[str, Any]],
    known_asset_ips: Sequence[str],
    top_n: int = IP_BEHAVIOR_CONTEXT_LIMIT,
) -> List[Dict[str, Any]]:
    known_asset_set = set(known_asset_ips)
    rows: List[Dict[str, Any]] = []
    for item in aggregates:
        src_ip = normalize_str(item.get("src_ip")) or "-"
        rows.append(
            {
                "context_role": normalize_str(item.get("context_role")) or "ip_behavior_context",
                "aggregate_scope": normalize_str(item.get("aggregate_scope")) or "same_src_ip_time_window",
                "should_promote_to_candidate": bool(item.get("should_promote_to_candidate")),
                "src_ip": src_ip,
                "window_start": normalize_str(item.get("window_start")),
                "window_end": normalize_str(item.get("window_end")),
                "burst_window_sec": safe_int(item.get("burst_window_sec"), 0),
                "request_count": safe_int(item.get("request_count"), 0),
                "distinct_paths": safe_int(item.get("distinct_paths"), 0),
                "distinct_methods": safe_int(item.get("distinct_methods"), 0),
                "status_4xx_count": safe_int(item.get("status_4xx_count"), 0),
                "status_4xx_ratio": round(safe_float(item.get("status_4xx_ratio"), 0.0), 4),
                "status_5xx_count": safe_int(item.get("status_5xx_count"), 0),
                "distinct_user_agents": safe_int(item.get("distinct_user_agents"), 0),
                "attack_categories_attempted": truncate_unique_strings(item.get("attack_categories_attempted")),
                "sensitive_path_hits": truncate_unique_strings(item.get("sensitive_path_hits")),
                "sample_request_ids": truncate_unique_strings(item.get("sample_request_ids")),
                "reason_hints": truncate_unique_strings(item.get("reason_hints")),
                "interpretation_limit": normalize_str(item.get("interpretation_limit")) or "context_only_no_success_inference",
                "known_asset": src_ip in known_asset_set,
            }
        )

    rows.sort(
        key=lambda x: (
            safe_int(x.get("request_count"), 0),
            len(x.get("attack_categories_attempted") or []),
            safe_int(x.get("distinct_paths"), 0),
            safe_float(x.get("status_4xx_ratio"), 0.0),
            normalize_str(x.get("window_start")),
        ),
        reverse=True,
    )
    return rows[:top_n]


def build_auth_behavior_context_rows(
    summaries: List[Dict[str, Any]],
    known_asset_ips: Sequence[str],
    top_n: int = AUTH_BEHAVIOR_CONTEXT_LIMIT,
) -> List[Dict[str, Any]]:
    known_asset_set = set(known_asset_ips)
    rows: List[Dict[str, Any]] = []
    for item in summaries:
        src_ip = normalize_str(item.get("src_ip")) or "-"
        rows.append(
            {
                "context_role": normalize_str(item.get("context_role")) or "auth_behavior_context",
                "aggregate_scope": normalize_str(item.get("aggregate_scope")) or "same_src_ip_auth_endpoint_time_window",
                "should_promote_to_candidate": bool(item.get("should_promote_to_candidate")),
                "src_ip": src_ip,
                "window_start": normalize_str(item.get("window_start")),
                "window_end": normalize_str(item.get("window_end")),
                "burst_window_sec": safe_int(item.get("burst_window_sec"), 0),
                "endpoint_family": normalize_str(item.get("endpoint_family")) or "auth_endpoint",
                "request_count": safe_int(item.get("request_count"), 0),
                "auth_request_count": safe_int(item.get("auth_request_count"), 0),
                "status_counts": normalize_counter_dict(item.get("status_counts")),
                "status_4xx_count": safe_int(item.get("status_4xx_count"), 0),
                "status_2xx_count": safe_int(item.get("status_2xx_count"), 0),
                "has_repeated_401": bool(item.get("has_repeated_401")),
                "has_rapid_burst": bool(item.get("has_rapid_burst")),
                "has_mixed_401_200": bool(item.get("has_mixed_401_200")),
                "has_single_200_only": bool(item.get("has_single_200_only")),
                "distinct_user_agents": safe_int(item.get("distinct_user_agents"), 0),
                "sample_request_ids": truncate_unique_strings(item.get("sample_request_ids")),
                "reason_hints": truncate_unique_strings(item.get("reason_hints")),
                "interpretation_limit": normalize_str(item.get("interpretation_limit"))
                or "post_body_not_visible_no_auth_success_inference",
                "known_asset": src_ip in known_asset_set,
            }
        )

    rows.sort(
        key=lambda x: (
            safe_int(x.get("request_count"), 0),
            safe_int(x.get("status_4xx_count"), 0),
            safe_int(x.get("status_2xx_count"), 0),
            normalize_str(x.get("window_start")),
        ),
        reverse=True,
    )
    return rows[:top_n]


def build_method_behavior_context_rows(
    summaries: List[Dict[str, Any]],
    known_asset_ips: Sequence[str],
    top_n: int = METHOD_BEHAVIOR_CONTEXT_LIMIT,
) -> List[Dict[str, Any]]:
    known_asset_set = set(known_asset_ips)
    rows: List[Dict[str, Any]] = []
    for item in summaries:
        src_ip = normalize_str(item.get("src_ip")) or "-"
        rows.append(
            {
                "context_role": normalize_str(item.get("context_role")) or "method_behavior_context",
                "aggregate_scope": normalize_str(item.get("aggregate_scope")) or "same_src_ip_method_time_window",
                "should_promote_to_candidate": bool(item.get("should_promote_to_candidate")),
                "src_ip": src_ip,
                "window_start": normalize_str(item.get("window_start")),
                "window_end": normalize_str(item.get("window_end")),
                "burst_window_sec": safe_int(item.get("burst_window_sec"), 0),
                "request_count": safe_int(item.get("request_count"), 0),
                "method_counts": normalize_counter_dict(item.get("method_counts")),
                "status_counts": normalize_counter_dict(item.get("status_counts")),
                "risky_methods_observed": truncate_unique_strings(item.get("risky_methods_observed")),
                "baseline_methods_observed": truncate_unique_strings(item.get("baseline_methods_observed")),
                "sample_request_ids": truncate_unique_strings(item.get("sample_request_ids")),
                "reason_hints": truncate_unique_strings(item.get("reason_hints")),
                "interpretation_limit": normalize_str(item.get("interpretation_limit"))
                or "no_method_success_inference_from_apache_logs",
                "known_asset": src_ip in known_asset_set,
            }
        )

    rows.sort(
        key=lambda x: (
            safe_int(x.get("request_count"), 0),
            len(x.get("risky_methods_observed") or []),
            len(x.get("baseline_methods_observed") or []),
            normalize_str(x.get("window_start")),
        ),
        reverse=True,
    )
    return rows[:top_n]


def build_protocol_anomaly_context_rows(
    summaries: List[Dict[str, Any]],
    known_asset_ips: Sequence[str],
    top_n: int = PROTOCOL_ANOMALY_CONTEXT_LIMIT,
) -> List[Dict[str, Any]]:
    known_asset_set = set(known_asset_ips)
    rows: List[Dict[str, Any]] = []
    for item in summaries:
        src_ip = normalize_str(item.get("src_ip")) or "-"
        rows.append(
            {
                "context_role": normalize_str(item.get("context_role")) or "protocol_anomaly_context",
                "aggregate_scope": normalize_str(item.get("aggregate_scope")) or "same_src_ip_protocol_anomaly_time_window",
                "should_promote_to_candidate": bool(item.get("should_promote_to_candidate")),
                "src_ip": src_ip,
                "window_start": normalize_str(item.get("window_start")),
                "window_end": normalize_str(item.get("window_end")),
                "burst_window_sec": safe_int(item.get("burst_window_sec"), 0),
                "request_count": safe_int(item.get("request_count"), 0),
                "status_counts": normalize_counter_dict(item.get("status_counts")),
                "method_counts": normalize_counter_dict(item.get("method_counts")),
                "anomaly_types_observed": truncate_unique_strings(item.get("anomaly_types_observed")),
                "sample_request_ids": truncate_unique_strings(item.get("sample_request_ids")),
                "reason_hints": truncate_unique_strings(item.get("reason_hints")),
                "interpretation_limit": normalize_str(item.get("interpretation_limit"))
                or "protocol_anomaly_context_only_no_success_inference",
                "known_asset": src_ip in known_asset_set,
            }
        )

    rows.sort(
        key=lambda x: (
            safe_int(x.get("request_count"), 0),
            len(x.get("anomaly_types_observed") or []),
            normalize_str(x.get("window_start")),
        ),
        reverse=True,
    )
    return rows[:top_n]


def has_php_wrapper_file_disclosure_context(item: Dict[str, Any]) -> bool:
    verdict = normalize_str(item.get("verdict"))
    if verdict == "suspicious_file_disclosure":
        return True
    hints = [normalize_str(x) for x in (item.get("reason_hints") or []) if normalize_str(x)]
    required = {
        "file_disclosure:php_filter_wrapper",
        "file_disclosure:base64_source_intent",
        "file_disclosure:resource_parameter",
    }
    return required.issubset(set(hints))


def build_behavior_scope_note(
    ip_behavior_aggregates: Sequence[Dict[str, Any]],
    auth_behavior_summaries: Sequence[Dict[str, Any]],
) -> Optional[str]:
    ip_rows_by_src: Dict[str, Dict[str, Any]] = {}
    for item in ip_behavior_aggregates:
        src_ip = normalize_str(item.get("src_ip"))
        if src_ip and src_ip not in ip_rows_by_src:
            ip_rows_by_src[src_ip] = item

    for auth_item in auth_behavior_summaries:
        src_ip = normalize_str(auth_item.get("src_ip"))
        if not src_ip:
            continue
        ip_item = ip_rows_by_src.get(src_ip)
        if not ip_item:
            continue
        auth_request_count = safe_int(
            auth_item.get("auth_request_count"),
            safe_int(auth_item.get("request_count"), 0),
        )
        ip_request_count = safe_int(ip_item.get("request_count"), 0)
        return (
            f"auth behavior summary 기준으로는 {auth_request_count}건의 auth endpoint 요청이 관찰되었고, "
            f"ip behavior aggregate 기준으로는 같은 src_ip/time window 에서 {ip_request_count}건의 전체 요청 문맥이 관찰되었다. "
            "두 집계는 scope 가 다르므로 같은 사건 수로 직접 합산하지 않는다."
        )

    return None


def build_report_input(
    stage1_payload: Dict[str, Any],
    llm_input_payload: Optional[Dict[str, Any]],
    stage1_errors_payload: Optional[Dict[str, Any]],
    top_incidents: int,
    top_noise_groups: int,
    top_ips: int,
    known_asset_ips: Sequence[str],
) -> Dict[str, Any]:
    results = stage1_payload.get("results") or []
    meta = stage1_payload.get("meta") or {}
    llm_meta = (llm_input_payload or {}).get("meta") or {}
    counts = llm_meta.get("counts") or {}
    noise_summary = (llm_input_payload or {}).get("noise_summary") or []
    supporting_events = (llm_input_payload or {}).get("supporting_events") or []
    false_positive_review_candidates = (llm_input_payload or {}).get("false_positive_review_candidates") or []
    probing_sequence_summaries = (llm_input_payload or {}).get("probing_sequence_summaries") or []
    static_baseline_summaries = (llm_input_payload or {}).get("static_baseline_summaries") or []
    crawler_baseline_summaries = (llm_input_payload or {}).get("crawler_baseline_summaries") or []
    sensitive_path_probe_summaries = (llm_input_payload or {}).get("sensitive_path_probe_summaries") or []
    mixed_baseline_scanner_summaries = (llm_input_payload or {}).get("mixed_baseline_scanner_summaries") or []
    ip_behavior_aggregates = (llm_input_payload or {}).get("ip_behavior_aggregates") or []
    auth_behavior_summaries = (llm_input_payload or {}).get("auth_behavior_summaries") or []
    method_behavior_summaries = (llm_input_payload or {}).get("method_behavior_summaries") or []
    protocol_anomaly_summaries = (llm_input_payload or {}).get("protocol_anomaly_summaries") or []
    stage1_errors = (stage1_errors_payload or {}).get("errors") or []
    filtered_out_breakdown = normalize_counter_dict(llm_meta.get("filtered_out_breakdown"))
    total_filtered_out_rows = safe_int(counts.get("filtered_out_rows"), 0)
    candidate_lookup = build_candidate_evidence_lookup(llm_input_payload)

    deduped_results = dedup_stage1_results(results, known_asset_ips=known_asset_ips)

    verdict_counter = Counter(normalize_str(x.get("verdict")) or "unknown" for x in deduped_results)
    severity_counter = Counter(normalize_str(x.get("severity")) or "unknown" for x in deduped_results)
    action_counter = Counter(
        normalize_str(action)
        for row in deduped_results
        for action in (row.get("recommended_actions") or [])
        if normalize_str(action)
    )
    table_counter = Counter(normalize_str(x.get("source_table")) or "unknown" for x in deduped_results)

    briefs = [
        asdict(x)
        for x in build_incident_briefs(
            results,
            top_n=top_incidents,
            known_asset_ips=known_asset_ips,
            candidate_lookup=candidate_lookup,
        )
    ]
    ip_rows = summarize_ips(results, top_n=top_ips, known_asset_ips=known_asset_ips)
    top_noise = sorted(
        noise_summary,
        key=lambda x: safe_int(x.get("count"), 0),
        reverse=True,
    )[:top_noise_groups]
    top_filtered_categories = build_filtered_category_rows(
        filtered_out_breakdown=filtered_out_breakdown,
        total_filtered_out_rows=total_filtered_out_rows,
        top_n=top_noise_groups,
    )
    top_out_of_candidate_recon = build_out_of_candidate_recon_rows(
        filtered_out_breakdown=filtered_out_breakdown,
        total_filtered_out_rows=total_filtered_out_rows,
        top_n=top_noise_groups,
    )
    top_static_baseline_summaries = build_static_baseline_context_rows(
        static_baseline_summaries,
        known_asset_ips=known_asset_ips,
        top_n=STATIC_BASELINE_CONTEXT_LIMIT,
    )
    top_crawler_baseline_summaries = build_crawler_baseline_context_rows(
        crawler_baseline_summaries,
        known_asset_ips=known_asset_ips,
        top_n=CRAWLER_BASELINE_CONTEXT_LIMIT,
    )
    top_sensitive_path_probe_summaries = build_sensitive_path_probe_context_rows(
        sensitive_path_probe_summaries,
        known_asset_ips=known_asset_ips,
        top_n=SENSITIVE_PATH_PROBE_CONTEXT_LIMIT,
    )
    top_mixed_baseline_scanner_summaries = build_mixed_baseline_scanner_context_rows(
        mixed_baseline_scanner_summaries,
        known_asset_ips=known_asset_ips,
        top_n=MIXED_BASELINE_SCANNER_CONTEXT_LIMIT,
    )
    top_ip_behavior_aggregates = build_ip_behavior_context_rows(
        ip_behavior_aggregates,
        known_asset_ips=known_asset_ips,
        top_n=IP_BEHAVIOR_CONTEXT_LIMIT,
    )
    top_auth_behavior_summaries = build_auth_behavior_context_rows(
        auth_behavior_summaries,
        known_asset_ips=known_asset_ips,
        top_n=AUTH_BEHAVIOR_CONTEXT_LIMIT,
    )
    top_method_behavior_summaries = build_method_behavior_context_rows(
        method_behavior_summaries,
        known_asset_ips=known_asset_ips,
        top_n=METHOD_BEHAVIOR_CONTEXT_LIMIT,
    )
    top_protocol_anomaly_summaries = build_protocol_anomaly_context_rows(
        protocol_anomaly_summaries,
        known_asset_ips=known_asset_ips,
        top_n=PROTOCOL_ANOMALY_CONTEXT_LIMIT,
    )

    matched_known_assets = sorted(
        {
            normalize_str(x.get("src_ip"))
            for x in deduped_results
            if normalize_str(x.get("src_ip")) in set(known_asset_ips)
        }
    )

    return {
        "analysis_context": {
            "query_timezone": llm_meta.get("query_timezone") or meta.get("source_query_timezone") or "Asia/Seoul",
            "window": llm_meta.get("analysis_window") or meta.get("source_window") or {},
            "source_exported_at": meta.get("source_exported_at") or llm_meta.get("exported_at"),
            "source_prepared_at": meta.get("source_prepared_at") or llm_meta.get("prepared_at"),
            "stage1_generated_at": meta.get("generated_at"),
            "mode": meta.get("mode"),
            "selected_model": meta.get("selected_model"),
        },
        "pipeline_counts": {
            "total_exported_rows": safe_int(counts.get("total_exported_rows"), 0),
            "candidate_rows": safe_int(counts.get("candidate_rows"), len(results)),
            "distinct_incident_count": len(deduped_results),
            "filtered_out_rows": total_filtered_out_rows,
            "filtered_out_non_aggregated_rows": safe_int(counts.get("filtered_out_non_aggregated_rows"), 0),
            "noise_group_count": safe_int(counts.get("noise_group_count"), len(noise_summary)),
            "supporting_event_count": safe_int(counts.get("supporting_events"), len(supporting_events)),
            "false_positive_review_candidate_count": safe_int(
                counts.get("false_positive_review_candidates"),
                len(false_positive_review_candidates),
            ),
            "probing_sequence_summary_count": safe_int(
                counts.get("probing_sequence_summaries"),
                len(probing_sequence_summaries),
            ),
            "static_baseline_summary_count": safe_int(
                counts.get("static_baseline_summaries"),
                len(static_baseline_summaries),
            ),
            "crawler_baseline_summary_count": safe_int(
                counts.get("crawler_baseline_summaries"),
                len(crawler_baseline_summaries),
            ),
            "sensitive_path_probe_summary_count": safe_int(
                counts.get("sensitive_path_probe_summaries"),
                len(sensitive_path_probe_summaries),
            ),
            "mixed_baseline_scanner_summary_count": safe_int(
                counts.get("mixed_baseline_scanner_summaries"),
                len(mixed_baseline_scanner_summaries),
            ),
            "ip_behavior_aggregate_count": safe_int(
                counts.get("ip_behavior_aggregates"),
                len(ip_behavior_aggregates),
            ),
            "auth_behavior_summary_count": safe_int(
                counts.get("auth_behavior_summaries"),
                len(auth_behavior_summaries),
            ),
            "method_behavior_summary_count": safe_int(
                counts.get("method_behavior_summaries"),
                len(method_behavior_summaries),
            ),
            "protocol_anomaly_summary_count": safe_int(
                counts.get("protocol_anomaly_summaries"),
                len(protocol_anomaly_summaries),
            ),
            "stage1_success_count": safe_int(meta.get("success_count"), len(results)),
            "stage1_error_count": safe_int(meta.get("error_count"), len(stage1_errors)),
        },
        "distributions": {
            "verdicts": dict(verdict_counter),
            "severities": dict(severity_counter),
            "source_tables": dict(table_counter),
            "recommended_actions": dict(action_counter),
            "filtered_out_breakdown": filtered_out_breakdown,
        },
        "top_incidents": briefs,
        "top_src_ips": ip_rows,
        "top_noise_groups": top_noise,
        "top_filtered_categories": top_filtered_categories,
        "top_out_of_candidate_recon": top_out_of_candidate_recon,
        "probing_sequence_summary_count": safe_int(
            counts.get("probing_sequence_summaries"),
            len(probing_sequence_summaries),
        ),
        "static_baseline_summary_count": safe_int(
            counts.get("static_baseline_summaries"),
            len(static_baseline_summaries),
        ),
        "crawler_baseline_summary_count": safe_int(
            counts.get("crawler_baseline_summaries"),
            len(crawler_baseline_summaries),
        ),
        "sensitive_path_probe_summary_count": safe_int(
            counts.get("sensitive_path_probe_summaries"),
            len(sensitive_path_probe_summaries),
        ),
        "mixed_baseline_scanner_summary_count": safe_int(
            counts.get("mixed_baseline_scanner_summaries"),
            len(mixed_baseline_scanner_summaries),
        ),
        "ip_behavior_aggregate_count": safe_int(
            counts.get("ip_behavior_aggregates"),
            len(ip_behavior_aggregates),
        ),
        "auth_behavior_summary_count": safe_int(
            counts.get("auth_behavior_summaries"),
            len(auth_behavior_summaries),
        ),
        "method_behavior_summary_count": safe_int(
            counts.get("method_behavior_summaries"),
            len(method_behavior_summaries),
        ),
        "protocol_anomaly_summary_count": safe_int(
            counts.get("protocol_anomaly_summaries"),
            len(protocol_anomaly_summaries),
        ),
        "probing_sequence_summaries": probing_sequence_summaries[:10],
        "static_baseline_summaries": top_static_baseline_summaries,
        "crawler_baseline_summaries": top_crawler_baseline_summaries,
        "sensitive_path_probe_summaries": top_sensitive_path_probe_summaries,
        "mixed_baseline_scanner_summaries": top_mixed_baseline_scanner_summaries,
        "ip_behavior_aggregates": top_ip_behavior_aggregates,
        "auth_behavior_summaries": top_auth_behavior_summaries,
        "method_behavior_summaries": top_method_behavior_summaries,
        "protocol_anomaly_summaries": top_protocol_anomaly_summaries,
        "supporting_events": supporting_events[:20],
        "false_positive_review_candidates": false_positive_review_candidates[:20],
        "stage1_errors_excerpt": stage1_errors[:5],
        "asset_context": {
            "known_asset_ips": list(known_asset_ips),
            "matched_known_assets": matched_known_assets,
            "matched_known_asset_incident_count": sum(1 for x in deduped_results if bool(x.get("known_asset"))),
            "caution": "known asset IP 에서 발생한 요청은 내부 테스트, 자체 호출, 운영 점검 트래픽일 수 있으므로 공격자 단정에 주의",
        },
        "policy_notes": {
            "routine_model_default": "gpt-5.4-mini",
            "milestone_presentation_model_default": "gpt-5.4",
            "raw_db_logs_are_not_sent_directly": True,
            "noise_is_aggregated_before_llm": True,
            "filtered_out_breakdown_is_preserved": bool(llm_meta.get("pipeline_policy", {}).get("filtered_noise_breakdown_is_preserved", False)),
            "dedupe_rule": "request_id 우선, 없으면 src_ip+method+uri+status_code+1초 단위 시각으로 incident 병합",
            "out_of_candidate_recon_policy": {
                "default_action": "low_signal_fuzzing 과 low_signal_dir_probe 는 기본적으로 incident 로 승격하지 않음",
                "reporting_rule": "stage2 에서는 low_signal_fuzzing 과 low_signal_dir_probe 만 후보 밖 탐색성 요청으로 표기",
                "promotion_review_rule": "동일 IP, 동일 시간대, 후속 고신호 incident 와 결합될 때만 승격 검토",
            },
            "reference_baseline_policy": {
                "default_action": "benign_normal_search 또는 normal_search_baseline 카테고리와 supporting_role=reference_baseline 은 정상 비교군으로 해석",
                "reporting_rule": "후보 밖 탐색성 요청이나 low signal fuzzing 으로 표현하지 않고 같은 endpoint 의 정상 baseline 또는 reference baseline 으로 설명",
                "comparison_rule": "정상 baseline 이 근접해 있어도 공격 candidate 의 의도나 심각도를 낮추지 않고 정상/공격 비교 문맥으로만 사용",
            },
            "probing_sequence_policy": {
                "default_action": "probing_sequence_summaries 는 context-only 이며 개별 incident 로 승격하지 않음",
                "interpretation_rule": "같은 src_ip, 짧은 시간 window, 여러 민감/관리/백업 경로 접근은 reconnaissance 또는 directory probing 정황으로만 설명",
                "fallback_rule": "반복되는 200 text/html 동일 응답 크기는 fallback HTML 가능성으로만 설명하고 민감 리소스 노출 성공으로 단정하지 않음",
                "blocked_rule": "예: /server-status 403 같은 차단 응답은 access control 이 동작한 정황으로 설명하되 scan/probe intent 는 보조적으로 언급 가능",
            },
            "static_baseline_summary_policy": {
                "default_action": "static_baseline_summaries 는 context-only 이며 개별 incident 나 analysis_candidate 로 승격하지 않음",
                "interpretation_rule": "favicon, robots.txt, sitemap.xml, static asset, health check, normal GET 은 baseline/static context 로만 설명",
                "success_rule": "status_code, response_body_bytes, content_type 만으로 static file 내용, crawler policy, site structure, JS 실행, file exposure, health 상태를 단정하지 않음",
                "visibility_rule": "Apache 로그 표면에서는 response body 원문, 브라우저 실행 여부, 서버 내부 파일 존재 여부를 확인할 수 없으므로 static/baseline outcome 은 관찰 문맥으로만 해석",
            },
            "crawler_baseline_summary_policy": {
                "default_action": "crawler_baseline_summaries 는 context-only 이며 개별 incident 나 analysis_candidate 로 승격하지 않음",
                "interpretation_rule": "crawler-like User-Agent, robots.txt, sitemap.xml, product/category browse 요청은 crawler-like baseline 또는 low-signal crawl context 로만 설명",
                "ua_rule": "Googlebot/Bingbot/GenericCrawler-like User-Agent 는 spoof 가능하므로 실제 crawler 정체를 단정하지 않음",
                "success_rule": "status_code, response_body_bytes, content_type 만으로 robots policy, sitemap 내용, site structure, product/category page existence, 공격 성공을 단정하지 않음",
                "visibility_rule": "Apache 로그 표면에서는 response body 원문, crawler verification, 서버 내부 page 존재 여부를 확인할 수 없으므로 crawler/browse outcome 은 관찰 문맥으로만 해석",
            },
            "sensitive_path_probe_summary_policy": {
                "default_action": "sensitive_path_probe_summaries 는 context-only 이며 개별 incident 나 analysis_candidate 로 승격하지 않음",
                "interpretation_rule": "wp-login/wp-admin/.env/phpinfo/server-status/backup.zip 같은 path 는 scanner-like sensitive path probing context 로만 설명",
                "success_rule": "status_code, response_body_bytes, content_type 만으로 WordPress 존재, admin access, .env 노출, phpinfo 노출, server-status 노출/차단, backup 노출, 공격 성공을 단정하지 않음",
                "visibility_rule": "Apache 로그 표면에서는 response body 원문, 서버 내부 파일 존재 여부, 애플리케이션 종류를 확인할 수 없으므로 sensitive path outcome 은 관찰 문맥으로만 해석",
            },
            "mixed_baseline_scanner_summary_policy": {
                "default_action": "mixed_baseline_scanner_summaries 는 context-only 이며 개별 incident 나 analysis_candidate 로 승격하지 않음",
                "interpretation_rule": "baseline/static/crawler-like 요청과 scanner-like sensitive path 가 같은 window 에 함께 있어도 단일 공격 성공으로 합치지 않고 각각의 문맥을 분리해서 설명",
                "separation_rule": "normal/static/crawler-like baseline 과 sensitive path probe context 를 구분해 설명",
                "success_rule": "status_code, response_body_bytes, content_type 만으로 file exposure, app presence, crawler authenticity, page existence, attack success 를 단정하지 않음",
                "visibility_rule": "Apache 로그 표면에서는 response body 원문, crawler verification, 서버 내부 파일 존재 여부를 확인할 수 없으므로 mixed context 는 관찰 문맥으로만 해석",
            },
            "behavior_scope_separation_policy": {
                "static_scope_rule": "static_baseline_summaries 의 request_count 는 같은 src_ip 와 static/health/browse baseline 시간창 기준 관찰 수를 뜻함",
                "crawler_scope_rule": "crawler_baseline_summaries 의 request_count 는 같은 src_ip 와 crawler-like UA/browse baseline 시간창 기준 관찰 수를 뜻함",
                "sensitive_path_scope_rule": "sensitive_path_probe_summaries 의 request_count 는 같은 src_ip 와 sensitive path 시간창 기준 관찰 수를 뜻함",
                "mixed_scope_rule": "mixed_baseline_scanner_summaries 의 request_count 는 같은 src_ip 와 mixed baseline/scanner 시간창 기준 관찰 수를 뜻함",
                "auth_scope_rule": "auth_behavior_summaries 의 request_count/auth_request_count 는 같은 src_ip 와 auth endpoint family 시간창 기준 auth 요청 수를 뜻함",
                "method_scope_rule": "method_behavior_summaries 의 request_count 는 같은 src_ip 와 method/protocol relevant row 시간창 기준 관찰 수를 뜻함",
                "protocol_scope_rule": "protocol_anomaly_summaries 의 request_count 는 같은 src_ip 와 protocol anomaly relevant row 시간창 기준 관찰 수를 뜻함",
                "ip_scope_rule": "ip_behavior_aggregates 의 request_count 는 같은 src_ip 와 시간창 기준 전체 또는 관련 요청 문맥 수를 뜻함",
                "non_merge_rule": "static_baseline_summaries, crawler_baseline_summaries, sensitive_path_probe_summaries, mixed_baseline_scanner_summaries, auth_behavior_summaries, method_behavior_summaries, protocol_anomaly_summaries, ip_behavior_aggregates 는 scope 가 다르므로 48~51건 같은 range 표현이나 직접 합산으로 설명하지 않음",
                "context_only_rule": "static_baseline_summaries, crawler_baseline_summaries, sensitive_path_probe_summaries, mixed_baseline_scanner_summaries, auth_behavior_summaries, method_behavior_summaries, protocol_anomaly_summaries, ip_behavior_aggregates 는 모두 context-only 이며 candidate 승격 근거가 아님",
            },
            "ip_behavior_aggregate_policy": {
                "default_action": "ip_behavior_aggregates 는 context-only 이며 개별 incident 나 analysis_candidate 로 승격하지 않음",
                "promotion_rule": "should_promote_to_candidate=false 이면 어떤 개별 row 도 이 aggregate 때문에 incident 후보로 승격된 것으로 해석하지 않음",
                "interpretation_rule": "같은 src_ip, 짧은 시간 window, 높은 4xx 비율, 다중 attempted category, 민감 경로 접근은 reconnaissance/scanning-like context 로만 설명",
                "category_rule": "attack_categories_attempted 는 시도 유형 요약이지 성공한 공격 목록이 아님",
                "sensitive_path_rule": "sensitive_path_hits 는 민감 경로 접근 시도 문맥일 뿐 실제 파일 노출 또는 침해 성공 근거가 아님",
                "success_rule": "status_code=200, text/html, response_body_bytes, status_5xx_count 만으로 공격 성공, 침해 성공, 파일 노출, XSS 실행, DB 유출을 단정하지 않음",
                "identity_rule": "동일 src_ip 는 scanning-like behavior 가 관찰된 출발지로만 표현하고 공격자나 침해 주체로 단정하지 않음",
            },
            "auth_behavior_summary_policy": {
                "default_action": "auth_behavior_summaries 는 context-only 이며 개별 incident 나 analysis_candidate 로 승격하지 않음",
                "promotion_rule": "should_promote_to_candidate=false 이면 어떤 개별 auth row 도 이 summary 때문에 incident 후보로 승격된 것으로 해석하지 않음",
                "interpretation_rule": "같은 src_ip, auth endpoint family, 짧은 시간 window 안의 반복 401, rapid burst, 401/200 혼재, 단독 200 baseline 을 auth behavior context 로만 설명",
                "visibility_rule": "Apache 로그 표면에서는 raw POST body 와 인증 결과 원문이 보이지 않을 수 있으므로 POST body 미확인 상태로 해석",
                "mixed_status_rule": "401 과 200 이 함께 있어도 HTTP 200 observed after repeated 401 정도로만 설명하고 로그인 성공, 계정 탈취, credential stuffing 성공으로 단정하지 않음",
                "success_rule": "status_code=200, response_body_bytes, resp_content_type 만으로 인증 성공이나 침해 성공 근거로 사용하지 않음",
                "identity_rule": "동일 src_ip 는 auth behavior sequence 가 관찰된 출발지로만 표현하고 공격자나 계정 탈취 주체로 단정하지 않음",
            },
            "method_behavior_summary_policy": {
                "default_action": "method_behavior_summaries 는 context-only 이며 개별 incident 나 analysis_candidate 로 승격하지 않음",
                "promotion_rule": "should_promote_to_candidate=false 이면 어떤 개별 method row 도 이 summary 때문에 incident 후보로 승격된 것으로 해석하지 않음",
                "interpretation_rule": "같은 src_ip, 짧은 시간 window 안에서 risky method 와 baseline method 가 섞여 관찰된 method probing 또는 baseline context 로만 설명",
                "success_rule": "OPTIONS, TRACE, PUT, DELETE, PATCH 의 status_code=200/201/204, response_body_bytes, status_counts 만으로 method 허용, 업로드 성공, 삭제 성공, XST 성공, CORS 취약점을 단정하지 않음",
                "baseline_rule": "HEAD 와 GET 은 method baseline 또는 reference context 로만 설명하고 candidate 로 재승격하지 않음",
                "visibility_rule": "Apache 로그 표면에서는 response body 원문, request body 원문, 서버 내부 상태를 확인할 수 없으므로 method outcome 은 시도 문맥으로만 해석",
            },
            "protocol_anomaly_summary_policy": {
                "default_action": "protocol_anomaly_summaries 는 context-only 이며 개별 incident 나 analysis_candidate 로 승격하지 않음",
                "interpretation_rule": "invalid method, bad protocol version, missing/odd Host, long path 는 request parsing/protocol surface 관찰 문맥으로만 설명",
                "success_rule": "status_code=200/400/405/408/414/500/501/505 또는 response_body_bytes 만으로 우회 성공, 침해 성공, 서버 취약점 성공을 단정하지 않음",
                "visibility_rule": "Apache 로그 표면에서는 response body 원문, request body 원문, 서버 내부 상태를 확인할 수 없으므로 protocol anomaly outcome 은 시도/관찰 문맥으로만 해석",
            },
            "user_agent_interpretation_policy": {
                "default_action": "User-Agent 는 보조 evidence 로만 사용",
                "generalization_rule": "lab-* 같은 실험 prefix 자체를 탐지 근거로 사용하지 않고, 비브라우저성 UA, 반복적 UA 패턴, 자동화 또는 테스트성 UA 가능성처럼 일반화해서 설명",
                "evidence_rule": "raw evidence 로 실제 user_agent 값을 표시할 수는 있지만 prefix 자체에 공격 의미를 과도하게 부여하지 않음",
                "known_asset_rule": "known asset IP 와 결합되면 내부 테스트 또는 운영 점검 가능성을 함께 병기",
            },
            "file_disclosure_policy": {
                "php_wrapper_rule": "php://filter/convert.base64-encode/resource=... 구조는 PHP stream wrapper 를 통해 대상 파일을 base64 인코딩된 형태로 읽도록 유도하는 source/config disclosure attempt 또는 LFI-like file disclosure attempt 로 설명 가능",
                "wrapper_vs_traversal_rule": "이는 단순 ../ path traversal 과 구분되는 PHP wrapper 기반 file disclosure 또는 source disclosure 시도이며, suspicious_file_disclosure verdict 또는 file_disclosure:* hint 가 있으면 해당 의미를 우선 설명",
                "hint_interpretation_rule": "file_disclosure:* reason_hints 는 의도/시도 근거이지 성공/유출 근거가 아님",
                "success_rule": "Apache 로그만으로 실제 PHP source/config 파일 내용 노출 성공을 확정하지 않음",
                "status_200_rule": "status_code=200, text/html, response_body_bytes 또는 200 empty body 는 정상 라우팅, 빈 PHP 출력, 로그인/에러 템플릿, fallback-like 응답 가능성을 함께 검토하며 file disclosure 성공 근거로 사용하지 않음",
                "direct_config_rule": "/config.php, /admin/config.php 직접 접근은 sensitive config path probing context 로 설명하고, wrapper payload 와 동일한 강한 file disclosure 시도로 과장하지 않으며 response body 원문 없이는 노출 성공으로 단정하지 않음",
                "empty_body_rule": "response_body_bytes=0 은 직접 접근 시도 또는 라우팅 성공 가능성만 시사하며 본문 노출 증거는 아님",
            },
            "supporting_events_policy": {
                "default_action": "supporting_events 는 개별 incident 가 아니라 문맥 정보로만 해석",
                "temporal_rule": "같은 src_ip 와 같은 uri 또는 endpoint family 의 근접 시계열로 해석",
                "reference_baseline_rule": "supporting_role=reference_baseline 또는 supporting_reason=nearby_normal_search_baseline 이면 같은 endpoint 의 정상 요청 예시로만 설명",
                "auth_behavior_rule": "supporting_role=auth_behavior_support 또는 supporting_reason=covered_by_auth_behavior_summary 이면 반복 auth 실패 row 가 top-level auth_behavior_summaries 에 의해 대표 사건 밖 문맥으로 정리된 것이라고 해석",
                "decoded_hint_rule": "encoding:* reason_hints 는 우회성 인코딩 시도 보조 근거로만 사용",
                "educational_sql_rule": "교육/문서 검색 문맥 hint 가 있으면 SQLi 단정을 낮추고 자연어 질의 가능성을 함께 검토",
            },
            "false_positive_review_policy": {
                "default_action": "false_positive_review_candidates 는 incident 로 승격하지 않고 prepare 단계에서 걸러진 자연어 검색 검토용으로만 사용",
                "reporting_rule": "LLM 이 낮춘 오탐인지 prepare 단계에서 제외된 오탐성 질의인지 구분할 때만 보조적으로 활용",
            },
        },
    }


def build_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "report_title": {"type": "string", "minLength": 1},
            "overall_assessment": {"type": "string", "minLength": 1},
            "executive_summary": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 6},
            "key_findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "minLength": 1},
                        "detail": {"type": "string", "minLength": 1},
                        "severity": {"type": "string", "enum": ["info", "low", "medium", "high", "critical"]},
                    },
                    "required": ["title", "detail", "severity"],
                    "additionalProperties": False,
                },
                "minItems": 3,
                "maxItems": 8,
            },
            "notable_incidents": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "incident_ref": {"type": "string", "minLength": 1},
                        "request_id": {"type": "string"},
                        "src_ip": {"type": "string"},
                        "verdict": {"type": "string"},
                        "severity": {"type": "string", "enum": ["info", "low", "medium", "high", "critical"]},
                        "why_it_matters": {"type": "string", "minLength": 1},
                    },
                    "required": ["incident_ref", "request_id", "src_ip", "verdict", "severity", "why_it_matters"],
                    "additionalProperties": False,
                },
                "minItems": 1,
                "maxItems": 6,
            },
            "notable_source_ips": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "src_ip": {"type": "string"},
                        "reason": {"type": "string", "minLength": 1},
                    },
                    "required": ["src_ip", "reason"],
                    "additionalProperties": False,
                },
                "minItems": 1,
                "maxItems": 6,
            },
            "noise_interpretation": {"type": "string", "minLength": 1},
            "recommended_actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "priority": {"type": "string", "enum": ["P1", "P2", "P3"]},
                        "action": {"type": "string", "minLength": 1},
                        "why": {"type": "string", "minLength": 1},
                    },
                    "required": ["priority", "action", "why"],
                    "additionalProperties": False,
                },
                "minItems": 3,
                "maxItems": 8,
            },
            "confidence_and_limitations": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 6,
            },
            "presentation_takeaway": {"type": "string", "minLength": 1},
        },
        "required": [
            "report_title",
            "overall_assessment",
            "executive_summary",
            "key_findings",
            "notable_incidents",
            "notable_source_ips",
            "noise_interpretation",
            "recommended_actions",
            "confidence_and_limitations",
            "presentation_takeaway",
        ],
        "additionalProperties": False,
    }


def build_messages(report_input: Dict[str, Any]) -> List[Dict[str, str]]:
    system_prompt = (
        "당신은 웹 보안 로그 2차 보고서 작성기다. "
        "Apache 웹 로그에 대한 사건형 분석 요약을 신중하고 실용적으로 작성하라. "
        "당신에게 주어진 것은 원본 DB 로그가 아니라 전처리 및 1차 분류가 끝난 요약 데이터뿐이다. "
        "과장하지 말고, 수상한 정황과 확정된 침해를 구분하라. "
        "심각도 표현은 필요한 최소 수준으로 사용하라. "
        "오탐 가능성이나 추가 상관분석 필요성이 있으면 분명히 언급하라. "
        "known_asset_ips 와 일치하는 출발지 IP 는 내부 테스트, 자체 호출, 운영 점검일 수 있으므로 공격자 단정 표현을 피하라. "
        "Apache 로그에는 raw POST body 원문이 없을 수 있으므로, raw POST body 기반 payload 성공/실패를 본 것처럼 단정하지 마라. "
        "path traversal 의 경우 200 응답만으로 실제 파일 노출을 단정하지 마라. "
        "resp_content_type 이 text/html 이거나 HTML fallback 정황이 있으면 시도 탐지와 실제 노출 가능성을 분리해서 서술하라. "
        "Apache 로그만으로 XSS payload 의 브라우저 실행 성공을 확정하지 마라. "
        "500 text/html 은 서버 처리 오류 정황일 수 있지만 XSS 실행 성공 근거로 단정하지 마라. "
        "200 application/json 응답도 브라우저 실행 성공 근거로 사용하지 마라. "
        "php://filter/convert.base64-encode/resource=... 구조는 PHP stream wrapper 를 통해 대상 파일을 base64 인코딩된 형태로 읽도록 유도하는 source/config disclosure attempt 또는 LFI-like file disclosure attempt 로 설명하라. "
        "이는 단순 ../ path traversal 과 구분되는 PHP wrapper 기반 file disclosure 시도다. "
        "file_disclosure:php_filter_wrapper, file_disclosure:base64_source_intent, file_disclosure:resource_parameter 같은 file_disclosure:* hint 는 의도/시도 근거이지 성공/유출 근거가 아니다. "
        "suspicious_file_disclosure verdict 가 있으면 PHP wrapper 기반 source/config disclosure 시도 의미를 우선 설명하되, Apache 로그만으로 실제 PHP source/config 파일 내용 노출 성공을 확정하지 마라. "
        "200 text/html 또는 response_body_bytes=0 응답은 정상 라우팅, 빈 PHP 출력, 로그인/에러 템플릿, fallback-like 응답일 수 있으므로 file disclosure 성공 근거로 사용하지 마라. "
        "/config.php, /admin/config.php 직접 접근은 민감 설정 파일 경로 probing context 로 설명하되 response body 원문 없이는 config 노출 성공으로 단정하지 마라. "
        "php://filter candidate 와 /config.php 또는 /admin/config.php 직접 접근은 같은 범주로 뭉뚱그리지 말고, 전자는 PHP wrapper 기반 file/source disclosure attempt, 후자는 sensitive config path probing context 로 구분해서 서술하라. "
        "document.cookie, localStorage, sessionStorage 접근 문자열은 브라우저 데이터 접근 의도 또는 탈취 시도 형태로만 표현하고, 실제 탈취 성공으로 단정하지 마라. "
        "외부 URL, fetch, location 변경, Image beacon 정황이 있어도 별도 네트워크나 애플리케이션 증거 없이는 외부 전송 성공을 확정하지 마라. "
        "HTML entity, URL encoding, double encoding 은 우회 또는 복원 가능한 payload 표현으로만 설명하고, 실행 성공의 직접 증거처럼 서술하지 마라. "
        "동일 파라미터가 반복되면 HPP(HTTP Parameter Pollution) 문맥을 검토하라. "
        "hpp_detected 가 true 이고 embedded_attack_hint 가 있으면, 사건 분류는 기존 SQLi/XSS 체계를 유지하되 보고서 설명에는 '중복 파라미터(HPP)를 이용한 시도' 문맥을 포함하라. "
        "noise_summary 가 비어 있어도 filtered_out_breakdown 이 있으면 후보 밖 요청의 세부 분포는 실제로 존재하는 것으로 해석하라. "
        "supporting_events 가 있으면 이는 개별 incident 가 아니라 같은 src_ip, uri 또는 endpoint family, 인접 시간대의 보조 문맥으로 해석하라. "
        "supporting_role=reference_baseline 또는 supporting_reason=nearby_normal_search_baseline 인 supporting_events 는 후보 밖 탐색성 요청이 아니라 같은 endpoint 의 정상 baseline 예시로 설명하라. "
        "supporting_role=auth_behavior_support 또는 supporting_reason=covered_by_auth_behavior_summary 인 supporting_events 는 반복 auth 실패 row 가 top-level auth_behavior_summaries 에 의해 대표 사건 밖 문맥으로 정리된 것으로 설명하고, 각 row 를 별도 incident 로 재승격하지 마라. "
        "benign_normal_search 또는 normal_search_baseline filtered_out category 는 low_signal_fuzzing 과 분리해서 정상 비교군 또는 reference baseline 으로 표현하라. "
        "정상 baseline 이 근접해 있어도 공격 candidate 의 의도나 심각도를 낮추는 근거로 사용하지 말고, 정상/공격 비교 문맥으로만 사용하라. "
        "supporting_events 의 encoding:* hint 는 우회성 인코딩 시도 보조 근거이며, educational_sql_search 계열 hint 는 자연어 검색 가능성을 함께 검토하라는 뜻이다. "
        "false_positive_review_candidates 가 있으면 prepare 단계에서 제외된 자연어형 보안 검색 질의 검토 정보로만 사용하라. "
        "probing_sequence_summaries 가 있으면 이는 context-only 이며 개별 incident 로 승격하지 말고, 같은 src_ip 에서 짧은 시간 안에 여러 민감/관리/백업 경로에 접근한 reconnaissance 또는 directory probing 흐름으로만 설명하라. "
        "probing_sequence_summaries 의 200 text/html 반복 응답과 동일 response_body_bytes 반복은 fallback HTML 가능성으로만 설명하고, .env/.git/config/admin page/backup file 노출 성공으로 단정하지 마라. "
        "probing_sequence_summaries 안의 403, 401 같은 차단 응답은 access control 이 동작한 정황으로 설명하되 scan/probe intent 는 남길 수 있다. "
        "static_baseline_summaries 가 있으면 이는 context-only 이며 개별 incident 로 승격하지 말고, 같은 src_ip 와 짧은 시간 window 안에서 favicon, robots.txt, sitemap.xml, static asset, health check, normal GET 이 함께 관찰된 baseline/static context 로만 설명하라. "
        "static_baseline_summaries 의 should_promote_to_candidate=false 이면 어떤 개별 row 도 이 summary 때문에 analysis_candidate 로 승격된 것으로 해석하지 마라. "
        "static_baseline_summaries 의 status_code=200/404/500, response_body_bytes, content_type 만으로 static file 존재, crawler policy 내용, site structure 노출, JS 실행, file exposure, health 정상 여부를 단정하지 마라. "
        "Apache 로그 표면에서는 response body 원문, 브라우저 실행 여부, 서버 내부 파일 존재 여부를 확인할 수 없으므로 static_baseline_summaries 는 관찰 문맥으로만 해석하라. "
        "crawler_baseline_summaries 가 있으면 이는 context-only 이며 개별 incident 나 analysis_candidate 로 승격하지 말고, 같은 src_ip 와 짧은 시간 window 안에서 crawler-like User-Agent, robots.txt, sitemap.xml, product/category browse, normal browse 가 함께 관찰된 crawler baseline context 로만 설명하라. "
        "crawler_baseline_summaries 의 should_promote_to_candidate=false 이면 어떤 개별 row 도 이 summary 때문에 analysis_candidate 로 승격된 것으로 해석하지 마라. "
        "Googlebot/Bingbot/GenericCrawler-like User-Agent 는 spoof 가능하므로 실제 crawler 정체를 단정하지 마라. "
        "crawler_baseline_summaries 의 status_code=200/404/500, response_body_bytes, content_type 만으로 robots policy 내용, sitemap 내용, site structure, product/category page existence, 공격 성공을 단정하지 마라. "
        "Apache 로그 표면에서는 response body 원문, crawler verification, 서버 내부 page 존재 여부를 확인할 수 없으므로 crawler_baseline_summaries 는 관찰 문맥으로만 해석하라. "
        "sensitive_path_probe_summaries 가 있으면 이는 context-only 이며 개별 incident 나 analysis_candidate 로 승격하지 말고, 같은 src_ip 와 짧은 시간 window 안에서 wp-login/wp-admin/.env/phpinfo/server-status/backup.zip 같은 path 가 관찰된 scanner-like sensitive path probing context 로만 설명하라. "
        "sensitive_path_probe_summaries 의 should_promote_to_candidate=false 이면 어떤 개별 row 도 이 summary 때문에 analysis_candidate 로 승격된 것으로 해석하지 마라. "
        "sensitive_path_probe_summaries 의 status_code=200/403/404/500, response_body_bytes, content_type 만으로 WordPress 존재, admin access, .env 노출, phpinfo 노출, server-status 노출/차단, backup 노출, 공격 성공을 단정하지 마라. "
        "Apache 로그 표면에서는 response body 원문, 서버 내부 파일 존재 여부, 애플리케이션 종류를 확인할 수 없으므로 sensitive_path_probe_summaries 는 관찰 문맥으로만 해석하라. "
        "mixed_baseline_scanner_summaries 가 있으면 이는 context-only 이며 개별 incident 나 analysis_candidate 로 승격하지 말고, 같은 src_ip 와 짧은 시간 window 안에서 baseline/static/crawler-like 요청과 scanner-like sensitive path 가 함께 관찰된 mixed context 로만 설명하라. "
        "mixed_baseline_scanner_summaries 의 should_promote_to_candidate=false 이면 어떤 개별 row 도 이 summary 때문에 analysis_candidate 로 승격된 것으로 해석하지 마라. "
        "mixed_baseline_scanner_summaries 는 baseline/static/crawler-like context 와 sensitive path probe context 를 같은 성공 공격이나 단일 침해 체인으로 합치지 않고 분리해서 설명하라. "
        "mixed_baseline_scanner_summaries 의 status_code=200/403/404/500, response_body_bytes, content_type 만으로 file exposure, app presence, crawler authenticity, page existence, 공격 성공을 단정하지 마라. "
        "Apache 로그 표면에서는 response body 원문, crawler verification, 서버 내부 파일 존재 여부를 확인할 수 없으므로 mixed_baseline_scanner_summaries 는 관찰 문맥으로만 해석하라. "
        "static_baseline_summaries, crawler_baseline_summaries, sensitive_path_probe_summaries, mixed_baseline_scanner_summaries, auth_behavior_summaries, method_behavior_summaries, protocol_anomaly_summaries, ip_behavior_aggregates 를 함께 언급할 때는 count scope 를 분리하라. "
        "static_baseline_summaries 의 request_count 는 같은 src_ip 와 static/health/browse baseline 시간창 기준 관찰 수이고, crawler_baseline_summaries 의 request_count 는 같은 src_ip 와 crawler-like UA/browse baseline 시간창 기준 관찰 수이며, sensitive_path_probe_summaries 의 request_count 는 같은 src_ip 와 sensitive path 시간창 기준 관찰 수이며, mixed_baseline_scanner_summaries 의 request_count 는 같은 src_ip 와 mixed baseline/scanner 시간창 기준 관찰 수이며, auth_behavior_summaries 의 request_count/auth_request_count 는 auth endpoint family 기준 auth 요청 수이며, method_behavior_summaries 의 request_count 는 같은 src_ip 와 method/protocol relevant row 시간창 기준 관찰 수이며, protocol_anomaly_summaries 의 request_count 는 같은 src_ip 와 protocol anomaly relevant row 시간창 기준 관찰 수이고, ip_behavior_aggregates 의 request_count 는 같은 src_ip/time window 기준 전체 또는 관련 요청 수다. "
        "여덟 count 를 48~51건 규모 같은 range 로 합치거나 같은 사건 수처럼 직접 합산하지 마라. "
        "여덟 collection 모두 context-only 이며 candidate 승격 근거가 아니다. "
        "ip_behavior_aggregates 가 있으면 이는 context-only 이며 개별 incident 로 승격하지 말고, 같은 src_ip 에서 짧은 시간 안에 여러 경로 접근, 높은 4xx 비율, 다중 attempted category, 민감 경로 접근이 함께 관찰된 reconnaissance 또는 scanning-like context 로만 설명하라. "
        "ip_behavior_aggregates 의 should_promote_to_candidate=false 이면 어떤 개별 row 도 이 aggregate 때문에 analysis_candidate 로 승격된 것으로 해석하지 마라. "
        "ip_behavior_aggregates 의 attack_categories_attempted 는 시도 유형 요약이지 성공한 공격 유형 목록이 아니며, sensitive_path_hits 는 민감 경로 접근 문맥일 뿐 실제 파일 노출 근거가 아니다. "
        "ip_behavior_aggregates 의 status_code=200, text/html, response_body_bytes, status_5xx_count 만으로 공격 성공, 침해 성공, 파일 노출, XSS 실행, DB 유출을 단정하지 마라. "
        "ip_behavior_aggregates 가 있어도 동일 src_ip 를 공격자라고 단정하지 말고, same src_ip observed with scanning-like behavior 정도의 보수적 표현만 사용하라. "
        "auth_behavior_summaries 가 있으면 이는 context-only 이며 개별 incident 로 승격하지 말고, 같은 src_ip 와 auth endpoint family 에서 짧은 시간 안에 반복 401, rapid burst, 401/200 혼재, 단독 200 baseline 이 관찰된 auth behavior context 로만 설명하라. "
        "auth_behavior_summaries 의 401 과 200 혼재는 HTTP 200 observed after repeated 401 정도로만 설명하고, 로그인 성공 confirmed, 계정 탈취 confirmed, credential stuffing 성공으로 단정하지 마라. "
        "Apache 로그 표면에서는 raw POST body, DB 인증 결과, response body 원문이 보이지 않을 수 있으므로 auth_behavior_summaries 는 POST body 미확인 상태로 해석하라. "
        "auth_behavior_summaries 의 status_code=200, response_body_bytes, resp_content_type 만으로 인증 성공이나 침해 성공 근거로 사용하지 마라. "
        "method_behavior_summaries 가 있으면 이는 context-only 이며 개별 incident 로 승격하지 말고, 같은 src_ip 와 짧은 시간 window 안에서 OPTIONS, TRACE, PUT, DELETE, PATCH 같은 risky method 와 HEAD, GET baseline method 가 함께 관찰된 method probing 또는 baseline context 로만 설명하라. "
        "method_behavior_summaries 의 should_promote_to_candidate=false 이면 어떤 개별 method row 도 이 summary 때문에 analysis_candidate 로 승격된 것으로 해석하지 마라. "
        "method_behavior_summaries 의 status_counts, response_body_bytes, status_code=200/201/204 만으로 method 허용, 업로드 성공, 삭제 성공, XST 성공, CORS 취약점을 단정하지 마라. "
        "TRACE 는 TRACE method probing 또는 exposure 확인 시도 정도로만 설명하고 XST 성공을 단정하지 마라. PUT 은 write/upload probing 정도로만 설명하고 업로드 성공을 단정하지 마라. DELETE 는 destructive method probing 정도로만 설명하고 리소스 삭제 성공을 단정하지 마라. OPTIONS 는 method discovery 또는 probing 정도로만 설명하고 CORS 취약점이나 method exposure 성공을 단정하지 마라. "
        "HEAD 와 GET 은 method baseline 또는 reference context 로만 설명하고 공격 성공 근거로 사용하지 마라. "
        "protocol_anomaly_summaries 가 있으면 이는 context-only 이며 개별 incident 로 승격하지 말고, 같은 src_ip 와 짧은 시간 window 안에서 invalid method, HTTP/1.0, bad protocol version, missing/odd Host, long path 가 관찰된 request parsing/protocol surface context 로만 설명하라. "
        "protocol_anomaly_summaries 의 should_promote_to_candidate=false 이면 어떤 개별 row 도 이 summary 때문에 analysis_candidate 로 승격된 것으로 해석하지 마라. "
        "protocol_anomaly_summaries 의 status_code=200/400/405/408/414/500/501/505, response_body_bytes, status_counts 만으로 protocol bypass 성공, exploit success, compromise success, virtual host bypass 성공을 단정하지 마라. "
        "bad protocol version, missing Host, odd Host, invalid method 는 malformed/parsing/protocol 관찰 문맥으로만 설명하고 우회 성공이나 침해 성공으로 단정하지 마라. "
        "Apache 로그 표면에서는 response body 원문, request body 원문, 서버 내부 상태를 확인할 수 없으므로 protocol anomaly outcome 은 시도/관찰 문맥으로만 해석하라. "
        "User-Agent 값은 raw evidence 로 인용할 수 있지만 lab-* 같은 실험 prefix 자체를 탐지 근거로 삼지 마라. "
        "User-Agent 해석은 비브라우저성 UA, 반복적 UA 패턴, 자동화 또는 테스트성 UA 가능성처럼 일반화하고, known_asset IP 와 결합되면 내부 테스트 또는 운영 점검 가능성을 함께 언급하라. "
        "low_signal_fuzzing 과 low_signal_dir_probe 는 기본적으로 incident 로 승격하지 말고, stage2 에서는 '후보 밖 탐색성 요청'으로 고정 표기하라. "
        "단, 동일 IP, 동일 시간대, 후속 고신호 incident 와 결합될 때만 승격 검토 대상으로 서술하라. "
        "filtered_out_breakdown, top_filtered_categories, top_out_of_candidate_recon 은 prepare 단계에서 보존된 사실 정보이므로 후보 밖 문맥 섹션과 recommended_actions 에 반영하라. "
        "반드시 schema-valid JSON 객체만 반환하라. "
        "자유서술 필드는 모두 한국어로 작성하라."
    )

    user_payload = {
        "report_goal": {
            "target": "Markdown 보고서로 바로 사용할 수 있는 간결한 보안 분석 요약 생성",
            "audience": "프로젝트 팀과 발표 검토자",
            "style": "명확하고, 근거 중심이며, 신중한 서술",
            "output_language": "한국어",
        },
        "instructions": [
            "제공된 분포와 상위 incident 를 사용해 분석 시간 구간을 설명하라.",
            "수상한 패턴, 주목할 IP, 즉시 필요한 조치에 집중하라.",
            "likely_false_positive 와 inconclusive 는 특히 조심해서 해석하라.",
            "제공된 근거가 강하지 않으면 성공적인 침해나 악용 성공을 단정하지 마라.",
            "Apache 로그에는 raw POST body 원문이 없을 수 있으므로 body 내부 payload 성공/실패를 본 것처럼 단정하지 마라.",
            "path traversal 은 raw_request_target, uri, resp_content_type, response_body_bytes, likely_html_fallback_response 를 함께 보고 시도와 실제 노출 가능성을 구분하라.",
            "php://filter/convert.base64-encode/resource=... 구조는 PHP stream wrapper 를 통해 대상 파일을 base64 인코딩된 형태로 읽도록 유도하는 source/config disclosure attempt 또는 LFI-like file disclosure attempt 로 설명하라.",
            "이는 단순 ../ path traversal 과 구분되는 PHP wrapper 기반 file disclosure 시도다.",
            "file_disclosure:* reason_hints 는 의도/시도 근거이지 성공/유출 근거가 아니다.",
            "suspicious_file_disclosure verdict 가 있으면 PHP wrapper 기반 source/config disclosure 시도 의미를 우선 설명하라.",
            "그러나 Apache 로그만으로 실제 PHP source/config 파일 내용 노출 성공은 확정하지 마라.",
            "status_code=200, text/html, response_body_bytes 또는 response_body_bytes=0 만으로 file disclosure 성공 근거로 사용하지 마라.",
            "/config.php, /admin/config.php 가 200 이어도 response body 원문이 없으면 config 노출 성공으로 단정하지 마라.",
            "response_body_bytes=0 인 경우에는 직접 접근은 되었으나 응답 본문은 비어 있거나 로그상 본문 노출 증거가 없다고 표현하라.",
            "php://filter candidate 와 direct config path probe 는 구분해서 설명하라. 전자는 PHP wrapper 기반 file/source disclosure attempt, 후자는 sensitive config path probing context 다.",
            "resp_content_type 이 text/html 이고 likely_html_fallback_response 가 true 면 앱 fallback HTML 가능성을 우선 검토하라.",
            "Apache 로그만으로 XSS payload 의 브라우저 실행 성공을 확정하지 마라.",
            "500 text/html 은 처리 오류 정황일 수 있지만 XSS 실행 성공 근거로 단정하지 마라.",
            "200 application/json 은 브라우저 실행 성공 근거로 사용하지 마라.",
            "document.cookie, localStorage, sessionStorage 문자열은 브라우저 데이터 접근 의도 또는 탈취 시도로만 서술하고 실제 탈취 성공으로 단정하지 마라.",
            "외부 URL, fetch, location 변경, Image beacon 정황이 있어도 별도 네트워크나 앱 증거 없이는 외부 전송 성공을 확정하지 마라.",
            "encoding:html_entity_payload, encoding:html_entity_decoded_xss, encoding:url_encoded_payload, encoding:double_decoded_payload 는 우회 또는 복원 관점에서만 언급하라.",
            "hpp_detected 가 true 인 incident 는 hpp_param_names 와 embedded_attack_hint 를 함께 보고, 중복 파라미터(HPP)를 통한 공격 시도인지 서술하라.",
            "known_asset_ips 와 일치하는 IP 는 내부 테스트/자체 호출 가능성을 반드시 함께 언급하라.",
            "noise_summary 가 비어 있어도 filtered_out_breakdown 이 있으면 후보 밖 세부 분포가 존재하는 것으로 서술하라.",
            "supporting_events 는 개별 incident 로 승격하지 말고, 같은 src_ip 와 같은 uri 또는 endpoint family 의 temporal chain 보조 문맥으로만 사용하라.",
            "supporting_role=reference_baseline 또는 supporting_reason=nearby_normal_search_baseline 인 supporting_events 는 후보 밖 탐색성 요청으로 쓰지 말고, 같은 endpoint 의 정상 baseline 또는 reference baseline 으로 설명하라.",
            "supporting_role=auth_behavior_support 또는 supporting_reason=covered_by_auth_behavior_summary 인 supporting_events 는 반복 auth 실패 row 가 auth_behavior_summaries 에 의해 대표 사건 밖 문맥으로 정리된 것으로 설명하고 각 row 를 별도 incident 로 재승격하지 마라.",
            "supporting_events 에 educational_sql_search 또는 sql_keyword_without_attack_structure 계열 hint 가 있으면 SQL 키워드 검색을 공격으로 단정하지 마라.",
            "supporting_events 나 incident reason_hints 에 encoding:double_decoded_sqli, encoding:decoded_depth_2 같은 hint 가 있으면 인코딩 기반 evasion 시도 가능성을 보조적으로 언급하라.",
            "false_positive_review_candidates 는 prepare 단계에서 제외된 자연어형 보안 검색 질의 검토용 정보로만 사용하고 incident 로 승격하지 마라.",
            "probing_sequence_summaries 는 context-only 이며 개별 incident 로 승격하지 말고, 같은 src_ip, 짧은 시간 window, 여러 민감/관리/백업 경로 접근이 관찰된 reconnaissance 또는 directory probing 흐름으로만 설명하라.",
            "probing_sequence_summaries 에서 200 text/html 반복 응답이나 동일 response_body_bytes 반복은 fallback HTML 가능성으로만 설명하고 실제 민감 리소스 노출 성공으로 단정하지 마라.",
            "probing_sequence_summaries 안의 direct config path 접근은 context_only 이며 개별 incident 나 config 노출 성공으로 과승격하지 마라.",
            "probing_sequence_summaries 에 403 또는 401 응답이 있으면 access control 이 동작한 정황으로 설명하되 scan/probe intent 는 보조적으로 언급하라.",
            "known_asset 이거나 known asset IP 와 겹치는 probing_sequence_summaries 는 내부 테스트/운영 점검 가능성을 함께 병기하라.",
            "static_baseline_summaries 는 context-only 이며 개별 incident 로 승격하지 말고, 같은 src_ip 와 짧은 시간 window 안에서 favicon, robots.txt, sitemap.xml, static asset, health check, normal GET 이 함께 관찰된 baseline/static context 로만 설명하라.",
            "static_baseline_summaries 의 should_promote_to_candidate=false 이면 어떤 개별 row 도 이 summary 때문에 candidate 로 승격된 것으로 해석하지 마라.",
            "static_baseline_summaries 의 status_code, response_body_bytes, content_type 만으로 static file 존재, crawler policy 내용, site structure 노출, JS 실행, file exposure, health 정상 여부를 단정하지 마라.",
            "Apache 로그 표면에서는 response body 원문, 브라우저 실행 여부, 서버 내부 파일 존재 여부를 확인할 수 없으므로 static_baseline_summaries 는 관찰 문맥으로만 해석하라.",
            "crawler_baseline_summaries 는 context-only 이며 개별 incident 나 analysis_candidate 로 승격하지 말고, 같은 src_ip 와 짧은 시간 window 안에서 crawler-like User-Agent, robots.txt, sitemap.xml, product/category browse, normal browse 가 함께 관찰된 crawler baseline context 로만 설명하라.",
            "crawler_baseline_summaries 의 should_promote_to_candidate=false 이면 어떤 개별 row 도 이 summary 때문에 candidate 로 승격된 것으로 해석하지 마라.",
            "Googlebot/Bingbot/GenericCrawler-like User-Agent 는 spoof 가능하므로 실제 crawler 정체를 단정하지 마라.",
            "crawler_baseline_summaries 의 status_code, response_body_bytes, content_type 만으로 robots policy 내용, sitemap 내용, site structure, product/category page existence, 공격 성공을 단정하지 마라.",
            "Apache 로그 표면에서는 response body 원문, crawler verification, 서버 내부 page 존재 여부를 확인할 수 없으므로 crawler_baseline_summaries 는 관찰 문맥으로만 해석하라.",
            "mixed_baseline_scanner_summaries 는 context-only 이며 개별 incident 나 analysis_candidate 로 승격하지 말고, 같은 src_ip 와 짧은 시간 window 안에서 baseline/static/crawler-like 요청과 scanner-like sensitive path 가 함께 관찰된 mixed context 로만 설명하라.",
            "mixed_baseline_scanner_summaries 의 should_promote_to_candidate=false 이면 어떤 개별 row 도 이 summary 때문에 candidate 로 승격된 것으로 해석하지 마라.",
            "mixed_baseline_scanner_summaries 는 baseline/static/crawler-like context 와 sensitive path probe context 를 같은 성공 공격이나 단일 침해 체인으로 합치지 말고 분리해서 설명하라.",
            "mixed_baseline_scanner_summaries 의 status_code, response_body_bytes, content_type 만으로 file exposure, app presence, crawler authenticity, page existence, 공격 성공을 단정하지 마라.",
            "Apache 로그 표면에서는 response body 원문, crawler verification, 서버 내부 파일 존재 여부를 확인할 수 없으므로 mixed_baseline_scanner_summaries 는 관찰 문맥으로만 해석하라.",
            "static_baseline_summaries, crawler_baseline_summaries, sensitive_path_probe_summaries, mixed_baseline_scanner_summaries, auth_behavior_summaries, method_behavior_summaries, protocol_anomaly_summaries, ip_behavior_aggregates 를 함께 언급할 때는 count scope 를 분리하라.",
            "static_baseline_summaries 의 request_count 는 같은 src_ip 와 static/health/browse baseline 시간창 기준 관찰 수이고, crawler_baseline_summaries 의 request_count 는 같은 src_ip 와 crawler-like UA/browse baseline 시간창 기준 관찰 수이며, sensitive_path_probe_summaries 의 request_count 는 같은 src_ip 와 sensitive path 시간창 기준 관찰 수이며, mixed_baseline_scanner_summaries 의 request_count 는 같은 src_ip 와 mixed baseline/scanner 시간창 기준 관찰 수이며, auth_behavior_summaries 의 request_count/auth_request_count 는 auth endpoint family 기준 auth 요청 수이며, method_behavior_summaries 의 request_count 는 같은 src_ip 와 method/protocol relevant row 시간창 기준 관찰 수이며, protocol_anomaly_summaries 의 request_count 는 같은 src_ip 와 protocol anomaly relevant row 시간창 기준 관찰 수이고, ip_behavior_aggregates 의 request_count 는 같은 src_ip/time window 기준 전체 또는 관련 요청 수다.",
            "여덟 count 를 48~51건 같은 range 로 합치거나 같은 사건 수처럼 직접 합산하지 마라.",
            "static_baseline_summaries, crawler_baseline_summaries, sensitive_path_probe_summaries, mixed_baseline_scanner_summaries, auth_behavior_summaries, method_behavior_summaries, protocol_anomaly_summaries, ip_behavior_aggregates 는 모두 context-only 이며 candidate 승격 근거가 아니다.",
            "ip_behavior_aggregates 는 context-only 이며 개별 incident 로 승격하지 말고, 같은 src_ip, 짧은 시간 window, 여러 path 접근, 높은 4xx 비율, attempted category 혼합이 관찰된 reconnaissance/scanning-like context 로만 설명하라.",
            "ip_behavior_aggregates 의 should_promote_to_candidate=false 이면 어떤 개별 row 도 이 aggregate 때문에 candidate 로 승격된 것으로 해석하지 마라.",
            "ip_behavior_aggregates 의 attack_categories_attempted 는 시도 유형 요약일 뿐 성공한 공격 유형 목록이 아니다.",
            "ip_behavior_aggregates 의 sensitive_path_hits 는 민감 경로 접근 시도 문맥일 뿐 실제 파일 노출 근거가 아니다.",
            "ip_behavior_aggregates 에 200 응답, text/html, response_body_bytes, 5xx count 가 있어도 공격 성공이나 침해 성공 근거로 사용하지 마라.",
            "ip_behavior_aggregates 가 있어도 동일 src_ip 를 공격자라고 단정하지 말고, same src_ip observed with scanning-like behavior 정도로만 표현하라.",
            "auth_behavior_summaries 는 context-only 이며 개별 incident 로 승격하지 말고, 같은 src_ip 와 auth endpoint family, 짧은 시간 window 안의 반복 401, rapid burst, 401/200 혼재, 단독 200 baseline 을 auth behavior context 로만 설명하라.",
            "auth_behavior_summaries 의 should_promote_to_candidate=false 이면 어떤 개별 auth row 도 이 summary 때문에 candidate 로 승격된 것으로 해석하지 마라.",
            "auth_behavior_summaries 의 401 과 200 혼재는 HTTP 200 observed after repeated 401 정도로만 설명하고 로그인 성공 confirmed, 계정 탈취, credential stuffing 성공으로 단정하지 마라.",
            "Apache 로그 표면에서는 raw POST body 와 인증 결과 원문이 보이지 않을 수 있으므로 auth_behavior_summaries 는 POST body 미확인 상태로 해석하라.",
            "auth_behavior_summaries 에 200 응답, response_body_bytes, application/json 같은 값이 있어도 인증 성공이나 침해 성공 근거로 사용하지 마라.",
            "method_behavior_summaries 는 context-only 이며 개별 incident 로 승격하지 말고, 같은 src_ip 와 짧은 시간 window 안에서 risky method 와 baseline method 가 함께 관찰된 method probing 또는 baseline context 로만 설명하라.",
            "method_behavior_summaries 의 should_promote_to_candidate=false 이면 어떤 개별 method row 도 이 summary 때문에 candidate 로 승격된 것으로 해석하지 마라.",
            "method_behavior_summaries 의 status_counts, response_body_bytes, status_code=200/201/204 만으로 method 허용, 업로드 성공, 삭제 성공, XST 성공, CORS 취약점을 단정하지 마라.",
            "TRACE 는 XST 성공이 아니라 TRACE probing 정도로만, PUT 은 업로드 성공이 아니라 write/upload probing 정도로만, DELETE 는 삭제 성공이 아니라 destructive method probing 정도로만, OPTIONS 는 CORS 취약점이 아니라 method discovery/probing 정도로만 설명하라.",
            "HEAD 와 GET 은 method baseline 또는 reference context 로만 설명하고 공격 성공 근거로 사용하지 마라.",
            "protocol_anomaly_summaries 는 context-only 이며 개별 incident 로 승격하지 말고, 같은 src_ip 와 짧은 시간 window 안에서 invalid method, HTTP/1.0, bad protocol version, missing/odd Host, long path 가 관찰된 request parsing/protocol surface context 로만 설명하라.",
            "protocol_anomaly_summaries 의 should_promote_to_candidate=false 이면 어떤 개별 row 도 이 summary 때문에 candidate 로 승격된 것으로 해석하지 마라.",
            "protocol_anomaly_summaries 의 status_code=200/400/405/408/414/500/501/505, response_body_bytes, status_counts 만으로 protocol bypass 성공, exploit success, compromise success, virtual host bypass 성공을 단정하지 마라.",
            "bad protocol version, missing Host, odd Host, invalid method 는 malformed/parsing/protocol 관찰 문맥으로만 설명하고 우회 성공이나 침해 성공으로 단정하지 마라.",
            "Apache 로그 표면에서는 response body 원문, request body 원문, 서버 내부 상태를 확인할 수 없으므로 protocol anomaly outcome 은 시도/관찰 문맥으로만 해석하라.",
            "User-Agent 값은 raw evidence 로 표시할 수 있지만 lab-* 같은 실험 prefix 자체를 공격 근거로 삼지 마라.",
            "User-Agent 해석은 비브라우저성 UA, 반복적 UA 패턴, 자동화 또는 테스트성 UA 가능성처럼 일반화하라.",
            "known_asset IP 와 결합된 비브라우저성 또는 자동화성 UA 는 내부 테스트 또는 운영 점검 가능성을 함께 병기하라.",
            "low_signal_fuzzing 과 low_signal_dir_probe 는 기본적으로 incident 로 승격하지 말고, 별도 '후보 밖 탐색성 요청' 섹션에서 설명하라.",
            "동일 IP, 동일 시간대, 후속 고신호 incident 와 결합될 때만 승격 검토 대상으로 서술하라.",
            "benign_normal_search 또는 normal_search_baseline filtered_out category 는 low_signal_fuzzing 과 분리해서 정상 비교군 또는 reference baseline 으로 설명하라.",
            "정상 baseline 이 근접해 있어도 공격 candidate 의 의도나 심각도를 낮추는 근거로 사용하지 마라.",
            "low_signal_fuzzing, low_signal_dir_probe, benign_normal_search, benign_fallback_html 같은 filtered_out_breakdown 카테고리가 있으면 noise_interpretation 에 구체적으로 반영하라.",
            "executive_summary 는 짧고 발표용으로 읽기 쉽게 작성하라.",
            "recommended_actions 는 구체적이고 운영 가능한 형태로 제시하라.",
            "notable_incidents 의 incident_ref 는 report_input.top_incidents 에 있는 값을 그대로 복사하라.",
            "report_title, overall_assessment, executive_summary, key_findings.title, key_findings.detail, notable_incidents.why_it_matters, notable_source_ips.reason, noise_interpretation, recommended_actions.action, recommended_actions.why, confidence_and_limitations, presentation_takeaway 는 모두 한국어로 작성하라.",
        ],
        "report_input": report_input,
    }

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]


def render_markdown(report_json: Dict[str, Any], report_input: Dict[str, Any], selected_model: str, mode: str) -> str:
    ctx = report_input.get("analysis_context") or {}
    counts = report_input.get("pipeline_counts") or {}
    distributions = report_input.get("distributions") or {}
    top_incidents = report_input.get("top_incidents") or []
    top_filtered_categories = report_input.get("top_filtered_categories") or []
    top_out_of_candidate_recon = report_input.get("top_out_of_candidate_recon") or []
    probing_sequence_summaries = report_input.get("probing_sequence_summaries") or []
    static_baseline_summaries = report_input.get("static_baseline_summaries") or []
    crawler_baseline_summaries = report_input.get("crawler_baseline_summaries") or []
    sensitive_path_probe_summaries = report_input.get("sensitive_path_probe_summaries") or []
    mixed_baseline_scanner_summaries = report_input.get("mixed_baseline_scanner_summaries") or []
    ip_behavior_aggregates = report_input.get("ip_behavior_aggregates") or []
    auth_behavior_summaries = report_input.get("auth_behavior_summaries") or []
    method_behavior_summaries = report_input.get("method_behavior_summaries") or []
    protocol_anomaly_summaries = report_input.get("protocol_anomaly_summaries") or []
    verdicts = distributions.get("verdicts") or {}
    severities = distributions.get("severities") or {}
    source_tables = distributions.get("source_tables") or {}
    filtered_out_breakdown = distributions.get("filtered_out_breakdown") or {}
    asset_context = report_input.get("asset_context") or {}
    behavior_scope_note = build_behavior_scope_note(ip_behavior_aggregates, auth_behavior_summaries)

    lines: List[str] = []
    lines.append(f"# {normalize_str(report_json.get('report_title'))}")
    lines.append("")
    lines.append(f"- 생성 시각: {iso_now()}")
    lines.append(f"- 분석 모드: {mode}")
    lines.append(f"- 사용 모델: {selected_model}")
    lines.append(f"- 분석 시간대: {normalize_str(ctx.get('query_timezone')) or 'Asia/Seoul'}")
    window = ctx.get("window") or {}
    lines.append(f"- 분석 구간: {normalize_str(window.get('start')) or '-'} ~ {normalize_str(window.get('end_exclusive')) or '-'}")
    if asset_context.get("known_asset_ips"):
        lines.append(f"- known asset IP: {', '.join(asset_context.get('known_asset_ips') or [])}")
    lines.append("")

    lines.append("## 1. 전체 평가")
    lines.append(normalize_str(report_json.get("overall_assessment")))
    lines.append("")

    lines.append("## 2. 경영 요약")
    for item in report_json.get("executive_summary") or []:
        lines.append(f"- {normalize_str(item)}")
    lines.append("")

    lines.append("## 3. 파이프라인 요약")
    lines.append(f"- 전체 export row 수: {safe_int(counts.get('total_exported_rows'), 0)}")
    lines.append(f"- 1차 후보 row 수: {safe_int(counts.get('candidate_rows'), 0)}")
    lines.append(f"- distinct incident 수: {safe_int(counts.get('distinct_incident_count'), 0)}")
    lines.append(f"- filtered out row 수: {safe_int(counts.get('filtered_out_rows'), 0)}")
    lines.append(f"- filtered out 비집계 row 수: {safe_int(counts.get('filtered_out_non_aggregated_rows'), 0)}")
    lines.append(f"- noise 집계 그룹 수: {safe_int(counts.get('noise_group_count'), 0)}")
    lines.append(f"- static baseline summary 수: {safe_int(counts.get('static_baseline_summary_count'), len(static_baseline_summaries))}")
    lines.append(f"- crawler baseline summary 수: {safe_int(counts.get('crawler_baseline_summary_count'), len(crawler_baseline_summaries))}")
    lines.append(f"- sensitive path probe summary 수: {safe_int(counts.get('sensitive_path_probe_summary_count'), len(sensitive_path_probe_summaries))}")
    lines.append(f"- mixed baseline/scanner summary 수: {safe_int(counts.get('mixed_baseline_scanner_summary_count'), len(mixed_baseline_scanner_summaries))}")
    lines.append(f"- ip behavior aggregate 수: {safe_int(counts.get('ip_behavior_aggregate_count'), len(ip_behavior_aggregates))}")
    lines.append(f"- auth behavior summary 수: {safe_int(counts.get('auth_behavior_summary_count'), len(auth_behavior_summaries))}")
    lines.append(f"- method behavior summary 수: {safe_int(counts.get('method_behavior_summary_count'), len(method_behavior_summaries))}")
    lines.append(f"- protocol anomaly summary 수: {safe_int(counts.get('protocol_anomaly_summary_count'), len(protocol_anomaly_summaries))}")
    lines.append(f"- stage1 성공/오류: {safe_int(counts.get('stage1_success_count'), 0)} / {safe_int(counts.get('stage1_error_count'), 0)}")
    if verdicts:
        lines.append(f"- verdict 분포: {json.dumps(verdicts, ensure_ascii=False)}")
    if severities:
        lines.append(f"- severity 분포: {json.dumps(severities, ensure_ascii=False)}")
    if source_tables:
        lines.append(f"- 대표 source table 분포: {json.dumps(source_tables, ensure_ascii=False)}")
    if filtered_out_breakdown:
        lines.append(f"- filtered_out 세부 분포: {json.dumps(filtered_out_breakdown, ensure_ascii=False)}")
    if top_filtered_categories:
        top_filtered_text = ", ".join(
            f"{normalize_str(x.get('category'))} {safe_int(x.get('count'), 0)}건 ({x.get('share_pct', 0)}%)"
            for x in top_filtered_categories
        )
        lines.append(f"- 후보 밖 주요 카테고리: {top_filtered_text}")
    lines.append("")

    lines.append("## 4. 핵심 발견")
    for finding in report_json.get("key_findings") or []:
        title = normalize_str(finding.get("title"))
        detail = normalize_str(finding.get("detail"))
        severity = normalize_str(finding.get("severity"))
        lines.append(f"- **{title}** [{severity}] - {detail}")
    lines.append("")

    lines.append("## 5. 주목할 사건")
    incident_lookup = {normalize_str(x.get("incident_ref")): x for x in top_incidents}
    for item in report_json.get("notable_incidents") or []:
        incident_ref = normalize_str(item.get("incident_ref"))
        req_id = normalize_str(item.get("request_id"))
        ref = incident_lookup.get(incident_ref, {})
        lines.append(
            f"- request_id={req_id or '-'} | src_ip={normalize_str(item.get('src_ip')) or '-'} | "
            f"verdict={normalize_str(item.get('verdict'))} | severity={normalize_str(item.get('severity'))}"
        )
        lines.append(f"  - 이유: {normalize_str(item.get('why_it_matters'))}")
        if ref:
            lines.append(
                f"  - uri={normalize_str(ref.get('uri')) or '-'} | method={normalize_str(ref.get('method')) or '-'} | "
                f"status={safe_int(ref.get('status_code'), 0)} | score={safe_int(ref.get('score'), 0)} | "
                f"log_time={normalize_str(ref.get('log_time')) or '-'}"
            )
            duplicate_count = safe_int(ref.get("duplicate_count"), 1)
            source_tables_text = ",".join(ref.get("source_tables") or []) or normalize_str(ref.get("source_table")) or "-"
            lines.append(f"  - incident_ref={incident_ref or '-'} | merged_rows={duplicate_count} | source_tables={source_tables_text}")
            if bool(ref.get("known_asset")):
                lines.append("  - 주의: 이 출발지 IP 는 known asset 목록과 일치하므로 내부 테스트/자체 호출 가능성을 함께 고려해야 합니다.")
            reasoning = normalize_str(ref.get("reasoning_summary"))
            if reasoning:
                lines.append(f"  - stage1 요약: {reasoning}")
            if has_php_wrapper_file_disclosure_context(ref):
                lines.append(
                    "  - file disclosure 해석: php://filter/convert.base64-encode/resource=... 계열은 PHP stream wrapper 를 이용한 source/config disclosure attempt 또는 LFI-like file disclosure attempt 로 해석할 수 있습니다."
                )
                lines.append(
                    "  - 해석 제한: Apache 로그만으로 실제 파일 내용 반환 여부는 확인할 수 없으므로, 성공한 유출이 아니라 시도 정황으로만 제한해 해석해야 합니다."
                )
        elif incident_ref:
            lines.append(f"  - incident_ref={incident_ref}")
    lines.append("")

    lines.append("## 6. 주목할 출발지 IP")
    for item in report_json.get("notable_source_ips") or []:
        lines.append(f"- {normalize_str(item.get('src_ip'))}: {normalize_str(item.get('reason'))}")
    matched_known_assets = asset_context.get("matched_known_assets") or []
    if matched_known_assets:
        lines.append("")
        lines.append("참고: 위 출발지 IP 중 일부는 known asset 목록과 일치하므로, 실제 공격자 IP 로 단정하지 말고 내부 테스트/자체 호출 여부를 먼저 확인해야 합니다.")
    lines.append("")

    lines.append("## 7. 후보 밖 문맥 요청")
    lines.append(normalize_str(report_json.get("noise_interpretation")))
    lines.append("")
    lines.append("정책:")
    lines.append("- low_signal_fuzzing / low_signal_dir_probe 는 기본적으로 incident 로 승격하지 않습니다.")
    lines.append("- low_signal_fuzzing / low_signal_dir_probe 만 후보 밖 탐색성 요청으로 고정 표기합니다.")
    lines.append("- benign_normal_search / normal_search_baseline 과 supporting_role=reference_baseline 은 정상 baseline 또는 reference baseline 으로 설명합니다.")
    lines.append("- 동일 IP·동일 시간대·후속 고신호 incident 와 결합될 때만 승격 검토합니다.")
    if top_out_of_candidate_recon:
        lines.append("")
        lines.append("후보 밖 탐색성 요청 분포:")
        for row in top_out_of_candidate_recon:
            lines.append(
                f"- {normalize_str(row.get('category'))}: {safe_int(row.get('count'), 0)}건 ({row.get('share_pct', 0)}%)"
            )
    elif top_filtered_categories:
        lines.append("")
        lines.append("후보 밖 세부 분포:")
        for row in top_filtered_categories:
            lines.append(
                f"- {normalize_str(row.get('category'))}: {safe_int(row.get('count'), 0)}건 ({row.get('share_pct', 0)}%)"
            )
    if probing_sequence_summaries:
        lines.append("")
        lines.append("Context-only probing sequence 요약:")
        for item in probing_sequence_summaries[:5]:
            sample_paths = ", ".join(item.get("sample_paths") or []) or "-"
            lines.append(
                f"- src_ip={normalize_str(item.get('src_ip')) or '-'} | "
                f"window={normalize_str(item.get('start')) or '-'} ~ {normalize_str(item.get('end')) or '-'} | "
                f"requests={safe_int(item.get('request_count'), 0)} | "
                f"distinct_paths={safe_int(item.get('distinct_path_count'), 0)} | "
                f"sample_paths={sample_paths}"
            )
            if item.get("response_size_repetition"):
                repetition = item.get("response_size_repetition") or {}
                lines.append(
                    f"  - 반복 응답 힌트: dominant_response_body_bytes={safe_int(repetition.get('dominant_response_body_bytes'), 0)} | "
                    f"dominant_count={safe_int(repetition.get('dominant_count'), 0)}"
                )
            interpretation_hint = normalize_str(item.get("interpretation_hint"))
            if interpretation_hint:
                lines.append(f"  - 해석: {interpretation_hint}")
    lines.append("")

    lines.append("## 8. Static baseline context")
    if static_baseline_summaries:
        lines.append("- 아래 항목은 context-only 이며 개별 incident 승격이나 baseline outcome 확정 근거가 아닙니다.")
        lines.append("- static_baseline_summaries 의 request 수는 같은 src_ip 와 static/health/browse baseline 시간창 기준 관찰 수입니다.")
        for item in static_baseline_summaries[:5]:
            status_counts = json.dumps(item.get("status_counts") or {}, ensure_ascii=False)
            asset_categories = ", ".join(item.get("asset_categories_observed") or []) or "-"
            reason_hints = ", ".join(item.get("reason_hints") or []) or "-"
            lines.append(
                f"- src_ip={normalize_str(item.get('src_ip')) or '-'} | "
                f"window={normalize_str(item.get('window_start')) or '-'} ~ {normalize_str(item.get('window_end')) or '-'} | "
                f"window_requests={safe_int(item.get('request_count'), 0)} | "
                f"asset_categories={asset_categories} | status_counts={status_counts}"
            )
            lines.append(f"  - reason_hints={reason_hints}")
            lines.append("  - 해석: static/health/browse baseline 관찰 문맥으로만 본다.")
            lines.append("  - 제한: status, bytes, content_type 만으로 static file 존재, robots/sitemap 내용, JS 실행, file exposure, health 정상 여부를 단정하지 않는다.")
            if bool(item.get("known_asset")):
                lines.append("  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.")
    else:
        lines.append("- 관찰된 static_baseline_summaries 없음")
    lines.append("")

    lines.append("## 9. Crawler baseline context")
    if crawler_baseline_summaries:
        lines.append("- 아래 항목은 context-only 이며 개별 incident 승격이나 crawler authenticity 확정 근거가 아닙니다.")
        lines.append("- crawler_baseline_summaries 의 request 수는 같은 src_ip 와 crawler-like UA/browse baseline 시간창 기준 관찰 수입니다.")
        for item in crawler_baseline_summaries[:5]:
            status_counts = json.dumps(item.get("status_counts") or {}, ensure_ascii=False)
            ua_families = ", ".join(item.get("crawler_like_user_agent_families") or []) or "-"
            path_categories = ", ".join(item.get("path_categories_observed") or []) or "-"
            reason_hints = ", ".join(item.get("reason_hints") or []) or "-"
            lines.append(
                f"- src_ip={normalize_str(item.get('src_ip')) or '-'} | "
                f"window={normalize_str(item.get('window_start')) or '-'} ~ {normalize_str(item.get('window_end')) or '-'} | "
                f"window_requests={safe_int(item.get('request_count'), 0)} | "
                f"ua_families={ua_families} | path_categories={path_categories} | status_counts={status_counts}"
            )
            lines.append(f"  - reason_hints={reason_hints}")
            lines.append("  - 해석: crawler-like baseline 또는 low-signal crawl context 로만 본다.")
            lines.append("  - 제한: User-Agent spoof 가능성, robots/sitemap 내용, site structure, page existence, attack success 를 단정하지 않는다.")
            if bool(item.get("known_asset")):
                lines.append("  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.")
    else:
        lines.append("- 관찰된 crawler_baseline_summaries 없음")
    lines.append("")

    lines.append("## 10. Mixed baseline/scanner context")
    if mixed_baseline_scanner_summaries:
        lines.append("- 아래 항목은 context-only 이며 baseline/static/crawler-like 와 scanner-like 를 하나의 성공 공격으로 합치는 근거가 아닙니다.")
        lines.append("- mixed_baseline_scanner_summaries 의 request 수는 같은 src_ip 와 mixed baseline/scanner 시간창 기준 관찰 수입니다.")
        for item in mixed_baseline_scanner_summaries[:5]:
            status_counts = json.dumps(item.get("status_counts") or {}, ensure_ascii=False)
            baseline_contexts = ", ".join(item.get("baseline_contexts_observed") or []) or "-"
            scanner_contexts = ", ".join(item.get("scanner_contexts_observed") or []) or "-"
            path_categories = ", ".join(item.get("path_categories_observed") or []) or "-"
            reason_hints = ", ".join(item.get("reason_hints") or []) or "-"
            lines.append(
                f"- src_ip={normalize_str(item.get('src_ip')) or '-'} | "
                f"window={normalize_str(item.get('window_start')) or '-'} ~ {normalize_str(item.get('window_end')) or '-'} | "
                f"window_requests={safe_int(item.get('request_count'), 0)} | "
                f"baseline_contexts={baseline_contexts} | scanner_contexts={scanner_contexts} | "
                f"path_categories={path_categories} | status_counts={status_counts}"
            )
            lines.append(f"  - reason_hints={reason_hints}")
            lines.append("  - 해석: 같은 window 안에서 baseline/static/crawler-like 와 sensitive path probe 가 함께 관찰된 mixed context 로만 본다.")
            lines.append("  - 제한: file exposure, app presence, crawler authenticity, page existence, attack success 를 단정하지 않고, 단일 성공 공격으로 합치지 않는다.")
            if bool(item.get("known_asset")):
                lines.append("  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.")
    else:
        lines.append("- 관찰된 mixed_baseline_scanner_summaries 없음")
    lines.append("")

    lines.append("## 11. IP behavior context")
    if ip_behavior_aggregates:
        lines.append("- 아래 항목은 context-only 이며 개별 incident 승격이나 severity 상향 근거가 아닙니다.")
        lines.append("- ip_behavior_aggregates 의 request 수는 같은 src_ip/time window 기준 전체 또는 관련 요청 문맥 수이며, auth behavior count 와 직접 합산하지 않습니다.")
        if behavior_scope_note:
            lines.append(f"- scope 구분: {behavior_scope_note}")
        for item in ip_behavior_aggregates[:5]:
            attack_categories = ", ".join(item.get("attack_categories_attempted") or []) or "-"
            sensitive_paths = ", ".join(item.get("sensitive_path_hits") or []) or "-"
            reason_hints = ", ".join(item.get("reason_hints") or []) or "-"
            lines.append(
                f"- src_ip={normalize_str(item.get('src_ip')) or '-'} | "
                f"window={normalize_str(item.get('window_start')) or '-'} ~ {normalize_str(item.get('window_end')) or '-'} | "
                f"window_requests={safe_int(item.get('request_count'), 0)} | "
                f"distinct_paths={safe_int(item.get('distinct_paths'), 0)} | "
                f"4xx_ratio={safe_float(item.get('status_4xx_ratio'), 0.0):.2f} | "
                f"5xx_count={safe_int(item.get('status_5xx_count'), 0)}"
            )
            lines.append(f"  - attempted_categories={attack_categories}")
            lines.append(f"  - sensitive_path_hits={sensitive_paths}")
            lines.append(f"  - reason_hints={reason_hints}")
            lines.append("  - 해석: 같은 src_ip 에서 scanning-like 또는 reconnaissance-like behavior 가 관찰된 문맥으로만 본다.")
            interpretation_limit = normalize_str(item.get("interpretation_limit"))
            if interpretation_limit:
                lines.append(f"  - 제한: {interpretation_limit}")
            if bool(item.get("known_asset")):
                lines.append("  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.")
    else:
        lines.append("- 관찰된 ip_behavior_aggregates 없음")
    lines.append("")

    lines.append("## 12. Auth behavior context")
    if auth_behavior_summaries:
        lines.append("- 아래 항목은 context-only 이며 개별 incident 승격이나 auth success 확정 근거가 아닙니다.")
        lines.append("- auth_behavior_summaries 의 request 수는 auth endpoint family 기준 auth 요청 수이며, ip behavior aggregate request 수와 scope 가 다릅니다.")
        lines.append("- User-Agent 값은 raw evidence 로 참조할 수 있지만 lab-* 같은 실험 prefix 자체를 공격 근거로 사용하지 않고, 비브라우저성 또는 반복적 UA 패턴, 자동화/테스트성 UA 가능성 정도로 일반화해 해석합니다.")
        if behavior_scope_note:
            lines.append(f"- scope 구분: {behavior_scope_note}")
        for item in auth_behavior_summaries[:5]:
            status_counts = json.dumps(item.get("status_counts") or {}, ensure_ascii=False)
            reason_hints = ", ".join(item.get("reason_hints") or []) or "-"
            lines.append(
                f"- src_ip={normalize_str(item.get('src_ip')) or '-'} | "
                f"endpoint_family={normalize_str(item.get('endpoint_family')) or '-'} | "
                f"window={normalize_str(item.get('window_start')) or '-'} ~ {normalize_str(item.get('window_end')) or '-'} | "
                f"auth_requests={safe_int(item.get('auth_request_count'), safe_int(item.get('request_count'), 0))} | "
                f"status_counts={status_counts}"
            )
            lines.append(f"  - reason_hints={reason_hints}")
            lines.append("  - 해석: raw POST body 미확인 상태에서 반복 auth interaction 문맥으로만 본다.")
            lines.append("  - 제한: HTTP 200 observed after repeated 401 이어도 로그인 성공 confirmed 로 단정하지 않는다.")
            if bool(item.get("known_asset")):
                lines.append("  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.")
    else:
        lines.append("- 관찰된 auth_behavior_summaries 없음")
    lines.append("")

    lines.append("## 13. Method behavior context")
    if method_behavior_summaries:
        lines.append("- 아래 항목은 context-only 이며 개별 incident 승격이나 method success 확정 근거가 아닙니다.")
        lines.append("- method_behavior_summaries 의 request 수는 같은 src_ip 와 method/protocol relevant row 시간창 기준 관찰 수이며, auth/ip behavior count 와 직접 합산하지 않습니다.")
        for item in method_behavior_summaries[:5]:
            method_counts = json.dumps(item.get("method_counts") or {}, ensure_ascii=False)
            status_counts = json.dumps(item.get("status_counts") or {}, ensure_ascii=False)
            risky_methods = ", ".join(item.get("risky_methods_observed") or []) or "-"
            baseline_methods = ", ".join(item.get("baseline_methods_observed") or []) or "-"
            reason_hints = ", ".join(item.get("reason_hints") or []) or "-"
            lines.append(
                f"- src_ip={normalize_str(item.get('src_ip')) or '-'} | "
                f"window={normalize_str(item.get('window_start')) or '-'} ~ {normalize_str(item.get('window_end')) or '-'} | "
                f"window_requests={safe_int(item.get('request_count'), 0)} | "
                f"method_counts={method_counts} | status_counts={status_counts}"
            )
            lines.append(f"  - risky_methods={risky_methods}")
            lines.append(f"  - baseline_methods={baseline_methods}")
            lines.append(f"  - reason_hints={reason_hints}")
            lines.append("  - 해석: method probing 또는 baseline comparison context 로만 본다.")
            lines.append("  - 제한: OPTIONS/TRACE/PUT/DELETE/PATCH 의 status 만으로 method 허용, 업로드/삭제, XST, CORS 취약점을 단정하지 않는다.")
            if bool(item.get("known_asset")):
                lines.append("  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.")
    else:
        lines.append("- 관찰된 method_behavior_summaries 없음")
    lines.append("")

    lines.append("## 14. Protocol anomaly context")
    if protocol_anomaly_summaries:
        lines.append("- 아래 항목은 context-only 이며 개별 incident 승격이나 protocol bypass / exploit success 확정 근거가 아닙니다.")
        lines.append("- protocol_anomaly_summaries 의 request 수는 같은 src_ip 와 protocol anomaly relevant row 시간창 기준 관찰 수이며, auth/method/ip behavior count 와 직접 합산하지 않습니다.")
        for item in protocol_anomaly_summaries[:5]:
            method_counts = json.dumps(item.get("method_counts") or {}, ensure_ascii=False)
            status_counts = json.dumps(item.get("status_counts") or {}, ensure_ascii=False)
            anomaly_types = ", ".join(item.get("anomaly_types_observed") or []) or "-"
            reason_hints = ", ".join(item.get("reason_hints") or []) or "-"
            lines.append(
                f"- src_ip={normalize_str(item.get('src_ip')) or '-'} | "
                f"window={normalize_str(item.get('window_start')) or '-'} ~ {normalize_str(item.get('window_end')) or '-'} | "
                f"window_requests={safe_int(item.get('request_count'), 0)} | "
                f"method_counts={method_counts} | status_counts={status_counts}"
            )
            lines.append(f"  - anomaly_types={anomaly_types}")
            lines.append(f"  - reason_hints={reason_hints}")
            lines.append("  - 해석: request parsing / protocol surface 관찰 문맥으로만 본다.")
            lines.append("  - 제한: status_code, response_body_bytes, status_counts 만으로 우회 성공, 침해 성공, virtual host bypass 성공을 단정하지 않는다.")
            if bool(item.get("known_asset")):
                lines.append("  - 주의: known asset IP 와 일치하므로 내부 테스트/운영 점검 가능성을 함께 고려해야 합니다.")
    else:
        lines.append("- 관찰된 protocol_anomaly_summaries 없음")
    lines.append("")

    lines.append("## 15. 권고 조치")
    for item in report_json.get("recommended_actions") or []:
        lines.append(f"- **{normalize_str(item.get('priority'))}** {normalize_str(item.get('action'))}")
        lines.append(f"  - 근거: {normalize_str(item.get('why'))}")
    lines.append("")

    lines.append("## 16. 신뢰도와 한계")
    for item in report_json.get("confidence_and_limitations") or []:
        lines.append(f"- {normalize_str(item)}")
    lines.append("")

    lines.append("## 17. 발표용 한 줄 정리")
    lines.append(normalize_str(report_json.get("presentation_takeaway")))
    lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_dry_run_markdown(report_input: Dict[str, Any], selected_model: str, mode: str) -> str:
    ctx = report_input.get("analysis_context") or {}
    counts = report_input.get("pipeline_counts") or {}
    incidents = report_input.get("top_incidents") or []
    filtered_rows = report_input.get("top_filtered_categories") or []
    recon_rows = report_input.get("top_out_of_candidate_recon") or []
    probing_sequence_summaries = report_input.get("probing_sequence_summaries") or []
    static_baseline_summaries = report_input.get("static_baseline_summaries") or []
    crawler_baseline_summaries = report_input.get("crawler_baseline_summaries") or []
    sensitive_path_probe_summaries = report_input.get("sensitive_path_probe_summaries") or []
    mixed_baseline_scanner_summaries = report_input.get("mixed_baseline_scanner_summaries") or []
    ip_behavior_aggregates = report_input.get("ip_behavior_aggregates") or []
    auth_behavior_summaries = report_input.get("auth_behavior_summaries") or []
    method_behavior_summaries = report_input.get("method_behavior_summaries") or []
    protocol_anomaly_summaries = report_input.get("protocol_anomaly_summaries") or []
    asset_context = report_input.get("asset_context") or {}
    behavior_scope_note = build_behavior_scope_note(ip_behavior_aggregates, auth_behavior_summaries)
    lines: List[str] = []
    lines.append("# 드라이런 보안 분석 보고서")
    lines.append("")
    lines.append(f"- 분석 모드: {mode}")
    lines.append(f"- 사용 모델 예정: {selected_model}")
    lines.append(f"- 분석 시간대: {normalize_str(ctx.get('query_timezone')) or 'Asia/Seoul'}")
    window = ctx.get("window") or {}
    lines.append(f"- 분석 구간: {normalize_str(window.get('start')) or '-'} ~ {normalize_str(window.get('end_exclusive')) or '-'}")
    if asset_context.get("known_asset_ips"):
        lines.append(f"- known asset IP: {', '.join(asset_context.get('known_asset_ips') or [])}")
    lines.append("")
    lines.append("## 요약")
    lines.append(f"- 전체 export row 수: {safe_int(counts.get('total_exported_rows'), 0)}")
    lines.append(f"- 1차 후보 row 수: {safe_int(counts.get('candidate_rows'), 0)}")
    lines.append(f"- distinct incident 수: {safe_int(counts.get('distinct_incident_count'), 0)}")
    lines.append(f"- filtered out row 수: {safe_int(counts.get('filtered_out_rows'), 0)}")
    lines.append(f"- probing sequence summary 수: {safe_int(counts.get('probing_sequence_summary_count'), len(probing_sequence_summaries))}")
    lines.append(f"- static baseline summary 수: {safe_int(counts.get('static_baseline_summary_count'), len(static_baseline_summaries))}")
    lines.append(f"- crawler baseline summary 수: {safe_int(counts.get('crawler_baseline_summary_count'), len(crawler_baseline_summaries))}")
    lines.append(f"- sensitive path probe summary 수: {safe_int(counts.get('sensitive_path_probe_summary_count'), len(sensitive_path_probe_summaries))}")
    lines.append(f"- mixed baseline/scanner summary 수: {safe_int(counts.get('mixed_baseline_scanner_summary_count'), len(mixed_baseline_scanner_summaries))}")
    lines.append(f"- ip behavior aggregate 수: {safe_int(counts.get('ip_behavior_aggregate_count'), len(ip_behavior_aggregates))}")
    lines.append(f"- auth behavior summary 수: {safe_int(counts.get('auth_behavior_summary_count'), len(auth_behavior_summaries))}")
    lines.append(f"- method behavior summary 수: {safe_int(counts.get('method_behavior_summary_count'), len(method_behavior_summaries))}")
    lines.append(f"- protocol anomaly summary 수: {safe_int(counts.get('protocol_anomaly_summary_count'), len(protocol_anomaly_summaries))}")
    lines.append(f"- stage1 성공/오류: {safe_int(counts.get('stage1_success_count'), 0)} / {safe_int(counts.get('stage1_error_count'), 0)}")
    if filtered_rows:
        lines.append("- 후보 밖 주요 카테고리:")
        for row in filtered_rows:
            lines.append(
                f"  - {normalize_str(row.get('category'))}: {safe_int(row.get('count'), 0)}건 ({row.get('share_pct', 0)}%)"
            )
    if recon_rows:
        lines.append("- 후보 밖 탐색성 요청 승격 정책: low_signal_fuzzing / low_signal_dir_probe 는 기본적으로 incident 로 승격하지 않고, 동일 IP·동일 시간대·후속 고신호 incident 와 결합될 때만 승격 검토")
    if any(normalize_str(row.get("category")) in REFERENCE_BASELINE_FILTERED_CATEGORIES for row in filtered_rows):
        lines.append("- 정상 baseline 정책: benign_normal_search / normal_search_baseline 은 후보 밖 탐색성 요청이 아니라 정상 비교군 또는 reference baseline 으로 해석")
    if probing_sequence_summaries:
        lines.append("- context-only probing sequence:")
        for item in probing_sequence_summaries[:5]:
            sample_paths = ", ".join(item.get("sample_paths") or []) or "-"
            lines.append(
                f"  - src_ip={normalize_str(item.get('src_ip')) or '-'} | "
                f"requests={safe_int(item.get('request_count'), 0)} | "
                f"distinct_paths={safe_int(item.get('distinct_path_count'), 0)} | "
                f"sample_paths={sample_paths}"
            )
    if static_baseline_summaries:
        lines.append("- Static baseline context:")
        lines.append("- static_baseline_summaries 의 request 수는 같은 src_ip 와 static/health/browse baseline 시간창 기준 관찰 수다.")
        for item in static_baseline_summaries[:5]:
            lines.append(
                f"  - src_ip={normalize_str(item.get('src_ip')) or '-'} | "
                f"window_requests={safe_int(item.get('request_count'), 0)} | "
                f"asset_categories={','.join(item.get('asset_categories_observed') or []) or '-'} | "
                f"status_counts={json.dumps(item.get('status_counts') or {}, ensure_ascii=False)}"
            )
        lines.append("- static baseline 해석 제한: status_code, response_body_bytes, content_type 만으로 static file 존재, robots/sitemap 내용, JS 실행, file exposure, health 정상 여부를 단정하지 않는다.")
    if crawler_baseline_summaries:
        lines.append("- Crawler baseline context:")
        lines.append("- crawler_baseline_summaries 의 request 수는 같은 src_ip 와 crawler-like UA/browse baseline 시간창 기준 관찰 수다.")
        for item in crawler_baseline_summaries[:5]:
            lines.append(
                f"  - src_ip={normalize_str(item.get('src_ip')) or '-'} | "
                f"window_requests={safe_int(item.get('request_count'), 0)} | "
                f"ua_families={','.join(item.get('crawler_like_user_agent_families') or []) or '-'} | "
                f"path_categories={','.join(item.get('path_categories_observed') or []) or '-'} | "
                f"status_counts={json.dumps(item.get('status_counts') or {}, ensure_ascii=False)}"
            )
        lines.append("- crawler baseline 해석 제한: 실제 crawler 여부, robots/sitemap 내용, site structure, product/category page existence, attack success 를 단정하지 않는다.")
    if sensitive_path_probe_summaries:
        lines.append("- Sensitive path probe context:")
        lines.append("- sensitive_path_probe_summaries 의 request 수는 같은 src_ip 와 sensitive path 시간창 기준 관찰 수다.")
        for item in sensitive_path_probe_summaries[:5]:
            lines.append(
                f"  - src_ip={normalize_str(item.get('src_ip')) or '-'} | "
                f"window_requests={safe_int(item.get('request_count'), 0)} | "
                f"path_categories={','.join(item.get('path_categories_observed') or []) or '-'} | "
                f"status_counts={json.dumps(item.get('status_counts') or {}, ensure_ascii=False)}"
            )
        lines.append("- sensitive path probe 해석 제한: WordPress 존재, admin access, .env/phpinfo/server-status/backup 노출 또는 차단 성공, attack success 를 단정하지 않는다.")
    if mixed_baseline_scanner_summaries:
        lines.append("- Mixed baseline/scanner context:")
        lines.append("- mixed_baseline_scanner_summaries 의 request 수는 같은 src_ip 와 mixed baseline/scanner 시간창 기준 관찰 수다.")
        for item in mixed_baseline_scanner_summaries[:5]:
            lines.append(
                f"  - src_ip={normalize_str(item.get('src_ip')) or '-'} | "
                f"window_requests={safe_int(item.get('request_count'), 0)} | "
                f"baseline_contexts={','.join(item.get('baseline_contexts_observed') or []) or '-'} | "
                f"scanner_contexts={','.join(item.get('scanner_contexts_observed') or []) or '-'} | "
                f"path_categories={','.join(item.get('path_categories_observed') or []) or '-'} | "
                f"status_counts={json.dumps(item.get('status_counts') or {}, ensure_ascii=False)}"
            )
        lines.append("- mixed baseline/scanner 해석 제한: baseline/static/crawler-like 와 scanner-like 를 같은 성공 공격으로 합치지 않고, file exposure, app presence, crawler authenticity, page existence, attack success 를 단정하지 않는다.")
    if ip_behavior_aggregates:
        lines.append("- context-only IP behavior aggregates:")
        lines.append("- ip_behavior_aggregates 의 request 수는 같은 src_ip/time window 기준 전체 또는 관련 요청 문맥 수다.")
        if behavior_scope_note:
            lines.append(f"- scope 구분: {behavior_scope_note}")
        for item in ip_behavior_aggregates[:5]:
            categories = ", ".join(item.get("attack_categories_attempted") or []) or "-"
            lines.append(
                f"  - src_ip={normalize_str(item.get('src_ip')) or '-'} | "
                f"window_requests={safe_int(item.get('request_count'), 0)} | "
                f"distinct_paths={safe_int(item.get('distinct_paths'), 0)} | "
                f"4xx_ratio={safe_float(item.get('status_4xx_ratio'), 0.0):.2f} | "
                f"attempted_categories={categories}"
            )
    if auth_behavior_summaries:
        lines.append("- context-only auth behavior summaries:")
        lines.append("- auth_behavior_summaries 의 request 수는 auth endpoint family 기준 auth 요청 수이며, ip_behavior_aggregates request 수와 직접 합산하지 않는다.")
        lines.append("- User-Agent 는 raw evidence 로 표시될 수 있지만 lab-* 같은 실험 prefix 자체를 공격 근거로 사용하지 않고, 비브라우저성 또는 반복적 UA 패턴, 자동화/테스트성 UA 가능성 정도로 일반화해 해석한다.")
        if behavior_scope_note:
            lines.append(f"- scope 구분: {behavior_scope_note}")
        for item in auth_behavior_summaries[:5]:
            lines.append(
                f"  - src_ip={normalize_str(item.get('src_ip')) or '-'} | "
                f"endpoint_family={normalize_str(item.get('endpoint_family')) or '-'} | "
                f"auth_requests={safe_int(item.get('auth_request_count'), safe_int(item.get('request_count'), 0))} | "
                f"status_counts={json.dumps(item.get('status_counts') or {}, ensure_ascii=False)}"
            )
        lines.append("- auth 해석 제한: raw POST body 미확인 상태이며 HTTP 200 observed after repeated 401 이어도 로그인 성공 confirmed 로 단정하지 않는다.")
    if method_behavior_summaries:
        lines.append("- context-only method behavior summaries:")
        lines.append("- method_behavior_summaries 의 request 수는 같은 src_ip 와 method/protocol relevant row 시간창 기준 관찰 수이며, auth/ip behavior count 와 직접 합산하지 않는다.")
        for item in method_behavior_summaries[:5]:
            lines.append(
                f"  - src_ip={normalize_str(item.get('src_ip')) or '-'} | "
                f"window_requests={safe_int(item.get('request_count'), 0)} | "
                f"risky_methods={','.join(item.get('risky_methods_observed') or []) or '-'} | "
                f"baseline_methods={','.join(item.get('baseline_methods_observed') or []) or '-'} | "
                f"method_counts={json.dumps(item.get('method_counts') or {}, ensure_ascii=False)}"
            )
        lines.append("- method 해석 제한: OPTIONS/TRACE/PUT/DELETE/PATCH 의 status_code=200/201/204 만으로 method 허용, 업로드 성공, 삭제 성공, XST 성공, CORS 취약점을 단정하지 않는다.")
    if protocol_anomaly_summaries:
        lines.append("- context-only protocol anomaly summaries:")
        lines.append("- protocol_anomaly_summaries 의 request 수는 같은 src_ip 와 protocol anomaly relevant row 시간창 기준 관찰 수이며, auth/method/ip behavior count 와 직접 합산하지 않는다.")
        for item in protocol_anomaly_summaries[:5]:
            lines.append(
                f"  - src_ip={normalize_str(item.get('src_ip')) or '-'} | "
                f"window_requests={safe_int(item.get('request_count'), 0)} | "
                f"anomaly_types={','.join(item.get('anomaly_types_observed') or []) or '-'} | "
                f"method_counts={json.dumps(item.get('method_counts') or {}, ensure_ascii=False)}"
            )
        lines.append("- protocol anomaly 해석 제한: status_code=200/400/405/408/414/500/501/505, response_body_bytes, status_counts 만으로 protocol bypass 성공, exploit success, compromise success, virtual host bypass 성공을 단정하지 않는다.")
    lines.append("")
    lines.append("## 상위 incident 미리보기")
    for item in incidents[:5]:
        known_asset_note = " | known_asset=yes" if bool(item.get("known_asset")) else ""
        lines.append(
            f"- incident_ref={normalize_str(item.get('incident_ref')) or '-'} | "
            f"request_id={normalize_str(item.get('request_id')) or '-'} | "
            f"src_ip={normalize_str(item.get('src_ip')) or '-'} | "
            f"verdict={normalize_str(item.get('verdict'))} | "
            f"severity={normalize_str(item.get('severity'))} | "
            f"uri={normalize_str(item.get('uri')) or '-'} | "
            f"merged_rows={safe_int(item.get('duplicate_count'), 1)}{known_asset_note}"
        )
        if has_php_wrapper_file_disclosure_context(item):
            lines.append(
                "  - PHP wrapper 문맥: php://filter/convert.base64-encode/resource=... 계열은 PHP stream wrapper 기반 source/config disclosure attempt 또는 LFI-like file disclosure attempt 로 해석한다."
            )
            lines.append(
                "  - 해석 제한: Apache 로그만으로 실제 파일 내용 반환 여부는 확인할 수 없으므로 성공한 유출이 아니라 시도 정황으로만 본다."
            )
    lines.append("")
    lines.append("## 메모")
    lines.append("- dry-run 이므로 실제 LLM API 호출 없이 요약 입력만 검증했다.")
    lines.append("- incident 는 request_id 우선, 없으면 src_ip+method+uri+status_code+1초 단위 시각으로 병합했다.")
    lines.append("- filtered_out_breakdown 은 noise_summary 와 별도로 보존되며, 보고서 초안에도 함께 노출된다.")
    lines.append("- static_baseline_summaries, crawler_baseline_summaries, sensitive_path_probe_summaries, mixed_baseline_scanner_summaries, auth_behavior_summaries, method_behavior_summaries, protocol_anomaly_summaries, ip_behavior_aggregates 는 scope 가 다르므로 count 를 range 로 합치거나 같은 사건 수처럼 직접 합산하지 않는다.")
    lines.append("- static_baseline_summaries 는 context-only 이며 static/health/browse baseline 문맥으로만 사용하고 static file 존재, robots/sitemap 내용, JS 실행, file exposure, health 정상 여부를 단정하지 않는다.")
    lines.append("- crawler_baseline_summaries 는 context-only 이며 crawler-like baseline 문맥으로만 사용하고 crawler authenticity, robots/sitemap 내용, site structure, page existence, attack success 를 단정하지 않는다.")
    lines.append("- sensitive_path_probe_summaries 는 context-only 이며 scanner-like sensitive path probing 문맥으로만 사용하고 WordPress 존재, admin access, .env/phpinfo/server-status/backup 노출, 차단 성공, attack success 를 단정하지 않는다.")
    lines.append("- mixed_baseline_scanner_summaries 는 context-only 이며 baseline/static/crawler-like 와 scanner-like 문맥을 분리해서 설명하고, 이를 같은 성공 공격이나 단일 침해 체인으로 합치지 않는다.")
    lines.append("- ip_behavior_aggregates 는 context-only 이며 개별 incident 승격이나 severity 상향 근거로 사용하지 않는다.")
    lines.append("- auth_behavior_summaries 는 context-only 이며 raw POST body 미확인 상태에서 auth sequence 문맥으로만 사용한다.")
    lines.append("- method_behavior_summaries 는 context-only 이며 method probing / baseline 문맥으로만 사용하고 method 허용이나 성공 근거로 사용하지 않는다.")
    lines.append("- protocol_anomaly_summaries 는 context-only 이며 request parsing / protocol surface 문맥으로만 사용하고 우회 성공이나 침해 성공 근거로 사용하지 않는다.")
    lines.append("- User-Agent 값은 evidence 로 참조할 수 있지만 lab-* 같은 실험 prefix 자체를 공격 근거로 사용하지 않는다.")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    args = parse_args()

    stage1_payload = load_json(args.stage1_results)
    if "results" not in stage1_payload or "meta" not in stage1_payload:
        print("[ERROR] stage1_results 형식이 올바르지 않습니다.", file=sys.stderr)
        return 2

    llm_input_path = args.llm_input or infer_related_path(args.stage1_results, "_llm_input")
    llm_input_payload: Optional[Dict[str, Any]] = None
    if os.path.exists(llm_input_path):
        llm_input_payload = load_json(llm_input_path)

    stage1_errors_path = args.stage1_errors or infer_related_path(args.stage1_results, "_stage1_errors")
    stage1_errors_payload: Optional[Dict[str, Any]] = None
    if os.path.exists(stage1_errors_path):
        stage1_errors_payload = load_json(stage1_errors_path)

    try:
        llm_config = resolve_llm_config(args.provider)
        selected_model = choose_model(llm_config.provider, args.mode, args.model, dry_run=bool(args.dry_run))
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 2
    base_name = derive_base_name(args.stage1_results, args.base_name)
    out_dir = Path(args.out_dir)
    report_json_path = out_dir / f"{base_name}_stage2_report.json"
    report_md_path = out_dir / f"{base_name}_stage2_report.md"
    report_input_path = out_dir / f"{base_name}_stage2_report_input.json"
    report_error_path = out_dir / f"{base_name}_stage2_report_error.json"
    report_raw_error_path = out_dir / f"{base_name}_stage2_report_raw_error.json"
    known_asset_ips = resolve_known_asset_ips(args.known_asset_ips)

    report_input = build_report_input(
        stage1_payload=stage1_payload,
        llm_input_payload=llm_input_payload,
        stage1_errors_payload=stage1_errors_payload,
        top_incidents=args.top_incidents,
        top_noise_groups=args.top_noise_groups,
        top_ips=args.top_ips,
        known_asset_ips=known_asset_ips,
    )
    dump_json(str(report_input_path), report_input, pretty=args.pretty)

    if args.dry_run:
        md = build_dry_run_markdown(report_input, selected_model=selected_model, mode=args.mode)
        write_text(str(report_md_path), md)
        dump_json(
            str(report_json_path),
            {
                "meta": {
                    "generated_at": iso_now(),
                    "mode": args.mode,
                    "provider": llm_config.provider,
                    "selected_model": selected_model,
                    "dry_run": True,
                    "known_asset_ips": known_asset_ips,
                    "base_url": llm_config.base_url,
                    "input_stage1_results": os.path.abspath(args.stage1_results),
                    "input_llm_input": os.path.abspath(llm_input_path) if llm_input_payload else None,
                },
                "report": None,
            },
            pretty=args.pretty,
        )
        print(f"[OK] stage2_report_input: {report_input_path}")
        print(f"[OK] stage2_report_md:    {report_md_path}")
        print(f"[OK] stage2_report_json:  {report_json_path}")
        return 0

    if not llm_config.api_key:
        print(f"[ERROR] {provider_api_key_error(llm_config.provider)}", file=sys.stderr)
        return 2

    try:
        messages = build_messages(report_input)
        schema = build_schema()
        llm_response = call_llm_json(
            config=llm_config,
            model=selected_model,
            messages=messages,
            schema=schema,
            schema_name="stage2_security_report",
            timeout_sec=args.timeout_sec,
            store=bool(args.store),
            reasoning_effort=args.reasoning_effort,
        )
        output_text = llm_response.output_text
        response_id = llm_response.response_id
        stop_reason = llm_response.stop_reason
        log_llm_response_summary("stage2_response", llm_response.provider, response_id, stop_reason)
        if not output_text:
            empty_error = RuntimeError("응답에서 output_text를 찾지 못했습니다.")
            dump_stage2_parse_error(
                report_error_path=report_error_path,
                raw_dump_path=report_raw_error_path,
                provider=llm_response.provider,
                model=llm_response.model,
                response_id=response_id,
                stop_reason=stop_reason,
                output_text=output_text,
                raw_response=llm_response.raw_response,
                parse_error=empty_error,
                pretty=args.pretty,
                repair_attempted=False,
            )
            print(f"[ERROR] {empty_error}", file=sys.stderr)
            print(f"[ERROR] raw dump: {report_raw_error_path}", file=sys.stderr)
            return 1
        try:
            parse_result = safe_parse_llm_json(output_text)
        except LLMJsonParseError as parse_error:
            if llm_config.provider != "anthropic":
                dump_stage2_parse_error(
                    report_error_path=report_error_path,
                    raw_dump_path=report_raw_error_path,
                    provider=llm_response.provider,
                    model=llm_response.model,
                    response_id=response_id,
                    stop_reason=stop_reason,
                    output_text=output_text,
                    raw_response=llm_response.raw_response,
                    parse_error=parse_error,
                    pretty=args.pretty,
                    repair_attempted=False,
                )
                print(f"[ERROR] stage2 JSON parse failed: {parse_error}", file=sys.stderr)
                print(f"[ERROR] raw dump: {report_raw_error_path}", file=sys.stderr)
                return 1

            print("[WARN] Anthropic stage2 JSON parse failed. Retrying one JSON repair request.", file=sys.stderr)
            repair_response = call_llm_json(
                config=llm_config,
                model=selected_model,
                messages=build_repair_messages(output_text),
                schema=schema,
                schema_name="stage2_security_report",
                timeout_sec=args.timeout_sec,
                store=bool(args.store),
                reasoning_effort=args.reasoning_effort,
            )
            log_llm_response_summary(
                "stage2_repair_response",
                repair_response.provider,
                repair_response.response_id,
                repair_response.stop_reason,
            )
            try:
                parse_result = safe_parse_llm_json(repair_response.output_text)
                llm_response = repair_response
                output_text = repair_response.output_text
                response_id = repair_response.response_id
                stop_reason = repair_response.stop_reason
            except LLMJsonParseError as repair_error:
                dump_stage2_parse_error(
                    report_error_path=report_error_path,
                    raw_dump_path=report_raw_error_path,
                    provider=repair_response.provider,
                    model=repair_response.model,
                    response_id=repair_response.response_id,
                    stop_reason=repair_response.stop_reason,
                    output_text=repair_response.output_text,
                    raw_response=repair_response.raw_response,
                    parse_error=repair_error,
                    pretty=args.pretty,
                    repair_attempted=True,
                    repair_response={
                        "response_id": repair_response.response_id,
                        "stop_reason": repair_response.stop_reason,
                        "output_text": repair_response.output_text,
                        "raw_response": repair_response.raw_response,
                        "initial_response_id": response_id,
                        "initial_stop_reason": stop_reason,
                        "initial_output_text": output_text,
                        "initial_raw_response": llm_response.raw_response,
                        "initial_parse_error": str(parse_error),
                    },
                )
                print(f"[ERROR] stage2 JSON repair failed: {repair_error}", file=sys.stderr)
                print(f"[ERROR] raw dump: {report_raw_error_path}", file=sys.stderr)
                return 1

        report_json = parse_result.parsed
        print(f"[INFO] stage2 JSON parsed via {parse_result.strategy}")
        markdown = render_markdown(report_json, report_input, selected_model=selected_model, mode=args.mode)

        dump_json(
            str(report_json_path),
            {
                "meta": {
                    "generated_at": iso_now(),
                    "mode": args.mode,
                    "provider": llm_config.provider,
                    "selected_model": selected_model,
                    "store": bool(args.store),
                    "reasoning_effort": args.reasoning_effort,
                    "known_asset_ips": known_asset_ips,
                    "base_url": llm_config.base_url,
                    "response_id": response_id,
                    "stop_reason": stop_reason,
                    "json_parse_strategy": parse_result.strategy,
                    "input_stage1_results": os.path.abspath(args.stage1_results),
                    "input_llm_input": os.path.abspath(llm_input_path) if llm_input_payload else None,
                },
                "report": report_json,
            },
            pretty=args.pretty,
        )
        write_text(str(report_md_path), markdown)
        print(f"[OK] stage2_report_input: {report_input_path}")
        print(f"[OK] stage2_report_json:  {report_json_path}")
        print(f"[OK] stage2_report_md:    {report_md_path}")
        return 0

    except error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = ""
        dump_json(
            str(report_error_path),
            {
                "error_type": "http_error",
                "error_message": f"HTTP {e.code}: {e.reason}",
                "response_excerpt": body[:2000],
            },
            pretty=args.pretty,
        )
        print(f"[ERROR] HTTP {e.code}: {e.reason}", file=sys.stderr)
        return 1
    except error.URLError as e:
        dump_json(
            str(report_error_path),
            {
                "error_type": "url_error",
                "error_message": normalize_str(e.reason) or repr(e),
            },
            pretty=args.pretty,
        )
        print(f"[ERROR] URL error: {normalize_str(e.reason) or repr(e)}", file=sys.stderr)
        return 1
    except Exception as e:
        dump_json(
            str(report_error_path),
            {
                "error_type": "unexpected_error",
                "error_message": repr(e),
            },
            pretty=args.pretty,
        )
        print(f"[ERROR] unexpected: {repr(e)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
