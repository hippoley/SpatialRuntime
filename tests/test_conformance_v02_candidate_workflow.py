from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "conformance-v02-candidate.yml"


def test_v02_candidate_auto_records_only_read_only_evidence():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "workflow_run:" in text
    assert 'workflows: ["CI"]' in text
    assert "types: [completed]" in text
    assert "github.event.workflow_run.event == 'push'" in text
    assert "github.event.workflow_run.head_branch == 'main'" in text
    assert "github.event.workflow_run.head_repository.full_name == github.repository" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "push:" not in text
    assert "contents: read" in text
    assert "actions: read" in text
    assert "contents: write" not in text
    assert "id-token: write" not in text
    assert "persist-credentials: false" in text
    assert "gh release create" not in text
    assert "git push " not in text
    assert "git tag -a" not in text


def test_candidate_is_exact_current_green_main_and_new_tag():
    text = WORKFLOW.read_text(encoding="utf-8")
    for required in (
        'test "$GITHUB_REF" = "refs/heads/main"',
        'test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"',
        'test "$(git rev-parse origin/main)" = "$EXPECTED_SHA"',
        'git ls-remote --exit-code --tags origin "refs/tags/$TAG"',
        'select(.event == "push" and .head_sha == env.EXPECTED_SHA and .conclusion == "success")',
        'test -s /tmp/release-ci-runs.txt',
        "TAG: conformance-v0.2.0",
        "github.event_name == 'workflow_run' && github.event.workflow_run.head_sha || github.sha",
        "ref: ${{ env.EXPECTED_SHA }}",
        "conformance-v0.2.0-UNPUBLISHED-candidate-${{ env.EXPECTED_SHA }}",
    ):
        assert required in text


def test_candidate_revalidates_and_retains_nonpublication_evidence():
    text = WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "python interop/conformance/verify_catalog.py",
        "python interop/external-results/verify_registry.py",
        "python interop/verify_maturity.py",
        "python docs/verify_p0_closure.py",
        "python interop/conformance/verify_release_contract.py",
        '--tag "$TAG"',
        '--commit "$EXPECTED_SHA"',
        "sha256sum release-candidate/conformance-release.json",
        "STATUS=UNPUBLISHED_CANDIDATE",
        "actions/upload-artifact@v4",
        "if-no-files-found: error",
    ):
        assert required in text
