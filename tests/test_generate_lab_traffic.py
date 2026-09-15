import argparse

import scripts.generate_lab_traffic as glt


def test_all_scenarios_have_desc_and_endpoints():
    for sid, scenario in glt.SCENARIOS.items():
        assert scenario.get("desc"), sid
        assert scenario.get("endpoints"), sid


def test_all_endpoints_have_no_fragment_and_allowed_method():
    for scenario in glt.SCENARIOS.values():
        for endpoint in scenario["endpoints"]:
            ep = glt.normalize_endpoint(endpoint)
            assert "#" not in ep["path"]
            assert ep["method"] in glt.ALLOWED_METHODS


def test_normalize_tuple_and_dict_endpoint():
    tuple_ep = glt.normalize_endpoint(("/a", "get"))
    dict_ep = glt.normalize_endpoint({"path": "/b", "method": "HEAD", "ua_family": "crawler", "tag": "x"})

    assert tuple_ep["path"] == "/a"
    assert tuple_ep["method"] == "GET"
    assert dict_ep["ua_family"] == "crawler"
    assert dict_ep["tag"] == "x"


def test_build_url_no_double_slash():
    assert glt.build_url("http://a.local/", "/x") == "http://a.local/x"
    assert glt.build_url("http://a.local", "x") == "http://a.local/x"


def test_mutation_seed_reproducible_and_no_fragment():
    r1 = glt.random.Random(42)
    r2 = glt.random.Random(42)
    path = "/search?q=phone&product_id=40&category=20"

    m1 = glt.mutate_path(path, r1)
    m2 = glt.mutate_path(path, r2)

    assert m1 == m2
    assert "#" not in m1


def test_new_coverage_scenarios_exist():
    expected = {
        "SQLi_Markers",
        "XSS_Markers",
        "Traversal_FileDisclosure_Markers",
        "CMDI_Markers",
        "HPP_Markers",
        "Log4Shell_SSRF_Markers",
        "SSTI_XXE_Markers",
        "Webshell_Path_Markers",
        "Auth_Context_Markers",
        "Method_Protocol_Context",
        "Baseline_Crawler_Mixed",
        "Mixed_Context_Heavy",
    }
    assert expected.issubset(set(glt.SCENARIOS.keys()))


def test_summary_counters_collect_method_tag_ua():
    args = argparse.Namespace(
        base_url="http://localhost:8080",
        scenario_id="SQLi_Markers",
        target_name="Lab",
        count=5,
        duration_minutes=0,
        min_delay=0.0,
        max_delay=0.0,
        profile_delay=False,
        seed=7,
        dry_run=True,
        print_curl=False,
        mutate_params=False,
        allow_public_target=True,
        xff_pool_file=None,
    )
    summary = glt.run_traffic(args)
    assert summary["request_count"] == 5
    assert sum(summary["method_counts"].values()) == 5
    assert sum(summary["tag_counts"].values()) == 5
    assert sum(summary["ua_family_counts"].values()) == 5


def test_dry_run_no_network_call(monkeypatch):
    called = {"urlopen": 0}

    def _bad_urlopen(*_args, **_kwargs):
        called["urlopen"] += 1
        raise AssertionError("urlopen should not be called in dry-run")

    monkeypatch.setattr(glt.request, "urlopen", _bad_urlopen)

    args = argparse.Namespace(
        base_url="http://localhost:8080",
        scenario_id="JuiceShop_Normal",
        target_name="Lab",
        count=3,
        duration_minutes=0,
        min_delay=0.0,
        max_delay=0.0,
        profile_delay=False,
        seed=1,
        dry_run=True,
        print_curl=True,
        mutate_params=True,
        allow_public_target=True,
        xff_pool_file=None,
    )
    summary = glt.run_traffic(args)
    assert summary["request_count"] == 3
    assert called["urlopen"] == 0
