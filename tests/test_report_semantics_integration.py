"""v0.07 보고서 의미 보존과 전달 경로의 모의 회귀 검사."""
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import llm_stage1_classifier as stage1
import llm_stage2_reporter as stage2
import viewer_payload_builder as viewer
from llm_client import LLMResponse
from scripts import check_stage2_report_quality as lint
from web.services import qa_runner


@pytest.mark.parametrize('text', [
    '분석가는 "첫 문장입니다. 403으로 차단되었습니다. 마지막 문장입니다."라고 말했습니다.',
    '무해하지 않은 것은 아닙니다.',
    '이 요청은 무해합니다만 공격 성공 여부는 확인되지 않습니다.',
    '403으로 차단되었습니다만 공격 성공 여부는 확인되지 않습니다.',
])
def test_ambiguous_and_quoted_claims_survive_every_postprocessor(text):
    sanitized, notes = stage2.sanitize_report_json_text({'overall_assessment': text})
    validated, _ = stage2.validate_http_status_report_semantics(sanitized, {})
    processed, warnings = stage2.postprocess_report_json({'overall_assessment': text}, {})
    assert sanitized == validated == processed == {'overall_assessment': text}
    assert notes == warnings
    result = lint.analyze_stage2_report_data({'report': processed, 'meta': {'guardrail_warnings': warnings}})
    assert result['verdict'] == 'WARN'
    assert any(row['source_text'] == text for row in result['warnings'])


@pytest.mark.parametrize('text', ['정상 동작을 입증할 수 없습니다.', '공격 성공 여부는 확인되지 않습니다.'])
def test_clear_uncertainty_does_not_create_safety_warning(text):
    report, warnings = stage2.postprocess_report_json({'overall_assessment': text}, {})
    assert report['overall_assessment'] == text
    assert warnings == []
    assert lint.analyze_stage2_report_data({'report': report})['verdict'] == 'PASS'


def test_quote_does_not_exempt_outside_403_assertion():
    quote = '분석가는 "첫 문장입니다. 403으로 차단되었습니다. 마지막 문장입니다."라고 말했습니다.'
    result, warnings = stage2.postprocess_report_json({'overall_assessment': quote + ' 403으로 차단되었습니다.'}, {})
    assert result['overall_assessment'].startswith(quote + ' HTTP 403 응답이 관찰')
    assert stage2.HTTP_STATUS_OUTCOME_WARNING in warnings
    assert any(note.startswith('safety_review:') for note in warnings)


def test_job13_missing_collections_are_not_success_claims():
    text = '별도 정찰 묶음, 인증 이상, 방법 이상, 프로토콜 이상, 후보 밖 잡음 분포는 제공되지 않았습니다.'
    result = lint.analyze_stage2_report_data({'report': {'executive_summary': [text]}})
    assert result['verdict'] == 'PASS'
    for text in ('PUT 업로드 성공', '인증 우회 성공', '403으로 차단되었습니다.', '차단 성공'):
        assert lint.analyze_stage2_report_data({'report': {'overall_assessment': text}})['verdict'] in {'FAIL', 'WARN'}


def test_all_scope_distinguishes_missing_from_empty_candidates():
    data = {'report': {'overall_assessment': '관찰 기록'}, 'stage1': {'meta': {'counts': {'candidate_rows': 0}}, 'results': []}, 'viewer': {'findings': []}}
    complete = lint.analyze_stage2_report_data(data, scope='all')
    assert complete['verdict'] == 'PASS'
    assert complete['coverage']['stage1']['status'] == 'checked_empty'
    del data['stage1']
    missing = lint.analyze_stage2_report_data(data, scope='all')
    assert missing['verdict'] == 'WARN'
    assert missing['coverage']['stage1']['status'] == 'missing'
    assert lint.analyze_stage2_report_data({'report': None}, scope='all')['verdict'] == 'WARN'
    assert lint.analyze_stage2_report_data({'report': None})['verdict'] == 'PASS'


