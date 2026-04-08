#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prepare_llm_input.py / llm_stage1_classifier.py 산출물을 바탕으로
최종 Markdown 분석 보고서를 생성하는 2차 LLM 리포터.

주요 개선 사항
- request_id 단독 매칭을 제거하고 incident_ref 기반으로 안전하게 재매칭
- access/security 중복 row 를 incident 단위로 묶어 distinct incident 중심으로 요약
- known asset IP(웹서버/DB/LLM 서버 등) 목록을 받아 내부 테스트/자체 호출 가능성을 보고서에 반영
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
from urllib import error, request

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_TIMEOUT_SEC = 180
DEFAULT_MODE = "routine"
DEFAULT_ROUTINE_MODEL = "gpt-5.4-mini"
DEFAULT_MILESTONE_MODEL = "gpt-5.4"
DEFAULT_PRESENTATION_MODEL = "gpt-5.4"
ALLOWED_MODES = {"routine", "milestone", "presentation"}
SEVERITY_ORDER = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
CONFIDENCE_ORDER = {"high": 3, "medium": 2, "low": 1}
TABLE_PRIORITY = {"security": 3, "error": 2, "access": 1}


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
    recommended_actions: List[str]
    known_asset: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM 2차 보고서 생성기 (Responses API / Structured Outputs)")
    parser.add_argument("--stage1-results", required=True, help="llm_stage1_classifier.py 결과 <base>_stage1_results.json")
    parser.add_argument("--llm-input", default=None, help="prepare_llm_input.py 결과 <base>_llm_input.json")
    parser.add_argument("--stage1-errors", default=None, help="선택: <base>_stage1_errors.json")
    parser.add_argument("--out-dir", default=".", help="산출물 저장 디렉터리")
    parser.add_argument("--base-name", default=None, help="산출물 파일명 접두어")
    parser.add_argument("--mode", default=DEFAULT_MODE, choices=sorted(ALLOWED_MODES), help="모델 사용 모드")
    parser.add_argument("--model", default=None, help="명시적 모델 override")
    parser.add_argument("--top-incidents", type=int, default=12, help="모델에 전달할 상위 incident 수")
    parser.add_argument("--top-noise-groups", type=int, default=8, help="모델에 전달할 상위 noise group 수")
    parser.add_argument("--top-ips", type=int, default=8, help="모델에 전달할 상위 src_ip 수")
    parser.add_argument("--known-asset-ips", default=os.getenv("KNOWN_ASSET_IPS", ""), help="쉼표 구분 known asset IP 목록")
    parser.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC, help="HTTP 타임아웃")
    parser.add_argument("--store", action="store_true", help="Responses API 결과 저장 활성화 (기본값은 false)")
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


def normalize_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def iso_now() -> str:
    return datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="milliseconds")


def choose_model(mode: str, override: Optional[str]) -> str:
    if override:
        return override
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


