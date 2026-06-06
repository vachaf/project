#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal provider-aware LLM HTTP client for OpenAI and Anthropic."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib import request

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"
SUPPORTED_PROVIDERS = ("openai", "anthropic")


@dataclass
class LLMConfig:
    provider: str
    api_key: str
    base_url: str


@dataclass
class LLMResponse:
    output_text: str
    response_id: Optional[str]
    raw_response: Dict[str, Any]
    provider: str
    model: str
    stop_reason: Optional[str] = None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_provider(value: Optional[str]) -> str:
    provider = (value or os.getenv("LLM_PROVIDER") or "openai").strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"unsupported provider: {provider} (supported: {', '.join(SUPPORTED_PROVIDERS)})")
    return provider


def _missing_usage_payload(response: LLMResponse, *, call_role: str, reason: str) -> Dict[str, Any]:
    return {
        "schema_version": "llm_usage.v1",
        "available": False,
        "provider": response.provider,
        "model": response.model,
        "response_id": response.response_id,
        "call_role": call_role,
        "estimated": False,
        "unavailable_reason": reason,
    }


def normalize_llm_usage(response: LLMResponse, *, call_role: str) -> Dict[str, Any]:
    raw_response = response.raw_response
    if not isinstance(raw_response, dict):
        return _missing_usage_payload(response, call_role=call_role, reason="provider_usage_missing")

    raw_usage = raw_response.get("usage")
    if not isinstance(raw_usage, dict):
        return _missing_usage_payload(response, call_role=call_role, reason="provider_usage_missing")

    payload: Dict[str, Any] = {
        "schema_version": "llm_usage.v1",
        "available": True,
        "provider": response.provider,
        "model": response.model,
        "response_id": response.response_id,
        "call_role": call_role,
        "estimated": False,
        "breakdown": {},
        "provider_usage": dict(raw_usage),
    }

    if response.provider == "openai":
        input_tokens = _safe_int(raw_usage.get("input_tokens"))
        output_tokens = _safe_int(raw_usage.get("output_tokens"))
        total_tokens = _safe_int(raw_usage.get("total_tokens"), input_tokens + output_tokens)
        input_details = raw_usage.get("input_tokens_details")
        output_details = raw_usage.get("output_tokens_details")
        breakdown = {
            "cached_input_tokens": _safe_int(input_details.get("cached_tokens")) if isinstance(input_details, dict) else 0,
            "reasoning_tokens": _safe_int(output_details.get("reasoning_tokens")) if isinstance(output_details, dict) else 0,
        }
        payload.update(
            {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "breakdown": breakdown,
            }
        )
        return payload

    if response.provider == "anthropic":
        input_tokens = _safe_int(raw_usage.get("input_tokens"))
        output_tokens = _safe_int(raw_usage.get("output_tokens"))
        cache_creation_input_tokens = _safe_int(raw_usage.get("cache_creation_input_tokens"))
        cache_read_input_tokens = _safe_int(raw_usage.get("cache_read_input_tokens"))
        total_input_tokens = input_tokens + cache_creation_input_tokens + cache_read_input_tokens
        breakdown = {
            "cache_creation_input_tokens": cache_creation_input_tokens,
            "cache_read_input_tokens": cache_read_input_tokens,
        }
        if raw_usage.get("service_tier") is not None:
            breakdown["service_tier"] = raw_usage.get("service_tier")
        payload.update(
            {
                "input_tokens": input_tokens,
                "total_input_tokens": total_input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_input_tokens + output_tokens,
                "breakdown": breakdown,
            }
        )
        return payload

    return _missing_usage_payload(response, call_role=call_role, reason="unsupported_provider_usage")


