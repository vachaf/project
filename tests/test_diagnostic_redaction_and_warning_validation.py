"""Synthetic diagnostic contracts; no live DB, API, LLM or existing artifacts."""
import copy
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest
from report_semantics import (normalize_guardrail_warnings, process_stage1,
    redact_diagnostic_text, redact_diagnostic, review_marker, review_asset_report)
from scripts import check_stage2_report_quality as lint
from src import llm_stage1_classifier as stage1, llm_stage2_reporter as stage2
from src import viewer_payload_builder as viewer
from web.services.qa_runner import QARunner
from llm_client import LLMResponse

SECRET = 'SYNTHETIC_TEST_CREDENTIAL'
CREDENTIALS = [
    f'Authorization: Bearer {SECRET}',
    f'aUtHoRiZaTiOn = bEaReR {SECRET}',
    f'Authorization: Basic {SECRET}==',
    f'authorization=basic {SECRET}',
    f'Authorization Bearer {SECRET}',
    f'"Authorization": "Bearer {SECRET}"',
    f"'Authorization': 'Basic {SECRET}'",
    f'API_KEY={SECRET}',
    f'api-key: {SECRET}',
    f'X-API-Key = "{SECRET}"',
    f"api key='{SECRET}'",
    f'api_key="{SECRET} with spaces"',
    f'Authorization: Bearer {SECRET} credential-tail',
    f'Authorization: Basic {SECRET} credential-tail',
    rf'\"Authorization\": \"Bearer {SECRET}\"',
    rf'api_key=\"{SECRET}\"',
]


def evidence():
    return {'asset_context': {'known_asset_ips': ['203.0.113.10']},
            'top_incidents': [{'src_ip': '203.0.113.10'}]}


@pytest.mark.parametrize('credential', CREDENTIALS)
def test_credentials_redacted_in_marker_asset_lint_and_forwarded_cache(credential):
    text = 'known_asset가 일치하므로 내부 테스트입니다. ' + credential
    original = {'overall_assessment': text}
    before = copy.deepcopy(original)
    marker = review_marker(text, 'report.overall_assessment', 'synthetic')
    asset = review_asset_report(original, evidence())
    result = lint.analyze_stage2_report_data({'report': original,
        'meta': {'guardrail_warnings': [marker]}}, asset_input=evidence())
    assert asset['warnings'] and result['warnings']
    for value in (marker, asset, result, QARunner()._normalize_qa_output(result)):
        assert SECRET not in json.dumps(value)
        assert '[REDACTED]' in json.dumps(value)
    assert original == before
    assert redact_diagnostic_text(redact_diagnostic_text(credential)) == redact_diagnostic_text(credential)
    for _ in range(3):
        marker = normalize_guardrail_warnings([marker, marker])[0]
        assert SECRET not in marker
    assert '/normal.php?q=%2527' == redact_diagnostic_text('/normal.php?q=%2527')


@pytest.mark.parametrize('credential', CREDENTIALS)
def test_original_evidence_retained_but_new_warning_delivery_redacted(credential):
    text = '무해하지 않은 것은 아닙니다. ' + credential
    source = {'reasoning_summary': text, 'raw_output_text': text,
        'raw_request': 'GET /normal.php?token=ordinary-tech HTTP/1.1',
        'guardrail_warnings': ['safety_review:' + json.dumps({
            'source_text': text, 'path': 'old', 'reason': 'uncertain'})]}
    processed = process_stage1(source)
    finding = viewer.build_finding(processed, 'stage1.results', None, True)
    brief = asdict(stage2.build_incident_briefs([processed], 1, [])[0])
    for value in (processed, finding, brief):
        assert SECRET not in json.dumps(value['guardrail_warnings'])
    assert source['reasoning_summary'] == text
    assert processed['raw_output_text'] == text
    assert finding['raw_request'] == source['raw_request']
    checked = lint.analyze_stage2_report_data({'report': {'overall_assessment': '관찰 기록'},
        'stage1': {'results': [processed]}, 'viewer': {'findings': [finding]}}, scope='all')
    assert SECRET not in json.dumps(checked)
    assert checked['verdict'] == 'WARN'


