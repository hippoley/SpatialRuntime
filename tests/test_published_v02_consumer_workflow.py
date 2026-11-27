from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "published-conformance-v02-consumer.yml"


def test_consumer_pins_actual_published_tag_not_main():
    s = WORKFLOW.read_text(encoding="utf-8")
    ref = "hippoley/SpatialRuntime/interop/conformance@conformance-v0.2.0"
    assert s.count(ref) == 3
    assert "interop/conformance@main" not in s
    assert "require_result: PASS" in s


def test_released_action_preserves_three_state_and_failing_receipts():
    s = WORKFLOW.read_text(encoding="utf-8")
    for name in ("released_pass", "released_unresolved", "released_fail"):
        assert f"id: {name}" in s
    assert s.count("outputs.conformance_result") == 3
    for expected in ("PASS", "UNRESOLVED", "FAIL"):
        assert f'= "{expected}"' in s
    for path in ("pass.json", "unresolved.json", "fail.json"):
        assert f"published-receipts/{path}" in s
    assert s.count("continue-on-error: true") == 2
    assert "actions/upload-artifact@v4" in s
    assert "if: always()" in s
    assert "external_effect_confirmation" in s