def build_incident_briefs(results: List[Dict[str, Any]], top_n: int, known_asset_ips: Sequence[str]) -> List[IncidentBrief]:
    deduped = dedup_stage1_results(results, known_asset_ips=known_asset_ips)
    briefs: List[IncidentBrief] = []
    for idx, item in enumerate(deduped[:top_n], start=1):
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
    stage1_errors = (stage1_errors_payload or {}).get("errors") or []

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

    briefs = [asdict(x) for x in build_incident_briefs(results, top_n=top_incidents, known_asset_ips=known_asset_ips)]
    ip_rows = summarize_ips(results, top_n=top_ips, known_asset_ips=known_asset_ips)
    top_noise = sorted(
        noise_summary,
        key=lambda x: safe_int(x.get("count"), 0),
        reverse=True,
    )[:top_noise_groups]

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
            "filtered_out_rows": safe_int(counts.get("filtered_out_rows"), 0),
            "noise_group_count": safe_int(counts.get("noise_group_count"), len(noise_summary)),
            "stage1_success_count": safe_int(meta.get("success_count"), len(results)),
            "stage1_error_count": safe_int(meta.get("error_count"), len(stage1_errors)),
        },
        "distributions": {
            "verdicts": dict(verdict_counter),
            "severities": dict(severity_counter),
            "source_tables": dict(table_counter),
            "recommended_actions": dict(action_counter),
        },
        "top_incidents": briefs,
        "top_src_ips": ip_rows,
        "top_noise_groups": top_noise,
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
            "dedupe_rule": "request_id 우선, 없으면 src_ip+method+uri+status_code+1초 단위 시각으로 incident 병합",
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
        "path traversal 의 경우 200 응답만으로 실제 파일 노출을 단정하지 마라. "
        "resp_content_type 이 text/html 이거나 HTML fallback 정황이 있으면 시도 탐지와 실제 노출 가능성을 분리해서 서술하라. "
        "동일 파라미터가 반복되면 HPP(HTTP Parameter Pollution) 문맥을 검토하라. "
        "hpp_detected 가 true 이고 embedded_attack_hint 가 있으면, 사건 분류는 기존 SQLi/XSS 체계를 유지하되 보고서 설명에는 '중복 파라미터(HPP)를 이용한 시도' 문맥을 포함하라. "
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
            "path traversal 은 raw_request_target, uri, resp_content_type, response_body_bytes, likely_html_fallback_response 를 함께 보고 시도와 실제 노출 가능성을 구분하라.",
            "resp_content_type 이 text/html 이고 likely_html_fallback_response 가 true 면 앱 fallback HTML 가능성을 우선 검토하라.",
            "hpp_detected 가 true 인 incident 는 hpp_param_names 와 embedded_attack_hint 를 함께 보고, 중복 파라미터(HPP)를 통한 공격 시도인지 서술하라.",
            "known_asset_ips 와 일치하는 IP 는 내부 테스트/자체 호출 가능성을 반드시 함께 언급하라.",
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


def extract_output_text(response_payload: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    response_id = normalize_str(response_payload.get("id")) or None
    output = response_payload.get("output") or []
    chunks: List[str] = []

    for item in output:
        if not isinstance(item, dict):
            continue
        for content in item.get("content") or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") == "output_text" and "text" in content:
                chunks.append(str(content.get("text", "")))

    if chunks:
        return "".join(chunks).strip(), response_id

    maybe_output_text = response_payload.get("output_text")
    if isinstance(maybe_output_text, str) and maybe_output_text.strip():
        return maybe_output_text.strip(), response_id

    return "", response_id


def call_responses_api(
    api_key: str,
    base_url: str,
    model: str,
    messages: List[Dict[str, str]],
    timeout_sec: int,
    store: bool,
    reasoning_effort: str,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "model": model,
        "input": messages,
        "store": store,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "stage2_security_report",
                "strict": True,
                "schema": build_schema(),
            }
        },
    }
    if reasoning_effort != "none":
        body["reasoning"] = {"effort": reasoning_effort}

    url = base_url.rstrip("/") + "/responses"
    data = json.dumps(body).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with request.urlopen(req, timeout=timeout_sec) as resp:
        return json.loads(resp.read().decode("utf-8"))