BAD = [({'reason': SECRET}), [SECRET], 7, None, True]


@pytest.mark.parametrize('bad', BAD)
@pytest.mark.parametrize('scope', ['stage2', 'all'])
def test_invalid_elements_do_not_crash_or_silently_pass(bad, scope):
    valid = review_marker('무해한 것으로 단정', 'report.overall_assessment', 'synthetic')
    raw = [valid, bad, valid, 'legacy-note', 'legacy-note']
    before = copy.deepcopy(raw)
    normalized = normalize_guardrail_warnings(raw, 'input.meta.guardrail_warnings')
    assert normalized[0] == valid and normalized[-1] == 'legacy-note'
    assert normalized.count(valid) == normalized.count('legacy-note') == 1
    assert len(normalized) == 3
    result = lint.analyze_stage2_report_data({'report': {'overall_assessment': '관찰 기록'},
        'meta': {'guardrail_warnings': raw}, 'stage1': {'results': []},
        'viewer': {'findings': []}}, scope=scope)
    assert result['verdict'] == 'WARN'
    invalid = [x for x in result['warnings'] if x['rule'] == 'guardrail_warning_input_invalid']
    assert len(invalid) == 1
    assert invalid[0]['path'] == 'input.meta.guardrail_warnings[1]'
    assert SECRET not in json.dumps(result)
    assert raw == before


@pytest.mark.parametrize('bad', BAD + ['legacy-note', ''])
@pytest.mark.parametrize('location', ['meta', 'stage1', 'stage1_row', 'viewer', 'viewer_row'])
def test_invalid_containers_warn_in_every_all_scope_warning_location(bad, location):
    data = {'report': {'overall_assessment': '관찰 기록'},
        'stage1': {'results': []}, 'viewer': {'findings': []}}
    value = {'guardrail_warnings': bad}
    if location == 'meta': data['meta'] = value
    elif location == 'stage1': data['stage1']['meta'] = value
    elif location == 'viewer': data['viewer']['meta'] = value
    elif location == 'stage1_row': data['stage1']['results'] = [value]
    else: data['viewer']['findings'] = [value]
    result = lint.analyze_stage2_report_data(data, scope='all')
    # A list of strings is a valid container; its ordinary legacy warning does
    # not gain a new safety meaning. All other parameter values are invalid.
    if isinstance(bad, list):
        assert result['verdict'] == 'PASS'
    else:
        assert result['verdict'] == 'WARN'
        assert any(x['rule'] == 'guardrail_warning_input_invalid' for x in result['warnings'])
    assert SECRET not in json.dumps(result)


@pytest.mark.parametrize('warnings', [[], ['legacy', 'legacy'],
    [review_marker('관찰', 'report', 'synthetic')]])
def test_valid_warning_order_and_missing_report_contract(warnings):
    result = normalize_guardrail_warnings(warnings)
    assert result == list(dict.fromkeys(warnings))
    assert normalize_guardrail_warnings(result) == result
    assert lint.analyze_stage2_report_data({'report': None})['verdict'] == 'PASS'
    assert lint.analyze_stage2_report_data({'report': None,
        'meta': {'guardrail_warnings': [None]}})['verdict'] == 'WARN'


