from web.routes.reports import NOTABLE_INCIDENT_COLUMNS, visible_columns_for_rows


def _column_keys(rows):
    return [column["key"] for column in visible_columns_for_rows(rows, NOTABLE_INCIDENT_COLUMNS)]


def test_hides_request_count_when_all_placeholder_dash():
    rows = [
        {"severity": "medium", "verdict": "suspicious_sqli", "incident_ref": "inc-1", "why_it_matters": "x", "source_ip": "1.1.1.1", "request_count": "-", "recommended_action": "block"},
        {"severity": "low", "verdict": "suspicious_path_traversal", "incident_ref": "inc-2", "why_it_matters": "y", "source_ip": "1.1.1.2", "request_count": "-", "recommended_action": "observe"},
    ]
    assert "request_count" not in _column_keys(rows)


def test_shows_request_count_when_any_non_empty_value():
    rows = [
        {"severity": "medium", "verdict": "suspicious_sqli", "incident_ref": "inc-1", "why_it_matters": "x", "source_ip": "1.1.1.1", "request_count": "-", "recommended_action": "block"},
        {"severity": "low", "verdict": "suspicious_path_traversal", "incident_ref": "inc-2", "why_it_matters": "y", "source_ip": "1.1.1.2", "request_count": "5", "recommended_action": "observe"},
    ]
    assert "request_count" in _column_keys(rows)


def test_hides_recommended_action_when_all_placeholder_dash():
    rows = [
        {"severity": "medium", "verdict": "suspicious_sqli", "incident_ref": "inc-1", "why_it_matters": "x", "source_ip": "1.1.1.1", "request_count": "2", "recommended_action": "-"},
        {"severity": "low", "verdict": "suspicious_path_traversal", "incident_ref": "inc-2", "why_it_matters": "y", "source_ip": "1.1.1.2", "request_count": "3", "recommended_action": "-"},
    ]
    assert "recommended_action" not in _column_keys(rows)


def test_shows_recommended_action_when_any_non_empty_value():
    rows = [
        {"severity": "medium", "verdict": "suspicious_sqli", "incident_ref": "inc-1", "why_it_matters": "x", "source_ip": "1.1.1.1", "request_count": "2", "recommended_action": "-"},
        {"severity": "low", "verdict": "suspicious_path_traversal", "incident_ref": "inc-2", "why_it_matters": "y", "source_ip": "1.1.1.2", "request_count": "3", "recommended_action": "investigate"},
    ]
    assert "recommended_action" in _column_keys(rows)


def test_keeps_core_columns_visible_even_when_placeholder():
    rows = [
        {"severity": "-", "verdict": "-", "incident_ref": "-", "title": "-", "why_it_matters": "-", "source_ip": "-", "request_count": "-", "recommended_action": "-"},
    ]
    keys = _column_keys(rows)
    assert "severity" in keys
    assert "verdict" in keys
    assert "incident_ref" in keys
    assert "why_it_matters" in keys
    assert "source_ip" in keys