def combine_llm_usage(usages: List[Dict[str, Any]]) -> Dict[str, Any]:
    available_usages = [usage for usage in usages if isinstance(usage, dict) and usage.get("available") is True]
    unavailable_usages = [usage for usage in usages if isinstance(usage, dict) and usage.get("available") is not True]
    by_provider: Dict[str, Dict[str, int]] = {}
    totals = {
        "schema_version": "llm_usage_totals.v1",
        "available": bool(available_usages),
        "call_count": len(available_usages),
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated": False,
        "by_provider": by_provider,
        "unavailable_count": len(unavailable_usages),
        "unavailable_reasons": {},
    }
    if available_usages:
        first = available_usages[0]
        totals["provider"] = first.get("provider")
        totals["selected_model"] = first.get("model")

    for usage in available_usages:
        provider = str(usage.get("provider") or "unknown")
        provider_bucket = by_provider.setdefault(
            provider,
            {
                "call_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            },
        )
        input_tokens = _safe_int(usage.get("input_tokens"))
        output_tokens = _safe_int(usage.get("output_tokens"))
        total_tokens = _safe_int(usage.get("total_tokens"), input_tokens + output_tokens)
        totals["input_tokens"] += input_tokens
        totals["output_tokens"] += output_tokens
        totals["total_tokens"] += total_tokens
        provider_bucket["call_count"] += 1
        provider_bucket["input_tokens"] += input_tokens
        provider_bucket["output_tokens"] += output_tokens
        provider_bucket["total_tokens"] += total_tokens
        if usage.get("estimated"):
            totals["estimated"] = True

    unavailable_reasons: Dict[str, int] = {}
    for usage in unavailable_usages:
        reason = str(usage.get("unavailable_reason") or "unknown")
        unavailable_reasons[reason] = unavailable_reasons.get(reason, 0) + 1
    totals["unavailable_reasons"] = unavailable_reasons
    return totals


def resolve_llm_config(provider_value: Optional[str]) -> LLMConfig:
    provider = normalize_provider(provider_value)
    if provider == "openai":
        return LLMConfig(
            provider=provider,
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            base_url=os.getenv("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL).strip() or DEFAULT_OPENAI_BASE_URL,
        )
    return LLMConfig(
        provider=provider,
        api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        base_url=os.getenv("ANTHROPIC_BASE_URL", DEFAULT_ANTHROPIC_BASE_URL).strip() or DEFAULT_ANTHROPIC_BASE_URL,
    )


def provider_api_key_error(provider: str) -> str:
    if provider == "anthropic":
        return "ANTHROPIC_API_KEY 환경 변수가 필요합니다."
    return "OPENAI_API_KEY 환경 변수가 필요합니다."


def extract_openai_output_text(response_payload: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    response_id = str(response_payload.get("id") or "").strip() or None
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
        return clean_output_text("".join(chunks)), response_id

    maybe_output_text = response_payload.get("output_text")
    if isinstance(maybe_output_text, str) and maybe_output_text.strip():
        return clean_output_text(maybe_output_text), response_id

    return "", response_id


def extract_anthropic_output_text(response_payload: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    response_id = str(response_payload.get("id") or "").strip() or None
    chunks: List[str] = []

    for content in response_payload.get("content") or []:
        if not isinstance(content, dict):
            continue
        if content.get("type") == "text" and "text" in content:
            chunks.append(str(content.get("text", "")))

    return clean_output_text("".join(chunks)), response_id


def clean_output_text(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def resolve_anthropic_max_tokens(override: Optional[int] = None) -> int:
    if override is not None:
        return override
    raw_value = os.getenv("ANTHROPIC_MAX_TOKENS", "").strip()
    if not raw_value:
        return 4096
    try:
        value = int(raw_value)
    except ValueError as e:
        raise ValueError("ANTHROPIC_MAX_TOKENS must be an integer") from e
    if value <= 0:
        raise ValueError("ANTHROPIC_MAX_TOKENS must be greater than 0")
    return value


def split_system_messages(messages: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, str]]]:
    system_chunks: List[str] = []
    user_messages: List[Dict[str, str]] = []
    for message in messages:
        role = message.get("role") or "user"
        content = message.get("content") or ""
        if role == "system":
            system_chunks.append(content)
        else:
            user_messages.append({"role": role, "content": content})
    return "\n\n".join(system_chunks), user_messages


def call_openai_responses(
    config: LLMConfig,
    model: str,
    messages: List[Dict[str, str]],
    schema: Dict[str, Any],
    schema_name: str,
    timeout_sec: int,
    store: bool,
    reasoning_effort: str,
) -> LLMResponse:
    body: Dict[str, Any] = {
        "model": model,
        "input": messages,
        "store": store,
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        },
    }
    if reasoning_effort != "none":
        body["reasoning"] = {"effort": reasoning_effort}

    req = request.Request(
        config.base_url.rstrip("/") + "/responses",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
    )
    with request.urlopen(req, timeout=timeout_sec) as resp:
        raw_response = json.loads(resp.read().decode("utf-8"))
    output_text, response_id = extract_openai_output_text(raw_response)
    return LLMResponse(
        output_text=output_text,
        response_id=response_id,
        raw_response=raw_response,
        provider=config.provider,
        model=model,
        stop_reason=response_payload_stop_reason(raw_response),
    )


def call_anthropic_messages(
    config: LLMConfig,
    model: str,
    messages: List[Dict[str, str]],
    schema: Dict[str, Any],
    schema_name: str,
    timeout_sec: int,
    max_tokens: Optional[int] = None,
) -> LLMResponse:
    system_text, anthropic_messages = split_system_messages(messages)
    schema_instruction = (
        "\n\nReturn only one JSON object. Do not wrap it in Markdown. "
        f"The JSON object must satisfy this JSON Schema named {schema_name}: "
        + json.dumps(schema, ensure_ascii=False)
    )
    body: Dict[str, Any] = {
        "model": model,
        "max_tokens": resolve_anthropic_max_tokens(max_tokens),
        "messages": anthropic_messages,
        "system": (system_text + schema_instruction).strip(),
    }

    req = request.Request(
        config.base_url.rstrip("/") + "/messages",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "x-api-key": config.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )
    with request.urlopen(req, timeout=timeout_sec) as resp:
        raw_response = json.loads(resp.read().decode("utf-8"))
    output_text, response_id = extract_anthropic_output_text(raw_response)
    return LLMResponse(
        output_text=output_text,
        response_id=response_id,
        raw_response=raw_response,
        provider=config.provider,
        model=model,
        stop_reason=response_payload_stop_reason(raw_response),
    )


def response_payload_stop_reason(response_payload: Dict[str, Any]) -> Optional[str]:
    stop_reason = response_payload.get("stop_reason")
    if stop_reason is None:
        return None
    return str(stop_reason).strip() or None


def call_llm_json(
    config: LLMConfig,
    model: str,
    messages: List[Dict[str, str]],
    schema: Dict[str, Any],
    schema_name: str,
    timeout_sec: int,
    store: bool,
    reasoning_effort: str,
    anthropic_max_tokens: Optional[int] = None,
) -> LLMResponse:
    if config.provider == "anthropic":
        return call_anthropic_messages(
            config=config,
            model=model,
            messages=messages,
            schema=schema,
            schema_name=schema_name,
            timeout_sec=timeout_sec,
            max_tokens=anthropic_max_tokens,
        )
    return call_openai_responses(
        config=config,
        model=model,
        messages=messages,
        schema=schema,
        schema_name=schema_name,
        timeout_sec=timeout_sec,
        store=store,
        reasoning_effort=reasoning_effort,
    )