def test_quality_cli_redacts_diagnostics_debug_and_invalid_warning_inputs(tmp_path):
    text = 'known_asset가 일치하므로 내부 테스트입니다. Authorization: Bearer ' + SECRET
    report = tmp_path / 'stage2_report.json'
    report.write_text(json.dumps({'report': {'overall_assessment': text},
        'meta': {'guardrail_warnings': [None, {'Authorization': 'Bearer ' + SECRET}]}}))
    (tmp_path / 'stage1_results.json').write_text(json.dumps({'results': [],
        'meta': {'guardrail_warnings': {'api_key': SECRET}}}))
    (tmp_path / 'viewer_payload.json').write_text(json.dumps({'findings': [],
        'meta': {'guardrail_warnings': 42}}))
    (tmp_path / 'stage2_report_input.json').write_text(json.dumps(evidence()))
    out = tmp_path / 'quality.json'
    cmd = [sys.executable, str(Path(lint.__file__)), '--scope', 'all', '--input', str(report),
        '--output', str(out), '--pretty', '--debug']
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0
    assert SECRET not in result.stdout + result.stderr + out.read_text()
    assert json.loads(out.read_text())['verdict'] == 'WARN'


def test_quality_cli_and_web_runner_error_redaction(tmp_path, monkeypatch):
    bad = tmp_path / 'bad.json'
    bad.write_text(json.dumps({'report': 'Authorization: Bearer ' + SECRET}))
    result = subprocess.run([sys.executable, str(Path(lint.__file__)), '--input', str(bad)],
        capture_output=True, text=True)
    assert result.returncode == 1
    assert SECRET not in result.stdout + result.stderr
    script = tmp_path / 'script.py'; script.write_text('pass')
    monkeypatch.setattr('web.services.qa_runner.subprocess.run', lambda *a, **k:
        SimpleNamespace(returncode=1, stdout='', stderr='Authorization: Bearer ' + SECRET))
    error = QARunner(script_path=script, output_dir=tmp_path/'output').run_quality_lint('synthetic', bad)
    assert error['is_error']
    assert SECRET not in json.dumps(error)
    assert '[REDACTED]' in error['error']


def test_mock_stage1_http_original_and_warning_reach_final_lint(monkeypatch):
    text = '403으로 차단되었습니다.\n무해하지 않은 것은 아닙니다. Authorization: Bearer ' + SECRET
    parsed = {'verdict': 'inconclusive', 'severity': 'low', 'confidence': 'low',
        'false_positive_possible': True, 'reasoning_summary': text,
        'evidence_fields': ['403으로 차단되었습니다.'], 'recommended_actions': ['review_raw_log']}
    raw = json.dumps(parsed, ensure_ascii=False)
    monkeypatch.setattr(stage1, 'call_llm_json', lambda **kw: LLMResponse(
        output_text=raw, response_id='synthetic', raw_response={}, provider='openai', model='synthetic'))
    row, error = stage1.classify_candidate(None, 'synthetic', {},
        {'request_id': 'synthetic', 'src_ip': '203.0.113.10', 'status_code': 403}, 0, False, '', 5, 0)
    assert error is None
    result = asdict(row)
    assert result['raw_output_text'] == raw
    assert any(v == text for v in result['wording_originals'].values())
    assert '\n' in result['reasoning_summary']
    finding = viewer.build_finding(result, 'stage1.results', None, True)
    brief = asdict(stage2.build_incident_briefs([result], 1, [])[0])
    for value in (result, finding, brief):assert SECRET not in json.dumps(value['guardrail_warnings'])
    report, warnings = stage2.postprocess_report_json({'overall_assessment': text}, {})
    checked = lint.analyze_stage2_report_data({'report': report, 'meta': {'guardrail_warnings': warnings},
        'stage1': {'results': [result]}, 'viewer': {'findings': [finding]}}, scope='all')
    assert SECRET not in json.dumps(checked)
    assert checked['verdict'] == 'WARN'


@pytest.mark.parametrize('text', [
    '  관찰 기록입니다.\n\t403으로 차단되었습니다.  ',
    '분석가는 "첫 문장입니다. 403으로 차단되었습니다. 마지막입니다."라고 말했습니다.',
    'URL https://example.test/normal.php?q=%2527 정상 경로 관찰.\nIP 203.0.113.10.',
    '무해하지 않은 것은 아닙니다. 403으로 차단되었습니다.',
])
def test_remote_http_rules_preserve_quote_technical_values_and_separators(text):
    stage1_text = stage1.normalize_stage1_http_status_text(text)
    stage2_text, _ = stage2.validate_http_status_report_semantics({'overall_assessment': text}, {})
    assert stage1_text == stage2_text['overall_assessment']
    if 'https://' in text or '"' in text:assert stage1_text == text
    assert stage1_text.count('\n') == text.count('\n')
    if text.startswith('  '):assert stage1_text.startswith('  ') and stage1_text.endswith('  ')


