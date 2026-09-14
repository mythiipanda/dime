from v2.tests.compatibility.harness import ShadowRunner, TurnTrace


def test_shadow_failure_does_not_change_primary_result():
    scenario = {"id": "x", "chain": ["q"], "budget": {"max_tool_calls": 1}}
    runner = ShadowRunner(
        lambda _: [TurnTrace(0.1, 1, (), ())],
        lambda _: [TurnTrace(0.1, 2, (), ())],
    )
    result = runner.run(scenario)
    assert result["primary"].passed
    assert not result["shadow"].passed