def test_mock_stage1_to_stage2_viewer_and_all_scope(monkeypatch):
    monkeypatch.setenv('ANTHROPIC_MODEL', 'claude-test')
    text = '무해하지 않은 것은 아닙니다. 403으로 차단되었습니다.'
    parsed = {'verdict': 'suspicious_sqli', 'severity': 'medium', 'confidence': 'medium', 'false_positive_possible': True, 'reasoning_summary': text, 'evidence_fields': ['query_string', 'php://filter/convert.base64-encode/resource=config.php'], 'recommended_actions': ['review_raw_log']}
    raw = json.dumps(parsed, ensure_ascii=False)
    monkeypatch.setattr(stage1, 'call_llm_json', lambda **kw: LLMResponse(output_text=raw, response_id='mock', raw_response={}, provider='openai', model='mock'))
    candidate = {'source_table': 'security', 'log_id': 7, 'request_id': 'req-7', 'incident_group_key': 'rid:req-7', 'src_ip': '192.168.56.1', 'method': 'GET', 'uri': '/normal.php', 'query_string': 'x=%2f&file=php://filter/resource=config.php', 'status_code': 403, 'score': 10, 'raw_request': 'GET /normal.php?x=%2f HTTP/1.1'}
    result, error = stage1.classify_candidate(None, 'mock', {}, candidate, 1, False, '', 5, 0)
    assert error is None
    row = asdict(result)
    assert row['raw_output_text'] == raw
    assert row['reasoning_summary'].startswith('무해하지 않은 것은 아닙니다. HTTP 403')
    assert row['guardrail_warnings'] and row['wording_originals']
    briefs = stage2.build_incident_briefs([row], 1, [])
    brief = asdict(briefs[0])
    finding = viewer.build_finding(row, 'stage1.results', candidate, True)
    for obj in (brief, finding):
        assert obj['reasoning_summary'] == row['reasoning_summary']
        assert set(row['guardrail_warnings']).issubset(obj['guardrail_warnings'])
        assert obj['evidence_fields'] == parsed['evidence_fields']
    for key in ('log_id', 'request_id', 'src_ip', 'uri', 'query_string', 'raw_request', 'status_code', 'score'):
        assert finding[key] == candidate[key]
        assert type(finding[key]) is type(candidate[key])
    artifact = {'report': {'overall_assessment': '관찰 기록'}, 'stage1': {'results': [row]}, 'viewer': {'findings': [finding], 'report': {'overall_assessment': '403으로 차단되었습니다.'}}}
    checked = lint.analyze_stage2_report_data(artifact, scope='all')
    assert checked['verdict'] == 'WARN'
    assert all(value['checked_fields'] > 0 for value in checked['coverage'].values())
    assert any(issue['path'] == 'viewer.report.overall_assessment' for issue in checked['warnings'])
    # Legacy constructors need no newly introduced arguments.
    stage1.Stage1Result(**{key: value for key, value in row.items() if key not in {'guardrail_warnings', 'wording_originals'}})
    stage2.IncidentBrief(**{key: value for key, value in brief.items() if key not in {'guardrail_warnings', 'wording_originals'}})


def test_web_cache_depends_on_semantics_module(tmp_path, monkeypatch):
    script = tmp_path / 'check.py'
    semantic = tmp_path / 'report_semantics.py'
    report = tmp_path / 'stage2_report.json'
    cached = tmp_path / 'cached.json'
    for path in (script, semantic, report):
        path.write_text('{}')
        os.utime(path, (100, 100))
    cached.write_text(json.dumps({'scope': 'all', 'verdict': 'PASS', 'summary': {}, 'coverage': {'stage1': {'status': 'missing'}, 'viewer': {'status': 'missing'}}}))
    os.utime(cached, (200, 200))
    monkeypatch.setattr(qa_runner, 'SEMANTICS_PATH', semantic)
    runner = qa_runner.QARunner(script_path=script)
    assert runner._read_cached_if_fresh(cached, report) is not None
    os.utime(semantic, (300, 300))
    assert runner._read_cached_if_fresh(cached, report) is None


@pytest.mark.parametrize('text', [
    '이 요청은 무해합니다만 정상 동작을 입증할 수 없습니다.',
    '파일 읽기 성공을 확인했습니다만 공격 성공 여부는 확인되지 않습니다.',
    '이 요청은 무해하며 정상 동작을 입증할 수 없습니다.',
])
def test_other_judgment_negation_never_exempts_assertion(text):
    report, warnings = stage2.postprocess_report_json({'overall_assessment': text}, {})
    assert report['overall_assessment'] == text
    assert any(note.startswith('safety_review:') for note in warnings)
    assert lint.analyze_stage2_report_data({'report': report, 'meta': {'guardrail_warnings': warnings}})['verdict'] in {'WARN', 'FAIL'}


def test_all_cli_reports_paths_and_missing_artifacts(tmp_path):
    import subprocess
    report = tmp_path / 'stage2_report.json'
    report.write_text(json.dumps({'report': {'overall_assessment': '관찰 기록'}}))
    output = tmp_path / 'quality.json'
    command = [sys.executable, str(Path(lint.__file__)), '--scope', 'all', '--input', str(report), '--output', str(output)]
    assert subprocess.run(command, capture_output=True).returncode == 0
    result = json.loads(output.read_text())
    assert result['verdict'] == 'WARN'
    assert result['coverage']['stage1']['status'] == 'missing'
    assert result['coverage']['stage2']['source_path'] == str(report)
    (tmp_path / 'stage1_results.json').write_text('{"results": []}')
    (tmp_path / 'viewer_payload.json').write_text('{"findings": []}')
    assert subprocess.run(command, capture_output=True).returncode == 0
    result = json.loads(output.read_text())
    assert result['verdict'] == 'PASS'
    assert result['coverage']['stage1']['status'] == 'checked_empty'