def render_markdown(report_json: Dict[str, Any], report_input: Dict[str, Any], selected_model: str, mode: str) -> str:
    ctx = report_input.get("analysis_context") or {}
    counts = report_input.get("pipeline_counts") or {}
    top_incidents = report_input.get("top_incidents") or []
    verdicts = (report_input.get("distributions") or {}).get("verdicts") or {}
    severities = (report_input.get("distributions") or {}).get("severities") or {}
    source_tables = (report_input.get("distributions") or {}).get("source_tables") or {}
    asset_context = report_input.get("asset_context") or {}

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
    lines.append(f"- noise 집계 그룹 수: {safe_int(counts.get('noise_group_count'), 0)}")
    lines.append(f"- stage1 성공/오류: {safe_int(counts.get('stage1_success_count'), 0)} / {safe_int(counts.get('stage1_error_count'), 0)}")
    if verdicts:
        lines.append(f"- verdict 분포: {json.dumps(verdicts, ensure_ascii=False)}")
    if severities:
        lines.append(f"- severity 분포: {json.dumps(severities, ensure_ascii=False)}")
    if source_tables:
        lines.append(f"- 대표 source table 분포: {json.dumps(source_tables, ensure_ascii=False)}")
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

    lines.append("## 7. noise 해석")
    lines.append(normalize_str(report_json.get("noise_interpretation")))
    lines.append("")

    lines.append("## 8. 권고 조치")
    for item in report_json.get("recommended_actions") or []:
        lines.append(f"- **{normalize_str(item.get('priority'))}** {normalize_str(item.get('action'))}")
        lines.append(f"  - 근거: {normalize_str(item.get('why'))}")
    lines.append("")

    lines.append("## 9. 신뢰도와 한계")
    for item in report_json.get("confidence_and_limitations") or []:
        lines.append(f"- {normalize_str(item)}")
    lines.append("")

    lines.append("## 10. 발표용 한 줄 정리")
    lines.append(normalize_str(report_json.get("presentation_takeaway")))
    lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_dry_run_markdown(report_input: Dict[str, Any], selected_model: str, mode: str) -> str:
    ctx = report_input.get("analysis_context") or {}
    counts = report_input.get("pipeline_counts") or {}
    incidents = report_input.get("top_incidents") or []
    asset_context = report_input.get("asset_context") or {}
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
    lines.append(f"- stage1 성공/오류: {safe_int(counts.get('stage1_success_count'), 0)} / {safe_int(counts.get('stage1_error_count'), 0)}")
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
    lines.append("")
    lines.append("## 메모")
    lines.append("- dry-run 이므로 실제 Responses API 호출 없이 요약 입력만 검증했다.")
    lines.append("- incident 는 request_id 우선, 없으면 src_ip+method+uri+status_code+1초 단위 시각으로 병합했다.")
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

    selected_model = choose_model(args.mode, args.model)
    base_name = derive_base_name(args.stage1_results, args.base_name)
    out_dir = Path(args.out_dir)
    report_json_path = out_dir / f"{base_name}_stage2_report.json"
    report_md_path = out_dir / f"{base_name}_stage2_report.md"
    report_input_path = out_dir / f"{base_name}_stage2_report_input.json"
    report_error_path = out_dir / f"{base_name}_stage2_report_error.json"
    known_asset_ips = parse_known_asset_ips(args.known_asset_ips)

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
                    "selected_model": selected_model,
                    "dry_run": True,
                    "known_asset_ips": known_asset_ips,
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

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    if not api_key:
        print("[ERROR] OPENAI_API_KEY 가 설정되어 있지 않습니다.", file=sys.stderr)
        return 2

    try:
        messages = build_messages(report_input)
        response_payload = call_responses_api(
            api_key=api_key,
            base_url=base_url,
            model=selected_model,
            messages=messages,
            timeout_sec=args.timeout_sec,
            store=bool(args.store),
            reasoning_effort=args.reasoning_effort,
        )
        output_text, response_id = extract_output_text(response_payload)
        if not output_text:
            raise RuntimeError("응답에서 output_text를 찾지 못했습니다.")
        report_json = json.loads(output_text)
        markdown = render_markdown(report_json, report_input, selected_model=selected_model, mode=args.mode)

        dump_json(
            str(report_json_path),
            {
                "meta": {
                    "generated_at": iso_now(),
                    "mode": args.mode,
                    "selected_model": selected_model,
                    "store": bool(args.store),
                    "reasoning_effort": args.reasoning_effort,
                    "known_asset_ips": known_asset_ips,
                    "base_url": base_url,
                    "response_id": response_id,
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
