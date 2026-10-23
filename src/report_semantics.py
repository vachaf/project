"""Pure wording guardrails; never alter source/technical fields or classification."""
import json
import re

PROMPT_BOUNDARY = (
    'HTTP 상태는 응답 관찰이며 실제 차단·안전·성공·실패의 증거가 아니다. '
    '공격 성공 없음과 성공 여부 미확인을 구별하고 후보 제외/0건으로 결과를 확정하지 마라. '
    'known_asset_ips가 비거나 미매칭이어도 내부 테스트 가능성을 낮추지 말고 매칭도 내부 테스트 확정 근거로 쓰지 마라. '
    '교육성 키워드 검색 제외는 실제 과거·유사 트래픽 대조가 아니다. 출발지·목적지는 실제 입력 필드에 맞춰라. '
    '기술 값과 인용은 보존하고 복합 판단은 무리하게 다시 쓰지 말고 검토 대상으로 명시하라. '
)
# Token boundaries protect URLs, paths, encoded strings, wrappers and identifiers.
PROTECTED = re.compile(
    r'''https?://\S+|\b\w+://\S+|(?:/|\b\w*[=_%])[^\s]+|`[^`]*`|["“‘「][\s\S]*?["”’」]'''
    r'|\b\d{4}-\d{2}-\d{2}T\S+|\b\d{2}:\d{2}:\d{2}\S*'
    r'|\b(?:[A-Za-z0-9_-]+\.)+[A-Za-z0-9_-]+\S*'
    r'|\b[0-9A-Fa-f]*:[0-9A-Fa-f:]+\b'
)
JUDGMENT = re.compile(r'무해[가-힣]*|정상[가-힣]*|\b(?:normal|benign)\b|차단[가-힣]*|공격\s*성공\s*없|(?:공격|파일|인증|우회)[^,;.!?\n]*?성공', re.I)
# Match the complete judgment predicate, so another judgment's negation cannot
# exempt an earlier assertion. Double negation remains a review case.
NEGATION = re.compile(
    r'^(?:[^,;.!?]*?요청은\s*)?(?:무해|정상)[^,;.!?]*?(?:하지(?:는)?\s*않습니다|단정할\s*수(?:는)?\s*없습니다|'
    r'볼\s*수(?:는)?\s*없습니다|근거가\s*부족합니다|증거가\s*없습니다|입증할\s*수(?:는)?\s*없습니다)$'
    r'|^(?:공격|파일|인증|권한|SQL)[^,;.!?]*?성공[^,;.!?]*?(?:(?:확인|입증)할\s*수(?:는)?\s*없습니다|확인되지\s*않습니다)$', re.I)


# Applied only to newly produced diagnostics. Source reports, request originals,
# raw LLM output and wording_originals remain evidence and are never rewritten.
_AUTH_VALUE = re.compile(
    r"(?i)(\bauthorization(?:\\?[\"'])?\s*(?:[:=]\s*(?:\\?[\"'])?\s*|\s+))"
    r"(?:(?:bearer|basic)\s+[^\r\n,;\"'\\}]+|[^\s,;\"'\\\r\n}]+)"
)
_API_VALUE = re.compile(
    r"(?i)(\b(?:x[-_])?api[-_ ]?key(?:\\?[\"'])?\s*[:=]\s*)"
    r"(?:\\?\"[^\"\\\r\n]*\\?\"|\\?'[^'\\\r\n]*\\?'|[^\s,;\"'\\\r\n}]+)"
)


def redact_diagnostic_text(text):
    """Redact explicit Authorization/API-key values, including auth schemes."""
    if not isinstance(text, str):
        return text
    return _API_VALUE.sub(lambda match: match[1] + '[REDACTED]',
                          _AUTH_VALUE.sub(lambda match: match[1] + '[REDACTED]', text))