def test_main_stage1_compound_retains_the_qualification_and_original():
    text = "403으로 차단되었고 실제 파일 노출은 확인되지 않았습니다."
    parsed = {"reasoning_summary": text, "evidence_fields": ["403으로 차단됨"]}
    result = stage1.validate_stage1_http_status_semantics(parsed, {"status_code": 403})
    assert result["reasoning_summary"].startswith("HTTP 403 응답이 관찰되어 접근 제한 가능성이 있습니다.")
    assert result["reasoning_summary"].endswith(" 실제 파일 노출은 확인되지 않았습니다.")
    assert result["wording_originals"]["stage1.reasoning_summary"] == text
    assert parsed["reasoning_summary"] == text



def test_nested_diagnostic_auth_fields_are_redacted_without_editing_input():
    data = {'detail': {'Authorization': 'Bearer ' + SECRET,
        'API-Key': SECRET}, 'other': ['Authorization: Basic ' + SECRET]}
    before = copy.deepcopy(data)
    clean = redact_diagnostic(data)
    assert SECRET not in json.dumps(clean)
    assert data == before
    assert redact_diagnostic(clean) == clean
    marker = 'safety_review:' + json.dumps({'source_text': data,
        'path': 'report', 'reason': 'synthetic'})
    checked = lint.analyze_stage2_report_data({'report': {},
        'meta': {'guardrail_warnings': [marker]}})
    assert checked['verdict'] == 'WARN'
    assert SECRET not in json.dumps(checked)


def test_mock_stage1_exception_and_stage2_parse_error_diagnostics_redacted(monkeypatch, tmp_path):
    def bad_call(**kwargs):
        raise RuntimeError('Authorization: Bearer ' + SECRET)
    monkeypatch.setattr(stage1, 'call_llm_json', bad_call)
    result, error = stage1.classify_candidate(None, 'synthetic', {},
        {'request_id': 'synthetic'}, 0, False, '', 5, 0)
    assert result is None and error is not None
    assert SECRET not in json.dumps(asdict(error))
    diagnostic, original = tmp_path/'error.json', tmp_path/'raw.json'
    stage2.dump_stage2_parse_error(report_error_path=diagnostic, raw_dump_path=original,
        provider='openai', model='synthetic', response_id='synthetic', stop_reason=None,
        output_text='Authorization: Bearer ' + SECRET, raw_response={},
        parse_error=RuntimeError('Authorization: Bearer ' + SECRET),
        pretty=True, repair_attempted=False)
    assert SECRET not in diagnostic.read_text()
    assert json.loads(original.read_text())['output_text'] == 'Authorization: Bearer ' + SECRET


