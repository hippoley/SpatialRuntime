from pathlib import Path

PUBLISH = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "publish-conformance-v02.yml"


def _source():
    return PUBLISH.read_text(encoding="utf-8")


def test_publish_only_with_explicit_issue_owner_command():
    s = _source()
    for needle in (
        "issue_comment:",
        "types: [created]",
        "github.event.issue.number == 104",
        "github.event.issue.pull_request == null",
        "github.actor == 'hippoley'",
        "github.event.comment.author_association == 'OWNER'",
        "github.event.comment.body == '/publish-conformance-v0.2.0'",
        "concurrency:",
    ):
        assert needle in s
    assert "workflow_run:" not in s
    assert "workflow_dispatch:" not in s
    assert "on:\n  push:" not in s


def test_source_and_artifact_are_pinned_to_actual_successful_candidate():
    s = _source()
    for needle in (
        "SOURCE_SHA: 8668ba93ad689fea5957de46d98cd138d8ac7865",
        "MANIFEST_SHA256: 25ed96cb44c66d2d62f3372ac663ffd3e6d3f41fb21a4024e31f169eac047e13",
        "CANDIDATE_RUN: '45965585857'",
        "CANDIDATE_ARTIFACT: '15181404876'",
        "ARTIFACT_ZIP_DIGEST: sha256:13ba2f8e9ea9cc6c1b2a2c87953ecae9463c5cc4a982b629aa74c11d4eda6b84",
        "MAIN_CI_RUN: '45965514662'",
        "git merge-base --is-ancestor",
        "sha256sum --check --status",
        ".expired == false",
    ):
        assert needle in s


def test_publication_is_nonforce_and_bytes_verified():
    s = _source()
    assert 'git tag -a "$TAG" "$SOURCE_SHA" -F /tmp/conformance-release.json' in s
    assert 'git push origin "refs/tags/$TAG"' in s
    assert "git push --force" not in s
    assert "git tag -f" not in s
    assert 'gh release create "$TAG" /tmp/conformance-release.json' in s
    assert "cmp /tmp/conformance-release.json /tmp/published/conformance-release.json" in s
    assert 'test "$(git rev-list -n 1 "$TAG")" = "$SOURCE_SHA"' in s
