def test_midrange_zone_is_accepted_and_aliased():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from shared.tools.shots import leaders
    src = open(leaders.__file__).read()
    assert '"midrange"' in src
    assert 'if z == "midrange"' in src
    assert 'z = "long_mid"' in src

def test_unknown_zone_error_steers_retry_and_lists_midrange():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from shared.tools.shots.leaders import get_shot_zone_leaders
    res = get_shot_zone_leaders.invoke({"zone": "bogus", "season": "2024-25"})
    assert res.get("ok") is False
    err = res.get("error") or ""
    assert "midrange" in err
    assert "retry" in err.lower()
