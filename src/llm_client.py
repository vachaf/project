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


def normalize_provider(value: Optional[str]) -> str:
    provider = (value or os.getenv("LLM_PROVIDER") or "openai").strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"unsupported provider: {provider} (supported: {', '.join(SUPPORTED_PROVIDERS)})")
    return provider


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
    return LLMResponse(output_text=output_text, response_id=response_id, raw_response=raw_response)


def call_anthropic_messages(
    config: LLMConfig,
    model: str,
    messages: List[Dict[str, str]],
    schema: Dict[str, Any],
    schema_name: str,
    timeout_sec: int,
) -> LLMResponse:
    system_text, anthropic_messages = split_system_messages(messages)
    schema_instruction = (
        "\n\nReturn only one JSON object. Do not wrap it in Markdown. "
        f"The JSON object must satisfy this JSON Schema named {schema_name}: "
        + json.dumps(schema, ensure_ascii=False)
    )
    body: Dict[str, Any] = {
        "model": model,
        "max_tokens": 4096,
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
    return LLMResponse(output_text=output_text, response_id=response_id, raw_response=raw_response)


def call_llm_json(
    config: LLMConfig,
    model: str,
    messages: List[Dict[str, str]],
    schema: Dict[str, Any],
    schema_name: str,
    timeout_sec: int,
    store: bool,
    reasoning_effort: str,
) -> LLMResponse:
    if config.provider == "anthropic":
        return call_anthropic_messages(
            config=config,
            model=model,
            messages=messages,
            schema=schema,
            schema_name=schema_name,
            timeout_sec=timeout_sec,
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
