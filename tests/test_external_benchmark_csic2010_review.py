from __future__ import annotations

import json
from pathlib import Path

from src.external_benchmark_csic2010_review import (
    review_agreement_category,
    review_requires_adjudication,
    stage1_eligible_canonical_case,
    validation_queue_identity_sets,
    validate_reviewed_manifest,
    validation_review_view,
)


def _review(**overrides):
    value = {
        "project_semantic": "project_attack_positive",
        "reviewed_family": "sqli",
        "classification_policy": "exact",
        "allowed_stage1_verdicts": ["suspicious_sqli"],
        "review_confidence": "high",
        "validation_confidence": "high",
    }
    value.update(overrides)
    return value


def test_validation_view_is_blind_to_source_prepare_and_provisional_fields() -> None:
    row = {
        "source_file": "normalTrafficTraining.txt",
        "request_index": 9,
        "raw_request_sha256": "a" * 64,
        "method": "POST",
        "request_line": "POST http://example.test/a?x=1 HTTP/1.1",
        "headers_present": ["Host", "Content-Type", "Content-Length", "Cookie"],
        "body_for_observability_review": "body-only",
        "source_label": "source_normal",
        "sampling_pool": "selected_source_normal",
        "selected": True,
        "score": 99,
        "verdict_hint": "sqli",
        "reason_hints": ["hidden"],
        "filtered_reasons": ["hidden"],
        "project_semantic": "project_attack_positive",
        "reviewed_family": "sqli",
        "classification_policy": "exact",
        "rationale": "hidden",
        "review_confidence": "high",
    }
    view = validation_review_view(row)

    assert view["case_token"] == "a" * 64
    assert view["raw_request_target"] == "http://example.test/a?x=1"
    assert view["uri"] == "/a"
    assert view["query_string"] == "?x=1"
    assert view["body_present"] is True
    assert view["content_type_metadata"] == "present"
    assert view["content_length_metadata"] == "present"
    serialized = json.dumps(view, sort_keys=True)
    for forbidden in ("source_file", "source_label", "sampling_pool", "selected", "score", "verdict_hint", "reason_hints", "filtered_reasons", "project_semantic", "reviewed_family", "classification_policy", "rationale", "review_confidence", "body-only"):
        assert forbidden not in serialized


def test_comparison_categories_and_adjudication_routing() -> None:
    first = _review()
    assert review_agreement_category(first, _review()) == "full_agreement"
    assert not review_requires_adjudication(first, _review())

    policy = _review(classification_policy="compatible_set")
    assert review_agreement_category(first, policy) == "semantic_agreement_policy_disagreement"
    assert review_requires_adjudication(first, policy)

    family = _review(reviewed_family="xss", allowed_stage1_verdicts=["suspicious_xss"])
    assert review_agreement_category(first, family) == "family_disagreement"

    not_scored = _review(project_semantic="not_scored_observability", reviewed_family=None, classification_policy="not_scored", allowed_stage1_verdicts=[])
    assert review_agreement_category(first, not_scored) == "observability_disagreement"

    low = _review(validation_confidence="low")
    assert review_requires_adjudication(first, low)


def test_validation_queue_identity_union_is_deduplicated_and_overlap_explicit() -> None:
    primary = [
        {"identity": {"source_file": "one", "request_index": 1, "raw_request_sha256": "a"}},
        {"identity": {"source_file": "one", "request_index": 2, "raw_request_sha256": "b"}},
    ]
    audit = {
        "post_body": [{"source_file": "two", "request_index": 3, "raw_request_sha256": "c"}],
        "put_body": [{"source_file": "one", "request_index": 2, "raw_request_sha256": "b"}],
    }
    sets = validation_queue_identity_sets(primary, audit)

    assert len(sets["primary"]) == 2
    assert len(sets["audit"]) == 2
    assert sets["overlap"] == {("one", 2, "b")}
    assert len(sets["union"]) == 3


def test_stage1_eligibility_excludes_unvalidated_and_nonselected_records() -> None:
    eligible = _review(review_status="validated_agreement", prepare_selected=True)
    assert stage1_eligible_canonical_case(eligible)
    assert not stage1_eligible_canonical_case(_review(review_status="provisional_unvalidated", prepare_selected=True))
    assert not stage1_eligible_canonical_case(_review(review_status="adjudicated", prepare_selected=False))
    assert not stage1_eligible_canonical_case(_review(review_status="adjudicated", prepare_selected=True, project_semantic="project_negative", reviewed_family=None, classification_policy="forbidden_only", allowed_stage1_verdicts=[]))


def test_canonical_manifest_has_no_raw_source_content_and_is_valid() -> None:
    path = Path("benchmarks/manifests/csic2010_reviewed_semantic_subset.v1.json")
    manifest = json.loads(path.read_text(encoding="utf-8"))

    assert len(manifest["cases"]) == 222
    assert validate_reviewed_manifest(manifest) == []
    serialized = json.dumps(manifest, ensure_ascii=False)
    for forbidden in ("body_for_observability_review", "request_line", "Cookie:", "Authorization:"):
        assert forbidden not in serialized
