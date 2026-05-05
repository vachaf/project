from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import check_stage2_report_quality as lint


def wrap_report(report: object) -> dict:
    return {"report": report}


def make_minimal_report(text: str, *, field: str = "overall_assessment") -> dict:
    report = {
        "report_title": "테스트 보고서",
        "overall_assessment": "안전한 요약",
        "executive_summary": ["요약 1", "요약 2", "요약 3"],
        "key_findings": [
            {"title": "포인트 1", "detail": "상세 1", "severity": "low"},
            {"title": "포인트 2", "detail": "상세 2", "severity": "low"},
            {"title": "포인트 3", "detail": "상세 3", "severity": "low"},
        ],
        "notable_incidents": [
            {
                "incident_ref": "inc-1",
                "request_id": "req-1",
                "src_ip": "192.168.56.1",
                "verdict": "suspicious",
                "severity": "low",
                "why_it_matters": "보수적 설명",
            }
        ],
        "notable_source_ips": [{"src_ip": "192.168.56.1", "reason": "내부 자산 가능성"}],
        "noise_interpretation": "저신호 요청이 섞여 있다.",
        "recommended_actions": [
            {"priority": "P1", "action": "로그 확인", "why": "근거 보강"},
            {"priority": "P2", "action": "소유자 확인", "why": "내부 테스트 여부 확인"},
            {"priority": "P3", "action": "모니터링 유지", "why": "재발 확인"},
        ],
        "confidence_and_limitations": ["Apache 로그만으로 성공을 단정하지 않는다."],
        "presentation_takeaway": "현재 증거는 시도 정황 중심이다.",
    }
    if field == "overall_assessment":
        report[field] = text
    elif field == "key_findings.detail":
        report["key_findings"][1]["detail"] = text
    elif field == "recommended_actions.why":
        report["recommended_actions"][0]["why"] = text
    else:
        raise ValueError(f"unsupported field: {field}")
    return report


def test_report_null_is_handled() -> None:
    result = lint.analyze_stage2_report_data(wrap_report(None))
    assert result["verdict"] == "PASS"
    assert result["summary"]["checked_fields"] == 0
    assert result["summary"]["blocker_count"] == 0
    assert result["summary"]["warning_count"] == 0


def test_negated_file_disclosure_downgrades() -> None:
    report = make_minimal_report("파일 내용 노출 성공은 확인할 수 없습니다.")
    result = lint.analyze_stage2_report_data(wrap_report(report))
    assert result["summary"]["blocker_count"] == 0
    assert result["summary"]["info_count"] >= 1
    assert any(issue["rule"] == "file_disclosure_success_assertion" for issue in result["warnings"] + result["info"])


def test_safe_auth_negation_is_not_blocker() -> None:
    report = make_minimal_report("로그인 성공은 확인되지 않았습니다")
    result = lint.analyze_stage2_report_data(wrap_report(report))
    assert result["summary"]["blocker_count"] == 0
    assert result["summary"]["warning_count"] == 0
    assert result["summary"]["info_count"] >= 1


def test_safe_account_takeover_negation_is_not_blocker() -> None:
    report = make_minimal_report("계정 탈취로는 해석하지 않았습니다")
    result = lint.analyze_stage2_report_data(wrap_report(report))
    assert result["summary"]["blocker_count"] == 0


def test_safe_xss_negation_is_not_blocker() -> None:
    report = make_minimal_report("XSS 실행 성공으로 해석할 수 있는 증거는 제공되지 않았습니다")
    result = lint.analyze_stage2_report_data(wrap_report(report))
    assert result["summary"]["blocker_count"] == 0


def test_report_level_non_assertion_claim_is_not_blocker() -> None:
    report = make_minimal_report(
        "후보 사건이 0건이므로 확정된 침해, 파일 노출, 인증 성공, 외부 전송 성공 등은 본 보고서에서 주장하지 않았습니다"
    )
    result = lint.analyze_stage2_report_data(wrap_report(report))
    assert result["summary"]["blocker_count"] == 0


def test_weak_possibility_stays_warning() -> None:
    report = make_minimal_report("HTTP 200 응답은 로그인 성공 가능성을 시사합니다")
    result = lint.analyze_stage2_report_data(wrap_report(report))
    assert result["summary"]["blocker_count"] == 0
    assert result["summary"]["warning_count"] >= 1


def test_recommended_action_check_is_not_blocker() -> None:
    report = make_minimal_report("브라우저 XSS 실행 여부 확인이 필요합니다", field="recommended_actions.why")
    result = lint.analyze_stage2_report_data(wrap_report(report))
    assert result["summary"]["blocker_count"] == 0
    assert result["summary"]["warning_count"] + result["summary"]["info_count"] >= 1


def test_risky_file_disclosure_assertion_is_blocker() -> None:
    report = make_minimal_report("config 파일 내용이 반환됐다.")
    result = lint.analyze_stage2_report_data(wrap_report(report))
    assert result["summary"]["blocker_count"] >= 1
    assert any(issue["rule"] == "file_disclosure_success_assertion" for issue in result["blockers"])


def test_risky_xss_assertion_is_blocker() -> None:
    report = make_minimal_report("브라우저에서 스크립트가 실행되어 쿠키가 탈취됐다.")
    result = lint.analyze_stage2_report_data(wrap_report(report))
    assert result["summary"]["blocker_count"] >= 1
    assert any(issue["rule"] == "xss_execution_assertion" for issue in result["blockers"])


def test_risky_sqli_assertion_is_blocker() -> None:
    report = make_minimal_report("SQL injection 성공으로 DB 결과가 반환됐다.")
    result = lint.analyze_stage2_report_data(wrap_report(report))
    assert result["summary"]["blocker_count"] >= 1
    assert any(issue["rule"] == "sql_success_assertion" for issue in result["blockers"])


def test_ip_attribution_is_warning_or_blocker_candidate() -> None:
    report = make_minimal_report("공격자 IP 192.168.56.1")
    result = lint.analyze_stage2_report_data(wrap_report(report))
    assert result["summary"]["warning_count"] + result["summary"]["blocker_count"] >= 1
    assert any(
        issue["rule"] == "ip_ua_attribution_assertion"
        for issue in result["warnings"] + result["blockers"] + result["info"]
    )


def test_key_findings_detail_is_checked() -> None:
    report = make_minimal_report("SQL injection 성공으로 DB 결과가 반환됐다.", field="key_findings.detail")
    result = lint.analyze_stage2_report_data(wrap_report(report))
    assert any(issue["path"].startswith("report.key_findings[1].detail") for issue in result["blockers"])


def test_cli_fail_on_blocker_changes_exit_code(tmp_path: Path) -> None:
    input_path = tmp_path / "stage2_report.json"
    payload = wrap_report(make_minimal_report("config 파일 내용이 반환됐다."))
    input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    command = [sys.executable, "scripts/check_stage2_report_quality.py", "--input", str(input_path)]
    normal = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], check=False)
    assert normal.returncode == 0

    strict = subprocess.run(command + ["--fail-on-blocker"], cwd=Path(__file__).resolve().parents[1], check=False)
    assert strict.returncode != 0