def test_viewer_cli_invalid_stage2_and_stage1_warnings_remain_reviewable(tmp_path):
    report, stage1_file, report_input, out = [tmp_path/name for name in
        ('stage2_report.json', 'stage1_results.json', 'stage2_report_input.json', 'viewer_payload.json')]
    report.write_text(json.dumps({'report': {'overall_assessment': '관찰 기록'},
        'meta': {'guardrail_warnings': None}}))
    stage1_file.write_text(json.dumps({'results': [{'request_id': 'synthetic',
        'reasoning_summary': '관찰 기록', 'guardrail_warnings': [{'Authorization': 'Bearer '+SECRET}]}]}))
    report_input.write_text('{"pipeline_counts": {"candidate_rows": 1}}')
    result = subprocess.run([sys.executable, str(Path(viewer.__file__)),
        '--stage2-report', str(report), '--stage1-results', str(stage1_file),
        '--stage2-report-input', str(report_input), '--out', str(out)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text())
    assert SECRET not in json.dumps(payload['meta']['guardrail_warnings'])
    checked = lint.analyze_stage2_report_data({'report': {'overall_assessment': '관찰 기록'},
        'stage1': {'results': []}, 'viewer': payload}, scope='all')
    assert checked['verdict'] == 'WARN'
    assert any(x['rule'] == 'guardrail_warning_input_invalid' for x in checked['warnings'])



@pytest.mark.parametrize('prefix', ['Authorization: Bearer ', 'API_KEY='])
@pytest.mark.parametrize('claim', ['403으로 차단되었습니다.', '파일 읽기 성공을 확인했습니다.', 'SQL injection 성공을 확인했습니다.'])
def test_clipped_excerpt_never_exposes_a_long_credential_tail(prefix, claim):
    text = prefix + SECRET * 20 + '\n' + claim
    checked = lint.analyze_stage2_report_data({'report': {'overall_assessment': text}})
    assert checked['verdict'] in {'WARN', 'FAIL'}
    assert SECRET not in json.dumps(checked)
    assert '[REDACTED]' in json.dumps(checked)
    excerpt = lint.clip_excerpt(text, len(text)-len(claim), len(text))
    assert SECRET not in excerpt


def test_stage1_error_excerpt_is_redacted_on_forwarding_without_rewriting_original():
    errors = {'errors': [{'error_message': 'Authorization: Bearer ' + SECRET,
        'response_excerpt': {'API-Key': SECRET}}]}
    before = copy.deepcopy(errors)
    payload = stage2.build_report_input({'results': []}, None, errors, 20, 20, 20, [])
    assert SECRET not in json.dumps(payload['stage1_errors_excerpt'])
    assert errors == before



def test_legacy_web_diagnostic_source_fallback_and_invalid_report_are_redacted(monkeypatch, tmp_path):
    from web.routes import reports as routes
    text = '무해합니다. Authorization: Bearer ' + SECRET
    payload = {'overall_assessment': text}
    legacy = {'verdict': 'WARN', 'warnings': [{'rule': 'safety_judgment_review',
        'path': 'report.overall_assessment', 'excerpt': 'Authorization: Basic ' + SECRET,
        'source_text': '', 'suggestion': 'API_KEY=' + SECRET}],
        'blockers': [], 'info': [], 'is_error': False}
    monkeypatch.setattr(routes, 'qa_runner', SimpleNamespace(run_quality_lint=lambda *a: legacy))
    report = SimpleNamespace(is_valid=True, report_id='synthetic', file_path=tmp_path/'report.json', report=payload)
    result = routes.lint_for_report(report)
    assert result['verdict'] == 'WARN'
    assert SECRET not in json.dumps(result)
    assert '[REDACTED]' in result['warnings'][0]['source_text']
    assert payload['overall_assessment'] == text
    assert legacy['warnings'][0]['source_text'] == ''
    report.is_valid = False
    report.error = 'Authorization: Bearer ' + SECRET
    assert SECRET not in json.dumps(routes.lint_for_report(report))


def test_all_scope_valid_warning_order_and_cross_scope_dedup_are_preserved():
    first = review_marker("first", "stage1", "synthetic")
    second = review_marker("second", "viewer", "synthetic")
    third = review_marker("third", "report", "synthetic")
    data = {"report": {"overall_assessment": "관찰 기록"},
        "stage1": {"results": [], "meta": {"guardrail_warnings": [first]}},
        "viewer": {"findings": [], "meta": {"guardrail_warnings": [second]}},
        "meta": {"guardrail_warnings": [third, first]}}
    checked = lint.analyze_stage2_report_data(data, scope="all")
    assert [x["source_text"] for x in checked["warnings"]] == ["first", "second", "third"]
    assert checked["summary"]["warning_count"] == 3