def redact_diagnostic(value):
    if isinstance(value, str):
        return redact_diagnostic_text(value)
    if isinstance(value, dict):
        return {redact_diagnostic_text(key):
                '[REDACTED]' if isinstance(key, str) and re.fullmatch(
                    r'authorization|(?:x[-_])?api[-_ ]?key', key, re.I)
                else redact_diagnostic(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_diagnostic(item) for item in value]
    return value


def review_marker(text, path, reason):
    return 'safety_review:' + json.dumps(redact_diagnostic(
        dict(source_text=text, path=path, reason=reason)), ensure_ascii=False)


def normalize_guardrail_warnings(value, path='guardrail_warnings'):
    """Only list[str] is valid; absent fields are supplied as [] by callers.

    Keep valid strings in order, deduplicate after validating all elements, and
    replace invalid input with content-free review markers, never a silent PASS.
    Explicit null, scalar/string and dict containers are invalid, not absence.
    """
    if not isinstance(value, list):
        return [review_marker(type(value).__name__, path, 'invalid_guardrail_warning_container')]
    result = []
    for index, warning in enumerate(value):
        if not isinstance(warning, str):
            warning = review_marker(type(warning).__name__, f'{path}[{index}]',
                                    'invalid_guardrail_warning_element')
        elif warning.startswith('safety_review:'):
            try:
                warning = 'safety_review:' + json.dumps(redact_diagnostic(
                    json.loads(warning.split(':', 1)[1])), ensure_ascii=False)
            except (ValueError, TypeError):
                warning = redact_diagnostic_text(warning)
        else:
            warning = redact_diagnostic_text(warning)
        if warning not in result:
            result.append(warning)
    return result


def http_outcome_is_protected(text):
    return bool(PROTECTED.search(text) or re.search(r'[,;]|되었고|지만|이며|습니다만|합니다만|\n', text))


def map_http_sentences(text, fallback, *, allow_compound=False):
    """Transform only unprotected sentence spans; preserve all separators."""
    protected = list(PROTECTED.finditer(text))
    parts = re.split(r'((?<=[.!?])[^\S\n]+|\n+)', text)
    offset = 0
    for index, part in enumerate(parts):
        start = offset
        offset += len(part)
        if index % 2 or any(span.start() < offset and span.end() > start for span in protected):
            continue
        if allow_compound or not http_outcome_is_protected(part):
            replacement = fallback(part)
            if replacement is not None:
                # Keep indentation/trailing whitespace around a corrected clause.
                left = len(part) - len(part.lstrip())
                right = len(part.rstrip())
                parts[index] = part[:left] + replacement + part[right:]
    return ''.join(parts)


def correct_http_outcome_assertions(text):
    """Rewrite assertion spans, keeping technical evidence and separators intact.

    Mask before finding clause boundaries/rules, but apply edits at original
    offsets. Quotes and technical values cannot become either claims or status
    evidence. Ambiguous compound/negated judgments retain their review scope.
    """
    from http_status_semantics import (
        HTTP_STATUS_BLOCK_ASSERTION_PATTERNS,
        HTTP_STATUS_GENERIC_BLOCK_ASSERTION_PATTERNS,
        HTTP_STATUS_ATTACK_FAILURE_PATTERNS,
        HTTP_STATUS_FILE_ACCESS_FAILURE_PATTERNS,
        http_status_outcome_fallback,
    )

    protected = list(PROTECTED.finditer(text))
    surface = list(text)
    for span in protected:
        # A non-whitespace mask cannot join predicate words across evidence.
        surface[span.start():span.end()] = '\0' * (span.end() - span.start())
    surface = ''.join(surface)
    patterns = (*HTTP_STATUS_BLOCK_ASSERTION_PATTERNS,
                *HTTP_STATUS_GENERIC_BLOCK_ASSERTION_PATTERNS,
                *HTTP_STATUS_ATTACK_FAILURE_PATTERNS,
                *HTTP_STATUS_FILE_ACCESS_FAILURE_PATTERNS)
    edits = []
    start = 0
    boundaries = [(m.start(), m.end()) for m in re.finditer(
        r'(?<=[.!?])[^\S\r\n]+|\r\n|[\r\n]|[,;][^\S\r\n]*', surface)]
    for end, next_start in boundaries + [(len(text), len(text))]:
        clause = surface[start:end]
        if not http_outcome_is_protected(clause) and http_status_outcome_fallback(clause):
            # Preserve the existing canonical rendering of a bare status claim.
            if re.fullmatch(r'\s*(?:HTTP\s*)?(?:401|403)(?:으로| 응답으로)\s*차단되었습니다[.!?]?\s*', clause, re.I):
                left = start + len(clause) - len(clause.lstrip())
                right = end - (len(clause) - len(clause.rstrip()))
                edits.append((left, right, http_status_outcome_fallback(clause)))
            else:
                for pattern in patterns:
                    for match in pattern.finditer(clause):
                        fallback = http_status_outcome_fallback(match.group())
                        left, right = match.span('assertion') if 'assertion' in match.groupdict() else match.span()
                        # Complete only the matched Korean predicate/inflection.
                        ending = re.match(r'[가-힣]*(?:\s+것으로\s*(?:추정|보)[가-힣]*)?[.!?]?', clause[right:])
                        right += ending.end()
                        if fallback is not None:
                            edits.append((start + left, start + right, fallback))
        start = next_start

    result = []
    cursor = 0
    for start, end, replacement in sorted(edits, key=lambda item: (item[0], -item[1])):
        if start < cursor or any(span.start() < end and span.end() > start for span in protected):
            continue
        result.extend((text[cursor:start], replacement))
        cursor = end
    result.append(text[cursor:])
    return ''.join(result)


def process_text(text, path='report', *, correct_http=True):
    spans = list(PROTECTED.finditer(text))
    def visible(part, offset):
        return ''.join(' ' if any(m.start() <= offset+i < m.end() for m in spans) else c for i,c in enumerate(part))
    warnings = []
    parts = re.split(r'((?<=[.!?])\s+|\n+|[,;]\s*|(?:하지만|그러나|반면|다만)\s+)', text)
    offset = 0
    for i, part in enumerate(parts):
        start = offset
        offset += len(part)
        if i % 2:
            continue
        surface = visible(part, start)
        quoted = any(m.start() < start+len(part) and m.end() > start and m.group()[0] in '"“‘「`' and JUDGMENT.search(m.group()) for m in spans)
        if quoted:
            if JUDGMENT.search(part):
                warnings.append(review_marker(text, path, 'quoted_or_uncertain_safety_scope'))
            continue
        if not JUDGMENT.search(surface):
            continue
        stripped = surface.strip().rstrip('.!?')
        if not re.search(r'무해|차단|\b(?:normal|benign)\b|성공', stripped) and re.search(r'정상\s*비교군', stripped):
            continue
        if re.fullmatch(r'(?:WAF\s*)?차단\s*정책을\s*(?:점검|검토)하세요', stripped):
            continue
        # Negation exempts only its own clause, never a preceding assertion.
        if NEGATION.fullmatch(stripped) and len(list(JUDGMENT.finditer(stripped))) == 1 and not re.search(r'지만|이며|합니다만|것은\s*아니|으로 차단|차단되', stripped):
            continue
        # An outcome's own uncertainty predicate ends the clause. A separate
        # safety assertion before it still requires review.
        judgments = list(JUDGMENT.finditer(stripped))
        if judgments and not any(m.group().startswith(('무해', '정상')) for m in judgments):
            if len(judgments) == 1 and re.search(r'(?:확인|입증|단정)(?:할\s*수(?:는)?\s*없|되지\s*않)|성공.*?아니', stripped):
                continue
        replacement = None
        claim = re.fullmatch(r'(응답은\s*)?(?:HTTP\s*)?(401|403)(?:으로| 응답으로)\s*차단(?:되었습니다|되었다|됨)', stripped)
        if claim and not correct_http:
            continue
        if claim:
            replacement = f'HTTP {claim[2]} 응답이 관찰되었습니다' + ('.' if part.rstrip().endswith('.') else '')
        else:
            if re.fullmatch(r'(?:입력값을 무해화하세요|입력값의 무해화를 권고합니다|무해화 조치를 검토하세요)', stripped):
                replacement = stripped.replace('무해화하세요', '안전하게 처리하세요').replace('무해화를', '안전한 처리를').replace('무해화', '안전한 처리')
            else:
                replacement = re.sub(r'무해합니다$', '안전하다고 확정할 수 없습니다', stripped) if re.fullmatch(r'(?:(?:이 |다른 )?요청은 )?무해합니다', stripped) else stripped
            replacement = re.sub(r'^무해한 요청입니다$', '안전 여부가 확인되지 않은 요청입니다', replacement)
            if replacement == stripped:
                replacement = None
            elif part.rstrip().endswith('.'):
                replacement += '.'
        if replacement is not None and surface == part:
            left = len(part) - len(part.lstrip())
            right = len(part.rstrip())
            parts[i] = part[:left] + replacement + part[right:]
            warnings.append('forbidden_phrase:무해' if '무해' in part else review_marker(text, path, 'simple_claim_corrected_to_observation'))
        else:
            warnings.append(review_marker(text, path, 'mixed_or_unsupported_safety_judgment'))
    return ''.join(parts), list(dict.fromkeys(warnings))

def process_stage1(item, path='stage1'):
    result = dict(item)
    warnings = normalize_guardrail_warnings(item.get('guardrail_warnings', []), path + '.guardrail_warnings')
    originals = dict(item.get('wording_originals') or {})
    for key in ('reasoning_summary', 'evidence_fields'):
        value = item.get(key)
        rows = value if isinstance(value, list) else [value]
        processed = []
        for i, text in enumerate(rows):
            if not isinstance(text, str):
                processed.append(text)
                continue
            field = f'{path}.{key}' + (f'[{i}]' if isinstance(value, list) else '')
            clean, notes = process_text(text, field)
            if clean != text:
                originals[field] = text
            processed.append(clean)
            warnings.extend(notes)
        if value is not None:
            result[key] = processed if isinstance(value, list) else processed[0]
    result['guardrail_warnings'] = list(dict.fromkeys(warnings))
    result['wording_originals'] = originals
    return result


def build_asset_match_context(known_asset_ips, source_ips):
    """Add evidence state without changing known_asset's membership boolean."""
    known = set(known_asset_ips)
    sources = sorted({ip for ip in source_ips if isinstance(ip, str) and ip and ip != '-'})
    states = {ip: 'not_configured' if not known else 'matched' if ip in known else 'unmatched' for ip in sources}
    return {
        'inventory_status': 'configured' if known else 'not_configured',
        'source_ip_match_states': states,
        'interpretation_boundary': (
            'known_asset=false는 미설정과 미일치를 구별하지 않는 목록 포함 여부 boolean. '
            'not_configured=자산 목록 미설정, matched=설정 목록과 일치, unmatched=설정 목록과 미일치. '
            '일치 여부는 소유자·요청 목적 검증 결과가 아니며 목록 완전성도 보장되지 않는다.'
        ),
    }


ASSET_SUBJECT = re.compile(r'known[_ -]?asset|자산|내부\s*테스트|자체\s*호출|운영\s*점검', re.I)
INTERNAL_SUBJECT = re.compile(r'내부\s*테스트|자체\s*호출|운영\s*점검', re.I)
# Match the judgment itself, rather than exempting a whole sentence because a
# later, different assertion is negated (e.g. "낮지만 배제할 수 없습니다").
ASSET_REDUCTION = re.compile(
    r'(?:가능성[^,;.!?\n]{0,45}?(?:낮(?:습니다|다|다고|게|아|은|으며|지만)|적(?:습니다|다|다고|어|은|지만)|높게\s*보이지|적극적으로\s*시사하(?:지|진)\s*않|배제할\s*수(?:는)?\s*있|배제(?:됩니다|했다|했습니다|할)))'
    r'|(?:내부\s*테스트|자체\s*호출|운영\s*점검)[^,;.!?\n]{0,35}?(?:아닙니다|아니다)', re.I)
ASSET_NEGATED_REDUCTION = re.compile(
    r'(?:낮|적)(?:다고|은\s*것으로)\s*(?:할|볼|판단할|단정할)\s*수(?:는)?\s*없'
    r'|배제할\s*수(?:는)?\s*없|(?:낮추|배제)지\s*않'
)
ASSET_CONFIRMATION = re.compile(
    r'(?:내부\s*테스트|자체\s*호출|운영\s*점검)(?:임|인\s*것|로|라고|으로|입니다|이다)[^,;.!?\n]{0,25}?(?:확정|확인|판명)'
    r'|(?:내부\s*테스트|자체\s*호출|운영\s*점검)(?:입니다|이다)(?![가-힣])'
    r'|(?:내부\s*테스트|자체\s*호출|운영\s*점검)\s*가능성[^,;.!?\n]{0,25}?(?:높습니다|높다|높게\s*보입니다|높아|높은|높다고|확실)', re.I)
# ASCII token boundaries allow Korean particles, but reject numeric/identifier
# prefixes and longer dotted addresses. A sentence-final dot is punctuation.
ASSET_IPV4 = re.compile(
    r'(?<![A-Za-z0-9_.:])(?:[0-9]{1,3}\.){3}[0-9]{1,3}'
    r'(?![A-Za-z0-9_:]|\.[A-Za-z0-9_.:])'
)
ASSET_UNCERTAINTY = re.compile(r'(?:확정|확인|단정|판단)할\s*수(?:는)?\s*없|확인되지\s*않|확정하지\s*않')


def iter_asset_report_fields(value, path='report', source_ip=None):
    """Inspect prose only. Keep complete original strings in diagnostics."""
    prose = {'report_title', 'overall_assessment', 'executive_summary', 'title', 'detail',
             'why_it_matters', 'reason', 'noise_interpretation', 'action', 'why',
             'confidence_and_limitations', 'presentation_takeaway'}
    if isinstance(value, dict):
        source_ip = value.get('src_ip', source_ip)
        for key, child in value.items():
            child_path = f'{path}.{key}'
            if key in prose:
                rows = child if isinstance(child, list) else [child]
                for i, row in enumerate(rows):
                    if isinstance(row, str):
                        yield child_path + (f'[{i}]' if isinstance(child, list) else ''), row, source_ip
            if isinstance(child, (dict, list)):
                yield from iter_asset_report_fields(child, child_path, source_ip)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            if isinstance(child, (dict, list)):
                yield from iter_asset_report_fields(child, f'{path}[{i}]', source_ip)


def review_asset_report(report, asset_input=None, *, field_path="report"):
    """Review only: never rewrite asset attribution or infer test likelihood."""
    context = asset_input.get('asset_context') if isinstance(asset_input, dict) else None
    known = context.get('known_asset_ips') if isinstance(context, dict) else None
    if not isinstance(known, list) or any(not isinstance(ip, str) for ip in known):
        return {'status': 'not_evaluable', 'reason': '실제 asset_context.known_asset_ips 입력이 없거나 유효하지 않음',
                'limitations': '자산 목록과 IP의 일치 및 가능성 추론은 평가 불가', 'warnings': []}
    source_ips = set()
    def collect(value):
        if isinstance(value, dict):
            ip = value.get('src_ip')
            if isinstance(ip, str):
                source_ips.add(ip)
            for key, child in value.items():
                if key != 'asset_context' and isinstance(child, (dict, list)):
                    collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)
    collect(asset_input)
    evidence = build_asset_match_context(known, source_ips)
    states = evidence['source_ip_match_states']
    warnings = []
    for path, text, subject_ip in iter_asset_report_fields(report, field_path):
        reasons = []
        # Sentence splitting must not split IPv4 literals at their dots.
        clauses = re.split(r'(?<=[.!?])\s+|\n+', text)
        for clause in clauses:
            if not ASSET_SUBJECT.search(clause):
                continue
            if INTERNAL_SUBJECT.search(clause):
                for match in ASSET_REDUCTION.finditer(clause):
                    local = re.split(r'[,;.!?\n]|하지만|그러나|반면|다만|지만|이며', clause[match.start():], maxsplit=1)[0]
                    if not ASSET_NEGATED_REDUCTION.search(local):
                        reasons.append('asset_membership_does_not_reduce_internal_test_possibility')
                for match in ASSET_CONFIRMATION.finditer(clause):
                    local = re.split(r'[,;.!?\n]|하지만|그러나|반면|다만|지만|이며', clause[match.start():], maxsplit=1)[0]
                    if not ASSET_UNCERTAINTY.search(local):
                        reasons.append('asset_membership_does_not_confirm_internal_test')
            # Compare explicit membership statements with supplied evidence.
            if re.search(r'known[_ -]?asset|자산', clause, re.I):
                mentioned = [match.group() for match in ASSET_IPV4.finditer(clause)]
                mentioned.extend(ip for ip in states if ':' in ip and re.search(
                    r'(?<![A-Za-z0-9_.:])' + re.escape(ip) + r'(?![A-Za-z0-9_:])', clause))
                if not mentioned and subject_ip in states:
                    mentioned = [subject_ip]
                observed_states = {states.get(ip, 'not_configured' if not known else 'matched' if ip in known else 'unmatched')
                                   for ip in mentioned} if mentioned else set(states.values())
                negative = re.search(r'(?:매칭|일치)[^,;.!?\n]{0,15}?(?:없|않|미일치)|미매칭|미일치', clause)
                positive = re.search(r'(?:매칭|일치)(?:합니다|했습니다|된다|됩니다|하는|한|되어|했|하므로|하였|이\s*있)', clause)
                if negative and 'matched' in observed_states and not re.search(r'일부|다른|미일치\s*IP', clause):
                    reasons.append('claimed_no_match_but_input_matches')
                if positive and not negative and (not known or ('unmatched' in observed_states if mentioned else observed_states == {'unmatched'})):
                    reasons.append('claimed_match_but_input_does_not_match')
                if re.search(r'(?:목록|리스트)[^,;.!?\n]{0,15}?(?:미설정|설정되지|없|비어)', clause) and known:
                    reasons.append('claimed_unconfigured_but_inventory_supplied')
        for reason in dict.fromkeys(reasons):
            warnings.append(redact_diagnostic({'path': path, 'source_text': text, 'reason': reason}))
    return {'status': 'checked', **evidence, 'warnings': warnings,
            'limitations': '제공된 입력 범위의 목록·IP 및 한국어 표현 규칙 검사; 목록 완전성, 실제 소유자·목적 및 모든 표현의 의미는 검증하지 못함'}
