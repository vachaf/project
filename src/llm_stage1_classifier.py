#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prepare_llm_input.py 산출물(<base>_llm_input.json)을 입력으로 받아
후보별 1차 LLM 분류 결과를 생성하는 Responses API 기반 스크립트.

주요 역할
- analysis_candidates 배열을 순회하며 후보별 1차 판정 수행
- Structured Outputs(JSON Schema)로 결과 형식 고정
- routine / milestone / presentation 모드에 따라 기본 모델 선택
- 결과를 stage1_results.json 으로 저장

권장 위치
- 별도 분석 VM 의 파이프라인 디렉터리
- 예: /opt/web_log_analysis/src/llm_stage1_classifier.py

환경 변수
- OPENAI_API_KEY: 필수
- OPENAI_BASE_URL: 선택 (기본: https://api.openai.com/v1)

주의
- 이 스크립트는 표준 라이브러리(urllib)만 사용해 Responses API 를 호출한다.
- OpenAI Python SDK 설치 여부와 무관하게 동작하도록 작성했다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, request

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_TIMEOUT_SEC = 180
DEFAULT_MODE = "routine"
DEFAULT_ROUTINE_MODEL = "gpt-5.4-mini"
DEFAULT_MILESTONE_MODEL = "gpt-5.4"
DEFAULT_PRESENTATION_MODEL = "gpt-5.4"
ALLOWED_MODES = {"routine", "milestone", "presentation"}


@dataclass
class Stage1Result:
    candidate_index: int
    incident_group_key: str
    request_id: str
    error_link_id: str
    model: str
    source_table: str
    merged_source_tables: List[str]
    merged_row_count: int
    merged_log_ids: List[int]
    log_id: Optional[int]
    src_ip: str
    method: str
    uri: str
    query_string: str
    log_time: str
    status_code: int
    score: int
    verdict_hint: str
    reason_hints: List[str]
    response_body_bytes: int
    resp_content_type: str
    raw_request_target: str
    path_normalized_from_raw_request: bool
    likely_html_fallback_response: bool
    hpp_detected: bool
    hpp_param_names: List[str]
    embedded_attack_hint: str
    verdict: str
    severity: str
    confidence: str
    false_positive_possible: bool
    reasoning_summary: str
    evidence_fields: List[str]
    recommended_actions: List[str]
    response_id: Optional[str]
    raw_output_text: str


@dataclass
class Stage1Error:
    candidate_index: int
    request_id: str
    model: str
    error_type: str
    error_message: str
    response_id: Optional[str] = None
    raw_response_excerpt: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM 1차 분류기 (Responses API / Structured Outputs)")
    parser.add_argument("--input", required=True, help="prepare_llm_input.py 결과 <base>_llm_input.json")
    parser.add_argument("--out-dir", default=".", help="산출물 저장 디렉터리")
    parser.add_argument("--base-name", default=None, help="산출물 파일명 접두어")
    parser.add_argument("--mode", default=DEFAULT_MODE, choices=sorted(ALLOWED_MODES), help="모델 사용 모드")
    parser.add_argument("--model", default=None, help="명시적 모델 override")
    parser.add_argument("--candidate-limit", type=int, default=0, help="상위 N개 후보만 처리 (0은 전체)")
    parser.add_argument("--max-evidence-items", type=int, default=8, help="후보별 evidence_fields 최대 개수")
    parser.add_argument("--sleep-sec", type=float, default=0.0, help="각 API 호출 사이 대기 시간")
    parser.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC, help="HTTP 타임아웃")
    parser.add_argument("--store", action="store_true", help="Responses API 결과 저장 활성화 (기본값은 false)")
    parser.add_argument("--reasoning-effort", choices=["none", "low", "medium", "high", "xhigh"], default="none", help="선택적 reasoning effort")
    parser.add_argument("--pretty", action="store_true", help="JSON pretty 출력")
    parser.add_argument("--dry-run", action="store_true", help="실제 API 호출 없이 요청 계획만 생성")
    return parser.parse_args()


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: str, payload: Any, pretty: bool) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2 if pretty else None)


def iso_now() -> str:
    return datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="milliseconds")


def normalize_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


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


def derive_base_name(input_path: str, explicit_base_name: Optional[str]) -> str:
    if explicit_base_name:
        return explicit_base_name
    return Path(input_path).stem.replace("_llm_input", "")


