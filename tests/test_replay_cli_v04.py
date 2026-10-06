import json

from spatialruntime.cli import main
from spatialruntime.runtime.replay import make_bundle, validate_bundle, ReplayValidationError
from spatialruntime.scenarios import run_kitchen_living_demo


def test_valid_demo_bundle_replays():
    result = run_kitchen_living_demo()
    bundle = make_bundle(case_id=result["case_id"], traces=result["traces"])
    report = validate_bundle(bundle)
    assert report.valid is True
    assert report.trace_count == 2
    assert report.first_step == 0
    assert report.last_step == 1
    assert report.final_state_hash == result["traces"][-1]["next_runtime_state_hash"]


def test_tampered_trace_is_rejected():
    result = run_kitchen_living_demo()
    bundle = make_bundle(case_id=result["case_id"], traces=result["traces"])
    bundle["traces"][0]["next_runtime_state"]["window_kitchen"]["executed_state"]["open_ratio"] = 0.99
    try:
        validate_bundle(bundle)
    except ReplayValidationError as exc:
        assert "bundle hash mismatch" in str(exc) or "trace hash mismatch" in str(exc)
    else:
        raise AssertionError("tampered bundle should fail")


def test_cross_step_state_chain_is_rejected_even_with_rehashed_bundle():
    result = run_kitchen_living_demo()
    traces = [dict(t) for t in result["traces"]]
    traces[1] = dict(traces[1])
    traces[1]["runtime_state_before"] = {
        **traces[1]["runtime_state_before"],
        "window_kitchen": {"executed_state": {"open_ratio": 0.123}},
    }
    # Individual trace hashes are intentionally left stale: the validator must reject
    # before any caller can pass off a rewritten chain as valid.
    bundle = make_bundle(case_id=result["case_id"], traces=traces)
    try:
        validate_bundle(bundle)
    except ReplayValidationError as exc:
        assert "trace hash mismatch" in str(exc) or "runtime_state_before hash mismatch" in str(exc)
    else:
        raise AssertionError("broken chain should fail")


def test_cli_scenario_then_replay(tmp_path, capsys):
    out = tmp_path / "episode.json"
    assert main(["scenario", "kitchen-living", "-o", str(out)]) == 0
    assert out.exists()

    generated = json.loads(out.read_text(encoding="utf-8"))
    assert generated["schema"] == "runtime_episode_bundle_v0.4"
    assert len(generated["traces"]) == 2

    capsys.readouterr()
    assert main(["replay", str(out)]) == 0
    replay_stdout = json.loads(capsys.readouterr().out)
    assert replay_stdout["valid"] is True
    assert replay_stdout["trace_count"] == 2


def test_cli_replay_returns_nonzero_for_tampered_bundle(tmp_path, capsys):
    result = run_kitchen_living_demo()
    bundle = make_bundle(case_id=result["case_id"], traces=result["traces"])
    bundle["traces"][1]["status"] = "tampered"

    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    assert main(["replay", str(path)]) == 2
    err = json.loads(capsys.readouterr().err)
    assert err["valid"] is False


def test_cli_inspect_emits_step_summary(tmp_path, capsys):
    out = tmp_path / "episode.json"
    assert main(["scenario", "kitchen-living", "-o", str(out)]) == 0
    capsys.readouterr()

    assert main(["inspect", str(out)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["replay"]["valid"] is True
    assert [s["step"] for s in data["steps"]] == [0, 1]
    assert data["steps"][1]["safety_forced_entities"] == ["window_kitchen"]
