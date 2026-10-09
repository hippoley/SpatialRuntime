from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "first-conformance-release.yml"


def test_first_conformance_release_is_green_main_only():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "github.event.workflow_run.head_branch == 'main'" in text
    assert "TAG: conformance-v0.1.0" in text
    assert 'GREEN_SHA: ${{ github.event.workflow_run.head_sha }}' in text


def test_existing_tag_controls_recovery_target():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'git fetch --force origin "refs/tags/$TAG:refs/tags/$TAG"' in text
    assert 'tag_commit="$(git rev-list -n 1 "$TAG")"' in text
    assert 'echo "release_sha=$tag_commit" >> "$GITHUB_OUTPUT"' in text
    assert 'release_sha=$GREEN_SHA' in text
    assert 'git checkout --detach "$RELEASE_SHA"' in text


def test_release_tag_is_annotated_and_never_force_moved():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "if: steps.target.outputs.tag_exists == 'false'" in text
    assert 'git tag -a "$TAG" "$RELEASE_SHA" -F /tmp/conformance-release.json' in text
    assert 'git push origin "refs/tags/$TAG"' in text
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


def test_release_page_is_idempotent_and_attaches_manifest():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'gh release view "$TAG"' in text
    assert 'gh release create "$TAG" /tmp/conformance-release.json' in text
    assert "--verify-tag" in text
    assert "GitHub Release $TAG already exists; leaving it unchanged." in text