def build_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": [
                    "benign_normal",
                    "likely_false_positive",
                    "suspicious_scan",
                    "suspicious_bruteforce",
                    "suspicious_sqli",
                    "suspicious_xss",
                    "suspicious_path_traversal",
                    "suspicious_command_injection",
                    "suspicious_auth_abuse",
                    "server_error_probe",
                    "inconclusive",
                ],
            },
            "severity": {
                "type": "string",
                "enum": ["info", "low", "medium", "high", "critical"],
            },
            "confidence": {
                "type": "string",
                "enum": ["low", "medium", "high"],
            },
            "false_positive_possible": {"type": "boolean"},
            "reasoning_summary": {"type": "string", "minLength": 1},
            "evidence_fields": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 12,
            },
            "recommended_actions": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "ignore",
                        "watch",
                        "review_raw_log",
                        "review_error_log",
                        "correlate_request_id",
                        "correlate_src_ip",
                        "rate_limit_or_block",
                        "investigate_immediately",
                    ],
                },
                "minItems": 1,
                "maxItems": 4,
            },
        },
        "required": [
            "verdict",
            "severity",
            "confidence",
            "false_positive_possible",
            "reasoning_summary",
            "evidence_fields",
            "recommended_actions",
        ],
        "additionalProperties": False,
    }


