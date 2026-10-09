from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "first-conformance-release.yml"


def test_first_conformance_release_is_green_main_only():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "github.event.workflow_run.head_branch == 'main'" in text
    assert 'TAG: conformance-v0.1.0' in text
    assert 'RELEASE_SHA: ${{ github.event.workflow_run.head_sha }}' in text


def test_release_tag_is_annotated_and_never_force_moved():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'git tag -a "$TAG" "$RELEASE_SHA" -F /tmp/conformance-release.json' in text
    assert 'git push origin "refs/tags/$TAG"' in text
    assert "immutable release tags are never moved or overwritten" in text
    assert "git tag -f" not in text
    assert "git push --force" not in text
    assert "git push -f" not in text


def test_release_rechecks_contract_and_p0_before_tagging():
    text = WORKFLOW.read_text(encoding="utf-8")
    required = [
        "python interop/conformance/verify_catalog.py",
        "python interop/external-results/verify_registry.py",
        "python interop/conformance/verify_release_contract.py",
        "python docs/verify_p0_closure.py",
        '--commit "$RELEASE_SHA"',
    ]
    for marker in required:
        assert marker in text
