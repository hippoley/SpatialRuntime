from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SURFACES = [
    ROOT / "README.md",
    ROOT / "interop" / "conformance" / "README.md",
    ROOT / "interop" / "conformance" / "examples" / "github-action.yml",
    ROOT / "interop" / "conformance" / "examples" / "README.md",
]


def test_public_conformance_quickstarts_pin_first_release():
    for path in PUBLIC_SURFACES:
        text = path.read_text(encoding="utf-8")
        if "hippoley/SpatialRuntime/interop/conformance@" in text:
            assert "hippoley/SpatialRuntime/interop/conformance@conformance-v0.1.0" in text


def test_neutral_public_quickstarts_do_not_use_placeholder_or_old_bootstrap_sha():
    forbidden = [
        "hippoley/SpatialRuntime/interop/conformance@<pinned-sha>",
        "hippoley/SpatialRuntime/interop/conformance@ce7cce687e623ed16f9c60db782bed05e9b117ba",
    ]
    for path in PUBLIC_SURFACES:
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in text, f"{path}: stale public pin {marker}"