def build_messages(meta: Dict[str, Any], candidate: Dict[str, Any], max_evidence_items: int) -> List[Dict[str, str]]:
    analysis_window = meta.get("analysis_window", {})
    system_prompt = (
        "당신은 웹 보안 로그 1차 분류기다. "
        "사전 필터링된 Apache/MariaDB 로그 후보 1건을 보수적으로 분류하라. "
        "제공된 필드만 근거로 사용하고 확신을 과장하지 마라. "
        "증거가 약하면 likely_false_positive 또는 inconclusive를 우선 고려하라. "
        "규칙 기반 힌트는 단서일 뿐 확정 증거가 아니다. "
        "반드시 schema-valid JSON 객체만 반환하라. "
        "verdict, severity, recommended_actions 같은 enum 값은 스키마에 정의된 영어 값을 그대로 사용하라. "
        "reasoning_summary 와 evidence_fields 의 자유서술 내용은 반드시 한국어로 작성하라. "
        "path traversal 의 경우 status_code 200 만으로 실제 파일 노출 성공을 암시하지 마라. "
        "resp_content_type 이 text/html 이고 HTML fallback 정황이 있으면 시도 탐지와 실제 노출 여부를 분리해서 서술하라. "
        "동일 파라미터가 반복되면 HTTP Parameter Pollution(HPP) 가능성을 검토하라. "
        "hpp_detected 가 true 이고 embedded_attack_hint 가 있으면, verdict 는 기존 SQLi/XSS 체계를 유지하되 reasoning_summary 와 evidence_fields 에 중복 파라미터(HPP) 문맥을 명시하라."
    )

    user_payload = {
        "policy": {
            "project_goal": "Apache 웹 로그를 기반으로 공격 징후를 선별하고 실험 보고에 활용하기 위한 1차 분류",
            "db_raw_preserved": bool(meta.get("pipeline_policy", {}).get("db_raw_preserved", True)),
            "send_raw_full_export_to_llm": bool(meta.get("pipeline_policy", {}).get("send_raw_full_export_to_llm", False)),
            "analysis_timezone": meta.get("query_timezone", "Asia/Seoul"),
            "response_language": "한국어",
        },
        "analysis_window": {
            "start": analysis_window.get("start"),
            "end_exclusive": analysis_window.get("end_exclusive"),
        },
        "candidate": {
            "source_table": candidate.get("source_table"),
            "incident_group_key": candidate.get("incident_group_key"),
            "merged_row_count": candidate.get("merged_row_count"),
            "merged_source_tables": candidate.get("merged_source_tables"),
            "merged_log_ids": candidate.get("merged_log_ids"),
            "log_id": candidate.get("log_id"),
            "log_time": candidate.get("log_time"),
            "src_ip": candidate.get("src_ip"),
            "method": candidate.get("method"),
            "uri": candidate.get("uri"),
            "query_string": candidate.get("query_string"),
            "status_code": candidate.get("status_code"),
            "score": candidate.get("score"),
            "verdict_hint": candidate.get("verdict_hint"),
            "reason_hints": (candidate.get("reason_hints") or [])[:max_evidence_items],
            "request_id": candidate.get("request_id"),
            "error_link_id": candidate.get("error_link_id"),
            "raw_request": candidate.get("raw_request"),
            "user_agent": candidate.get("user_agent"),
            "referer": candidate.get("referer"),
            "duration_us": candidate.get("duration_us"),
            "ttfb_us": candidate.get("ttfb_us"),
            "response_body_bytes": candidate.get("response_body_bytes"),
            "resp_content_type": candidate.get("resp_content_type"),
            "raw_request_target": candidate.get("raw_request_target"),
            "path_normalized_from_raw_request": candidate.get("path_normalized_from_raw_request"),
            "likely_html_fallback_response": candidate.get("likely_html_fallback_response"),
            "hpp_detected": candidate.get("hpp_detected"),
            "hpp_param_names": candidate.get("hpp_param_names"),
            "embedded_attack_hint": candidate.get("embedded_attack_hint"),
            "raw_log_excerpt": normalize_str(candidate.get("raw_log"))[:1200],
        },
        "label_guidance": {
            "benign_normal": "정상 트래픽이거나 일반적인 애플리케이션 동작으로 보는 것이 가장 타당한 경우.",
            "likely_false_positive": "규칙 기반 전처리가 의심 신호를 잡았지만, 제공된 증거만으로는 정상 가능성이 충분히 큰 경우.",
            "suspicious_scan": "정찰, 탐색, 스캐닝 성격의 행위로 보는 것이 가장 타당한 경우.",
            "suspicious_bruteforce": "인증 시도 반복이나 자격 증명 추측 행위로 보는 것이 가장 타당한 경우.",
            "suspicious_sqli": "SQL 인젝션 시도로 해석하는 것이 가장 타당한 경우.",
            "suspicious_xss": "XSS 시도로 해석하는 것이 가장 타당한 경우.",
            "suspicious_path_traversal": "경로 탐색 또는 파일 노출 시도로 해석하는 것이 가장 타당한 경우.",
            "suspicious_command_injection": "명령 실행 유도 시도로 해석하는 것이 가장 타당한 경우.",
            "suspicious_auth_abuse": "명확한 brute force 까지는 아니지만 인증 기능 오용 정황이 있는 경우.",
            "server_error_probe": "서버 또는 프록시 오류를 유발하거나 오류 경로를 탐색하는 행위로 보는 것이 가장 타당한 경우.",
            "inconclusive": "수상하긴 하지만 제공된 근거만으로 특정 클래스를 부여하기에는 부족한 경우.",
        },
        "severity_guidance": {
            "info": "운영상 무해하거나 정상 가능성이 매우 높은 수준.",
            "low": "신호가 약하거나 영향도가 낮은 의심 수준.",
            "medium": "악성 시도로 볼 만한 정황이 있으나 추가 확인이 필요한 수준.",
            "high": "공격 지표가 강하거나 사람이 즉시 검토해야 할 수준.",
            "critical": "악성 가능성이 매우 높고 즉시 대응이 필요한 수준.",
        },
        "action_guidance": [
            "ignore",
            "watch",
            "review_raw_log",
            "review_error_log",
            "correlate_request_id",
            "correlate_src_ip",
            "rate_limit_or_block",
            "investigate_immediately",
        ],
        "instructions": [
            "판단 근거는 제공된 필드에 한정하라.",
            "심각도는 필요한 최소 수준만 부여하라.",
            "query_string 이 비어 있고 근거가 status code 나 user agent 위주이면 과도하게 단정하지 마라.",
            "request_id 와 error_link_id 는 상관분석 단서일 뿐 공격의 확정 증거는 아니다.",
            "path traversal 은 raw_request 의 시도 정황과 실제 파일 노출 성공 여부를 분리해서 판단하라.",
            "status_code 가 200 이어도 resp_content_type 이 text/html 이고 likely_html_fallback_response 가 true 면 앱의 fallback HTML 반환 가능성을 우선 고려하라.",
            "response_body_bytes 와 resp_content_type 은 응답이 파일처럼 보이는지, HTML 페이지처럼 보이는지 판단하는 보조 근거로 사용하라.",
            "reasoning_summary 는 한국어로 1~3문장 이내로 간결하게 작성하라.",
            "evidence_fields 는 중요한 필드명이나 핵심 힌트를 한국어 짧은 구절로 적고, 긴 원문을 그대로 복사하지 마라.",
            "enum 값이 아닌 자유서술은 모두 한국어로 작성하라.",
        ],
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

    # 일부 응답 포맷에서는 output_text 가 평탄화되어 올 수 있어 보조적으로 확인
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
                "name": "stage1_log_triage",
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


def classify_candidate(
    api_key: str,
    base_url: str,
    model: str,
    meta: Dict[str, Any],
    candidate: Dict[str, Any],
    timeout_sec: int,
    store: bool,
    reasoning_effort: str,
    max_evidence_items: int,
    candidate_index: int,
) -> Tuple[Optional[Stage1Result], Optional[Stage1Error]]:
    request_id = normalize_str(candidate.get("request_id"))
    incident_group_key = normalize_str(candidate.get("incident_group_key"))

    try:
        messages = build_messages(meta, candidate, max_evidence_items=max_evidence_items)
        raw_response = call_responses_api(
            api_key=api_key,
            base_url=base_url,
            model=model,
            messages=messages,
            timeout_sec=timeout_sec,
            store=store,
            reasoning_effort=reasoning_effort,
        )
        output_text, response_id = extract_output_text(raw_response)
        if not output_text:
            return None, Stage1Error(
                candidate_index=candidate_index,
                request_id=request_id,
                model=model,
                error_type="empty_output",
                error_message="응답에서 output_text를 찾지 못했습니다.",
                response_id=response_id,
                raw_response_excerpt=json.dumps(raw_response, ensure_ascii=False)[:1500],
            )

        parsed = json.loads(output_text)
        result = Stage1Result(
            candidate_index=candidate_index,
            incident_group_key=incident_group_key,
            request_id=request_id,
            error_link_id=normalize_str(candidate.get("error_link_id")),
            model=model,
            source_table=normalize_str(candidate.get("source_table")),
            merged_source_tables=[normalize_str(x) for x in (candidate.get("merged_source_tables") or []) if normalize_str(x)],
            merged_row_count=int(candidate.get("merged_row_count") or 1),
            merged_log_ids=[int(x) for x in (candidate.get("merged_log_ids") or []) if str(x).strip()],
            log_id=candidate.get("log_id"),
            src_ip=normalize_str(candidate.get("src_ip")),
            method=normalize_str(candidate.get("method")),
            uri=normalize_str(candidate.get("uri")),
            query_string=normalize_str(candidate.get("query_string")),
            log_time=normalize_str(candidate.get("log_time")),
            status_code=int(candidate.get("status_code") or 0),
            score=int(candidate.get("score") or 0),
            verdict_hint=normalize_str(candidate.get("verdict_hint")),
            reason_hints=[normalize_str(x) for x in (candidate.get("reason_hints") or []) if normalize_str(x)],
            response_body_bytes=int(candidate.get("response_body_bytes") or 0),
            resp_content_type=normalize_str(candidate.get("resp_content_type")),
            raw_request_target=normalize_str(candidate.get("raw_request_target")),
            path_normalized_from_raw_request=bool(candidate.get("path_normalized_from_raw_request")),
            likely_html_fallback_response=bool(candidate.get("likely_html_fallback_response")),
            hpp_detected=bool(candidate.get("hpp_detected")),
            hpp_param_names=[normalize_str(x) for x in (candidate.get("hpp_param_names") or []) if normalize_str(x)],
            embedded_attack_hint=normalize_str(candidate.get("embedded_attack_hint")),
            verdict=normalize_str(parsed.get("verdict")),
            severity=normalize_str(parsed.get("severity")),
            confidence=normalize_str(parsed.get("confidence")),
            false_positive_possible=bool(parsed.get("false_positive_possible")),
            reasoning_summary=normalize_str(parsed.get("reasoning_summary")),
            evidence_fields=[normalize_str(x) for x in (parsed.get("evidence_fields") or []) if normalize_str(x)],
            recommended_actions=[normalize_str(x) for x in (parsed.get("recommended_actions") or []) if normalize_str(x)],
            response_id=response_id,
            raw_output_text=output_text,
        )
        return result, None

    except error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = ""
        return None, Stage1Error(
            candidate_index=candidate_index,
            request_id=request_id,
            model=model,
            error_type="http_error",
            error_message=f"HTTP {e.code}: {e.reason}",
            raw_response_excerpt=body[:1500],
        )
    except error.URLError as e:
        return None, Stage1Error(
            candidate_index=candidate_index,
            request_id=request_id,
            model=model,
            error_type="url_error",
            error_message=normalize_str(e.reason) or repr(e),
        )
    except json.JSONDecodeError as e:
        return None, Stage1Error(
            candidate_index=candidate_index,
            request_id=request_id,
            model=model,
            error_type="json_decode_error",
            error_message=str(e),
        )
    except Exception as e:  # pragma: no cover - 운영 예외 포착용
        return None, Stage1Error(
            candidate_index=candidate_index,
            request_id=request_id,
            model=model,
            error_type="unexpected_error",
            error_message=repr(e),
        )


def main() -> int:
    args = parse_args()
    payload = load_json(args.input)

    if "analysis_candidates" not in payload or "meta" not in payload:
        print("[ERROR] 입력 JSON 형식이 올바르지 않습니다. prepare_llm_input.py 결과 파일인지 확인하세요.", file=sys.stderr)
        return 2

    selected_model = choose_model(args.mode, args.model)
    base_name = derive_base_name(args.input, args.base_name)
    out_dir = Path(args.out_dir)
    results_path = out_dir / f"{base_name}_stage1_results.json"
    errors_path = out_dir / f"{base_name}_stage1_errors.json"

    candidates: List[Dict[str, Any]] = payload.get("analysis_candidates") or []
    if args.candidate_limit and args.candidate_limit > 0:
        candidates = candidates[: args.candidate_limit]

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL

    meta = payload.get("meta") or {}

    if args.dry_run:
        dry_payload = {
            "meta": {
                "generated_at": iso_now(),
                "input_file": os.path.abspath(args.input),
                "mode": args.mode,
                "selected_model": selected_model,
                "candidate_count": len(candidates),
                "source_counts": meta.get("counts"),
                "candidate_group_summary_count": len(payload.get("candidate_group_summary") or []),
                "store": bool(args.store),
                "reasoning_effort": args.reasoning_effort,
                "base_url": base_url,
            },
            "candidates_preview": [
                {
                    "candidate_index": idx,
                    "incident_group_key": normalize_str(c.get("incident_group_key")),
                    "merged_row_count": int(c.get("merged_row_count") or 1),
                    "merged_source_tables": [normalize_str(x) for x in (c.get("merged_source_tables") or []) if normalize_str(x)],
                    "request_id": normalize_str(c.get("request_id")),
                    "src_ip": normalize_str(c.get("src_ip")),
                    "method": normalize_str(c.get("method")),
                    "uri": normalize_str(c.get("uri")),
                    "score": c.get("score"),
                    "verdict_hint": c.get("verdict_hint"),
                }
                for idx, c in enumerate(candidates)
            ],
        }
        dump_json(str(results_path), dry_payload, pretty=args.pretty)
        print(f"[OK] dry-run plan: {results_path}")
        return 0

    if not api_key:
        print("[ERROR] OPENAI_API_KEY 환경 변수가 필요합니다.", file=sys.stderr)
        return 2

    results: List[Dict[str, Any]] = []
    errors_out: List[Dict[str, Any]] = []

    for idx, candidate in enumerate(candidates):
        result, err = classify_candidate(
            api_key=api_key,
            base_url=base_url,
            model=selected_model,
            meta=meta,
            candidate=candidate,
            timeout_sec=args.timeout_sec,
            store=bool(args.store),
            reasoning_effort=args.reasoning_effort,
            max_evidence_items=args.max_evidence_items,
            candidate_index=idx,
        )
        if result:
            results.append(asdict(result))
            print(
                f"[OK] idx={idx} request_id={result.request_id or '-'} "
                f"verdict={result.verdict} severity={result.severity} confidence={result.confidence}"
            )
        if err:
            errors_out.append(asdict(err))
            print(
                f"[WARN] idx={idx} request_id={err.request_id or '-'} "
                f"type={err.error_type} msg={err.error_message}",
                file=sys.stderr,
            )
        if args.sleep_sec > 0 and idx < len(candidates) - 1:
            time.sleep(args.sleep_sec)

    result_payload = {
        "meta": {
            "generated_at": iso_now(),
            "input_file": os.path.abspath(args.input),
            "mode": args.mode,
            "selected_model": selected_model,
            "store": bool(args.store),
            "reasoning_effort": args.reasoning_effort,
            "base_url": base_url,
            "source_window": meta.get("analysis_window"),
            "source_query_timezone": meta.get("query_timezone"),
            "source_exported_at": meta.get("exported_at"),
            "source_prepared_at": meta.get("prepared_at"),
            "source_counts": meta.get("counts"),
            "candidate_group_summary_count": len(payload.get("candidate_group_summary") or []),
            "preserved_candidate_identity_fields": [
                "incident_group_key",
                "merged_row_count",
                "merged_source_tables",
                "merged_log_ids",
                "method",
                "query_string",
                "verdict_hint",
                "reason_hints",
                "error_link_id",
                "response_body_bytes",
                "resp_content_type",
                "raw_request_target",
                "path_normalized_from_raw_request",
                "likely_html_fallback_response",
            ],
            "processed_candidate_count": len(candidates),
            "success_count": len(results),
            "error_count": len(errors_out),
        },
        "results": results,
    }

    dump_json(str(results_path), result_payload, pretty=args.pretty)
    dump_json(str(errors_path), {"errors": errors_out}, pretty=args.pretty)

    print(f"[OK] stage1_results: {results_path}")
    print(f"[OK] stage1_errors:  {errors_path}")
    return 0 if not errors_out else 1


if __name__ == "__main__":
    raise SystemExit(main())
