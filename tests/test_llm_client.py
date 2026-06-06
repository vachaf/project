from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from llm_client import LLMResponse, combine_llm_usage, normalize_llm_usage


def test_normalize_openai_usage_includes_cached_and_reasoning_breakdown() -> None:
    response = LLMResponse(
        output_text="{}",
        response_id="resp_1",
        raw_response={
            "id": "resp_1",
            "usage": {
                "input_tokens": 32,
                "input_tokens_details": {"cached_tokens": 7},
                "output_tokens": 18,
                "output_tokens_details": {"reasoning_tokens": 5},
                "total_tokens": 50,
            },
        },
        provider="openai",
        model="gpt-test",
    )

    usage = normalize_llm_usage(response, call_role="stage1_candidate")

    assert usage["schema_version"] == "llm_usage.v1"
    assert usage["available"] is True
    assert usage["provider"] == "openai"
    assert usage["model"] == "gpt-test"
    assert usage["response_id"] == "resp_1"
    assert usage["call_role"] == "stage1_candidate"
    assert usage["input_tokens"] == 32
    assert usage["output_tokens"] == 18
    assert usage["total_tokens"] == 50
    assert usage["estimated"] is False
    assert usage["breakdown"]["cached_input_tokens"] == 7
    assert usage["breakdown"]["reasoning_tokens"] == 5
    assert usage["provider_usage"]["input_tokens"] == 32


def test_normalize_anthropic_usage_counts_cache_input_tokens() -> None:
    response = LLMResponse(
        output_text="{}",
        response_id="msg_1",
        raw_response={
            "id": "msg_1",
            "usage": {
                "input_tokens": 410,
                "cache_creation_input_tokens": 11,
                "cache_read_input_tokens": 13,
                "output_tokens": 585,
                "service_tier": "standard",
            },
        },
        provider="anthropic",
        model="claude-test",
    )

    usage = normalize_llm_usage(response, call_role="stage2_report")

    assert usage["available"] is True
    assert usage["provider"] == "anthropic"
    assert usage["input_tokens"] == 410
    assert usage["total_input_tokens"] == 434
    assert usage["output_tokens"] == 585
    assert usage["total_tokens"] == 1019
    assert usage["breakdown"]["cache_creation_input_tokens"] == 11
    assert usage["breakdown"]["cache_read_input_tokens"] == 13
    assert usage["breakdown"]["service_tier"] == "standard"


def test_normalize_missing_usage_is_unavailable() -> None:
    response = LLMResponse(
        output_text="{}",
        response_id="resp_missing",
        raw_response={"id": "resp_missing"},
        provider="openai",
        model="gpt-test",
    )

    usage = normalize_llm_usage(response, call_role="stage1_candidate")

    assert usage == {
        "schema_version": "llm_usage.v1",
        "available": False,
        "provider": "openai",
        "model": "gpt-test",
        "response_id": "resp_missing",
        "call_role": "stage1_candidate",
        "estimated": False,
        "unavailable_reason": "provider_usage_missing",
    }


def test_combine_llm_usage_sums_available_by_provider_and_counts_unavailable() -> None:
    totals = combine_llm_usage(
        [
            {
                "available": True,
                "provider": "openai",
                "model": "gpt-a",
                "input_tokens": 10,
                "output_tokens": 3,
                "total_tokens": 13,
                "estimated": False,
            },
            {
                "available": True,
                "provider": "anthropic",
                "model": "claude-a",
                "input_tokens": 20,
                "output_tokens": 5,
                "total_tokens": 25,
                "estimated": False,
            },
            {
                "available": False,
                "provider": "openai",
                "model": "gpt-a",
                "unavailable_reason": "provider_usage_missing",
            },
        ]
    )

    assert totals["schema_version"] == "llm_usage_totals.v1"
    assert totals["available"] is True
    assert totals["call_count"] == 2
    assert totals["input_tokens"] == 30
    assert totals["output_tokens"] == 8
    assert totals["total_tokens"] == 38
    assert totals["estimated"] is False
    assert totals["by_provider"]["openai"]["call_count"] == 1
    assert totals["by_provider"]["anthropic"]["total_tokens"] == 25
    assert totals["unavailable_count"] == 1
    assert totals["unavailable_reasons"] == {"provider_usage_missing": 1}
