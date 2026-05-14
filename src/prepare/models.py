from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Candidate:
    source_table: str
    log_id: Optional[int]
    log_time: Optional[str]
    src_ip: str
    method: str
    uri: str
    query_string: str
    status_code: int
    score: int
    verdict_hint: str
    reason_hints: List[str]
    request_id: str
    error_link_id: str
    raw_request: str
    user_agent: str
    referer: str
    duration_us: int
    ttfb_us: int
    raw_log: str
    handler: str
    log_schema: str
    response_body_bytes: int
    resp_content_type: str
    raw_request_target: str
    path_normalized_from_raw_request: bool
    likely_html_fallback_response: bool
    hpp_detected: bool
    hpp_param_names: List[str]
    embedded_attack_hint: str
    incident_group_key: str = ""
    merged_row_count: int = 1
    merged_source_tables: List[str] = field(default_factory=list)
    merged_log_ids: List[int] = field(default_factory=list)


@dataclass
class NoiseAggregate:
    category: str
    src_ip: str
    uri: str
    method: str
    status_code: int
    count: int
    start: Optional[str]
    end: Optional[str]
    user_agent: str
    note: str
