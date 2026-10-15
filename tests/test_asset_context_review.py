"""Regression coverage for input-backed asset attribution, without LLM/DB calls."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from report_semantics import review_asset_report
from src import llm_stage2_reporter as stage2
from scripts import check_stage2_report_quality as lint


def asset_input(known, ips=('203.0.113.10',)):
    return {'asset_context': {'known_asset_ips': known},
            'top_incidents': [{'src_ip': ip, 'known_asset': ip in known} for ip in ips]}


@pytest.mark.parametrize('known,ips,expected', [
    ([], ['203.0.113.10'], {'203.0.113.10': 'not_configured'}),
    (['203.0.113.10'], ['203.0.113.10'], {'203.0.113.10': 'matched'}),
    (['203.0.113.20'], ['203.0.113.10'], {'203.0.113.10': 'unmatched'}),
    (['203.0.113.10'], ['203.0.113.10', '203.0.113.20'],
     {'203.0.113.10': 'matched', '203.0.113.20': 'unmatched'}),
])
def test_input_context_states_and_boolean_contract(known, ips, expected):
    rows = [{'src_ip': ip, 'request_id': f'r-{i}', 'verdict': 'suspicious_sqli'} for i, ip in enumerate(ips)]
    result = stage2.build_report_input({'results': rows}, None, None, 20, 20, 20, known)
    assert result['asset_context']['source_ip_match_states'] == expected
    assert result['asset_context']['inventory_status'] == ('configured' if known else 'not_configured')
    for row in result['top_incidents']:
        assert type(row['known_asset']) is bool
        assert row['known_asset'] is (row['src_ip'] in known)
    prompt = stage2.build_messages(result)
    assert 'source_ip_match_states' in json.dumps(prompt, ensure_ascii=False)
    assert '목록 완전성' in json.dumps(prompt, ensure_ascii=False)


@pytest.mark.parametrize('text', [
    'known asset IP 매칭이 없어 내부 테스트 가능성을 적극적으로 시사하진 않지만, 반대로 외부 공격자로 단정할 근거도 충분하지 않습니다.',
    'known asset IP와의 매칭이 없어 내부 테스트/자체 호출 가능성을 배제할 수는 있지만, 이를 뒷받침하는 추가 단서는 제공되지 않았습니다.',
    'known_asset IP와의 매칭은 없었으므로 내부 테스트 가능성은 특별히 높게 보이지 않지만, 완전히 배제할 수는 없습니다.',
    '자산 목록이 비어 있으므로 내부 테스트 가능성이 낮습니다.',
    'known_asset가 일치하므로 내부 테스트입니다.',
    'known_asset가 일치하므로 내부 테스트임을 확인했습니다.',
])
@pytest.mark.parametrize('known', [[], ['203.0.113.10'], ['203.0.113.20']])
def test_wrong_or_ambiguous_inference_warns_and_keeps_original(text, known):
    report = {'confidence_and_limitations': [text]}
    evidence = asset_input(known)
    review = review_asset_report(report, evidence)
    assert review['warnings']
    assert all(row['path'] == 'report.confidence_and_limitations[0]' and row['source_text'] == text for row in review['warnings'])
    processed, warnings = stage2.postprocess_report_json(report, evidence)
    assert processed == report
    assert any(note.startswith('safety_review:') for note in warnings)
    checked = lint.analyze_stage2_report_data({'report': report}, asset_input=evidence)
    assert checked['verdict'] == 'WARN'
    assert any(row['rule'] == 'asset_context_inference' for row in checked['warnings'])


@pytest.mark.parametrize('text', [
    '자산 목록이 미설정되어 소유자 정보가 부족합니다. 내부 테스트 여부는 확인할 수 없습니다.',
    'known_asset IP 매칭이 없지만 내부 테스트 가능성을 배제할 수는 없습니다.',
    'known_asset IP 매칭이 없어도 내부 테스트 가능성이 낮다고 단정할 수 없습니다.',
    'known_asset IP 일치로 내부 테스트임을 확정할 수는 없습니다.',
    '내부 테스트나 운영 점검 여부는 추가 맥락이 없어 확정할 수 없습니다.',
    '내부 테스트 가능성을 낮추지 않습니다.',
])
def test_information_limits_and_proper_negations_do_not_warn(text):
    # Inventory absence is actual input, rather than missing evidence.
    evidence = asset_input([])
    report = {'confidence_and_limitations': [text]}
    assert review_asset_report(report, evidence)['warnings'] == []
    assert lint.analyze_stage2_report_data({'report': report}, asset_input=evidence)['verdict'] == 'PASS'


def test_mixed_ip_membership_compared_with_each_report_subject():
    evidence = asset_input(['203.0.113.10'], ['203.0.113.10', '203.0.113.20'])
    report = {'notable_source_ips': [
        {'src_ip': '203.0.113.10', 'reason': 'known_asset와 매칭이 없습니다.'},
        {'src_ip': '203.0.113.20', 'reason': 'known_asset와 일치합니다.'},
    ]}
    warnings = review_asset_report(report, evidence)['warnings']
    assert {row['path'] for row in warnings} == {'report.notable_source_ips[0].reason', 'report.notable_source_ips[1].reason'}
    correct = {'notable_source_ips': [
        {'src_ip': '203.0.113.10', 'reason': 'known_asset와 일치합니다. 내부 테스트인지는 확인할 수 없습니다.'},
        {'src_ip': '203.0.113.20', 'reason': 'known_asset와 매칭이 없습니다. 내부 테스트 가능성은 배제할 수 없습니다.'},
    ]}
    assert review_asset_report(correct, evidence)['warnings'] == []


@pytest.mark.parametrize('evidence', [None, {}, {'asset_context': {}}, {'asset_context': {'known_asset_ips': 'not-a-list'}}])
def test_missing_input_is_explicitly_not_evaluable(evidence):
    result = lint.analyze_stage2_report_data({'report': {'overall_assessment': '관찰 기록'}}, asset_input=evidence)
    assert result['asset_review']['status'] == 'not_evaluable'
    assert result['asset_review']['limitations']
    assert any(row['rule'] == 'asset_context_not_evaluable' for row in result['info'])


def test_optional_cli_and_legacy_cli(tmp_path):
    report = tmp_path / 'report.json'
    evidence = tmp_path / 'input.json'
    output = tmp_path / 'quality.json'
    report.write_text(json.dumps({'report': {'overall_assessment': 'known_asset 미매칭으로 내부 테스트 가능성이 낮습니다.'}}, ensure_ascii=False))
    evidence.write_text(json.dumps(asset_input([])))
    cmd = [sys.executable, str(Path(lint.__file__)), '--input', str(report), '--output', str(output)]
    assert subprocess.run(cmd, capture_output=True).returncode == 0
    assert json.loads(output.read_text())['asset_review']['status'] == 'not_evaluable'
    assert subprocess.run(cmd + ['--asset-input', str(evidence)], capture_output=True).returncode == 0
    checked = json.loads(output.read_text())
    assert checked['asset_review']['status'] == 'checked'
    assert checked['verdict'] == 'WARN'


def test_all_scope_checks_stale_viewer_asset_prose_independently():
    text = 'known_asset가 일치하므로 내부 테스트입니다.'
    data = {'report': {'overall_assessment': '정보 부족으로 목적을 확인할 수 없습니다.'},
            'stage1': {'results': []}, 'viewer': {'report': {'overall_assessment': text}, 'findings': []}}
    result = lint.analyze_stage2_report_data(data, scope='all', asset_input=asset_input(['203.0.113.10']))
    assert result['verdict'] == 'WARN'
    assert any(row['path'] == 'viewer.report.overall_assessment' and row['source_text'] == text for row in result['warnings'])


def test_stale_match_metadata_does_not_override_actual_inventory():
    evidence = asset_input([])
    evidence['asset_context']['matched_known_assets'] = ['203.0.113.10']
    evidence['top_incidents'][0]['known_asset'] = True
    result = review_asset_report({'overall_assessment': 'known_asset와 일치합니다.'}, evidence)
    assert result['source_ip_match_states']['203.0.113.10'] == 'not_configured'
    assert any(row['reason'] == 'claimed_match_but_input_does_not_match' for row in result['warnings'])



def assert_asset_review_channels(text, evidence, expected_reason=None):
    """Both consumers must retain the prose and the same diagnostic evidence."""
    report = {'overall_assessment': text}
    expected = ([{'path': 'report.overall_assessment', 'source_text': text,
                  'reason': expected_reason}] if expected_reason else [])
    assert review_asset_report(report, evidence)['warnings'] == expected
    processed, notes = stage2.postprocess_report_json(report, evidence)
    assert processed == report
    asset_notes = [json.loads(note.removeprefix('safety_review:')) for note in notes
                   if note.startswith('safety_review:')]
    assert all(row['path'] == 'report.overall_assessment' and row['source_text'] == text
               for row in asset_notes)
    asset_notes = [row for row in asset_notes
                   if row['reason'].startswith(('asset_membership_', 'claimed_'))]
    assert asset_notes == expected
    checked = lint.analyze_stage2_report_data({'report': report}, asset_input=evidence)
    assert checked['verdict'] == ('WARN' if expected_reason else 'PASS')
    issues = [row for row in checked['warnings'] if row['rule'] == 'asset_context_inference']
    assert len(issues) == len(expected)
    for issue in issues:
        assert issue['path'] == 'report.overall_assessment'
        assert issue['source_text'] == text
        assert issue['suggestion'] == expected_reason


@pytest.mark.parametrize('separator', ['은 ', '는 ', '이 ', '가 ', '과 ', '와 ', ' '])
@pytest.mark.parametrize('ip,claim,reason', [
    ('203.0.113.10', '일치합니다.', None),
    ('203.0.113.20', '일치합니다.', 'claimed_match_but_input_does_not_match'),
    ('203.0.113.10', '매칭이 없습니다.', 'claimed_no_match_but_input_matches'),
    ('203.0.113.20', '매칭이 없습니다.', None),
    ('203.0.113.100', '일치합니다.', 'claimed_match_but_input_does_not_match'),
])
def test_explicit_ip_particles_and_spaces_use_own_membership(separator, ip, claim, reason):
    evidence = asset_input(['203.0.113.10'], ['203.0.113.10', '203.0.113.20'])
    assert_asset_review_channels(f'출발지 IP {ip}{separator}known_asset와 {claim}', evidence, reason)


@pytest.mark.parametrize('text,expected', [
    ('203.0.113.10은', ['203.0.113.10']),
    ('203.0.113.10 입니다.', ['203.0.113.10']),
    ('(203.0.113.10).', ['203.0.113.10']),
    ('203.0.113.100은', ['203.0.113.100']),
    ('1203.0.113.10은', []),
    ('203.0.113.1000은', []),
    ('1.203.0.113.10은', []),
    ('203.0.113.10.1은', []),
    ('id203.0.113.10은', []),
    ('203.0.113.10_id', []),
])
def test_asset_ip_numeric_and_identifier_boundaries(text, expected):
    from report_semantics import ASSET_IPV4
    assert [match.group() for match in ASSET_IPV4.finditer(text)] == expected


@pytest.mark.parametrize('predicate', ['할', '볼', '판단할', '단정할'])
@pytest.mark.parametrize('particle', ['', '는'])
def test_negation_of_the_same_possibility_evaluation_passes(predicate, particle):
    text = f'known_asset 미매칭만으로 내부 테스트 가능성이 낮다고 {predicate} 수{particle} 없습니다.'
    assert_asset_review_channels(text, asset_input([]))


@pytest.mark.parametrize('text', [
    'known_asset 미매칭으로 내부 테스트 가능성이 낮지만 공격 성공 여부는 확인할 수 없습니다.',
    'known_asset 미매칭으로 내부 테스트 가능성이 낮다고 판단하지만 공격 성공 여부는 확인할 수 없습니다.',
    'known_asset 미매칭으로 내부 테스트 가능성이 낮으며 공격 성공 여부는 판단할 수 없습니다.',
    'known_asset 미매칭으로 내부 테스트 가능성이 낮다고 할 수 있습니다.',
])
def test_other_evaluation_negation_does_not_exempt_reduction(text):
    assert_asset_review_channels(text, asset_input([]),
                                'asset_membership_does_not_reduce_internal_test_possibility')


@pytest.mark.parametrize('text', [
    'known_asset 미매칭만으로 내부 테스트 가능성이 낮은 것으로 볼 수 없습니다.',
    'known_asset 미매칭만으로 내부 테스트 가능성이 적다고 판단할 수 없습니다.',
])
def test_existing_direct_possibility_negations_still_pass(text):
    assert_asset_review_channels(text, asset_input([]))