def test_web_cache_rejects_removed_companion(tmp_path, monkeypatch):
    script, semantic, report, companion, cached = [tmp_path / name for name in ('check.py', 'semantics.py', 'report.json', 'stage1_results.json', 'cached.json')]
    for path in (script, semantic, report, companion):
        path.write_text('{}')
        os.utime(path, (100, 100))
    cached.write_text(json.dumps({'scope': 'all', 'coverage': {'stage1': {'status': 'checked'}, 'viewer': {'status': 'missing'}}}))
    os.utime(cached, (200, 200))
    monkeypatch.setattr(qa_runner, 'SEMANTICS_PATH', semantic)
    runner = qa_runner.QARunner(script_path=script)
    assert runner._read_cached_if_fresh(cached, report) is not None
    companion.unlink()
    assert runner._read_cached_if_fresh(cached, report) is None



def test_actual_viewer_cli_delivers_report_and_finding_warnings(tmp_path):
    import subprocess
    from report_semantics import process_stage1
    row = process_stage1({'request_id': 'r-9', 'source_table': 'security', 'log_id': 9, 'reasoning_summary': '무해하지 않은 것은 아닙니다.', 'evidence_fields': ['php://filter/resource=normal.php'], 'raw_request': 'GET /normal.php?x=%2f HTTP/1.1'})
    report, warnings = stage2.postprocess_report_json({'overall_assessment': '분석가는 "403으로 차단되었습니다."라고 말했습니다.'}, {})
    report_path, input_path, stage1_path, output = [tmp_path / name for name in ('stage2_report.json', 'stage2_report_input.json', 'stage1_results.json', 'viewer_payload.json')]
    report_path.write_text(json.dumps({'report': report, 'meta': {'guardrail_warnings': warnings}}, ensure_ascii=False))
    input_path.write_text('{"pipeline_counts": {"candidate_rows": 1}}')
    stage1_path.write_text(json.dumps({'results': [row]}, ensure_ascii=False))
    cmd = [sys.executable, str(Path(viewer.__file__)), '--stage2-report', str(report_path), '--stage2-report-input', str(input_path), '--stage1-results', str(stage1_path), '--out', str(output)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text())
    assert payload['report']['overall_assessment'] == report['overall_assessment']
    assert set(warnings + row['guardrail_warnings']).issubset(payload['meta']['guardrail_warnings'])
    assert payload['findings'][0]['reasoning_summary'] == row['reasoning_summary']
    assert payload['findings'][0]['raw_request'] == row['raw_request']
    assert payload['findings'][0]['log_id'] == 9
    checked = lint.analyze_stage2_report_data({'report': report, 'stage1': {'results': [row]}, 'viewer': payload}, scope='all')
    assert checked['verdict'] == 'WARN'



def test_simple_safety_and_http_corrections_compose_without_rollback():
    report, warnings = stage2.postprocess_report_json({'overall_assessment': '이 요청은 무해합니다. 403으로 차단되었습니다.'}, {})
    assert report['overall_assessment'] == '이 요청은 안전하다고 확정할 수 없습니다. ' + stage2.http_status_outcome_fallback('403으로 차단되었습니다.')
    assert 'forbidden_phrase:무해' in warnings
    assert stage2.HTTP_STATUS_OUTCOME_WARNING in warnings



def test_empty_viewer_object_is_invalid_scope_input():
    checked = lint.analyze_stage2_report_data({'report': {'overall_assessment': '관찰 기록'}, 'stage1': {'results': []}, 'viewer': {}}, scope='all')
    assert checked['verdict'] == 'WARN'
    assert checked['coverage']['viewer']['status'] == 'invalid'



def test_http_correction_keeps_original_quote_offsets():
    quote = '분석가는 "첫 문장입니다. 403으로 차단되었습니다. 마지막 문장입니다."라고 말했습니다.'
    result, warnings = stage2.postprocess_report_json({'overall_assessment': '403으로 차단되었습니다. ' + quote}, {})
    assert result['overall_assessment'] == stage2.http_status_outcome_fallback('403으로 차단되었습니다.') + ' ' + quote
    assert any(note.startswith('safety_review:') for note in warnings)
