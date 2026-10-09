#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

CONTRACT = HERE / 'release-contract.v0.1.json'
CATALOG = HERE / 'manifest.v0.1.json'
MATURITY = ROOT / 'interop' / 'conformance-maturity.v0.1.json'
CHANGELOG = HERE / 'CHANGELOG.md'
POLICY = HERE / 'RELEASE-POLICY.md'
ACTION = HERE / 'action.yml'


def main() -> None:
    errors: list[str] = []

    for path in (CONTRACT, CATALOG, MATURITY, CHANGELOG, POLICY, ACTION):
        if not path.is_file():
            errors.append(f'missing release dependency: {path.relative_to(ROOT)}')

    if errors:
        raise SystemExit('\n'.join(errors))

    contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    maturity = json.loads(MATURITY.read_text(encoding='utf-8'))

    if contract.get('schema') != 'spatialruntime.conformance-release-contract.v0.1':
        errors.append('release contract schema mismatch')

    pattern = contract.get('tag_pattern')
    try:
        tag_re = re.compile(str(pattern))
    except re.error as exc:
        errors.append(f'invalid tag_pattern: {exc}')
        tag_re = None

    if tag_re is not None:
        for sample in ('conformance-v0.1.0', 'conformance-v1.0.0'):
            if tag_re.fullmatch(sample) is None:
                errors.append(f'tag_pattern rejects valid sample: {sample}')
        for invalid in ('v0.1.0', 'conformance-0.1.0', 'conformance-v0.1'):
            if tag_re.fullmatch(invalid) is not None:
                errors.append(f'tag_pattern accepts invalid sample: {invalid}')

    required_checks = contract.get('required_checks')
    if not isinstance(required_checks, list) or not required_checks:
        errors.append('required_checks must be non-empty')

    expected_checks = {
        'interop/conformance/verify_catalog.py',
        'interop/external-results/verify_registry.py',
        'repository CI green on supported Python versions',
    }
    if isinstance(required_checks, list) and not expected_checks.issubset(set(required_checks)):
        errors.append('release contract is missing required evidence checks')

    modes = [p.get('mode') for p in catalog.get('profiles', []) if isinstance(p, dict)]
    if not modes or any(not isinstance(x, str) or not x for x in modes):
        errors.append('catalog contains invalid public mode')
    if len(set(modes)) != len(modes):
        errors.append('catalog contains duplicate public mode')

    maturity_ids = {
        s.get('id')
        for s in maturity.get('surfaces', [])
        if isinstance(s, dict) and isinstance(s.get('id'), str)
    }
    if not maturity_ids:
        errors.append('maturity matrix has no surfaces')

    if catalog.get('preferred_action') != 'interop/conformance':
        errors.append('preferred_action must remain interop/conformance')

    aliases = catalog.get('legacy_compatible_actions')
    if not isinstance(aliases, list) or 'interop/agent-effect-authority' not in aliases:
        errors.append('legacy AEA compatibility action missing from catalog')

    if 'No immutable conformance-v tag exists yet.' not in CHANGELOG.read_text(encoding='utf-8'):
        errors.append('changelog must state current no-tag release blocker')

    report = {
        'schema': contract.get('schema'),
        'catalog': catalog.get('schema'),
        'public_modes': sorted(modes),
        'maturity_surfaces': sorted(maturity_ids),
        'status': 'PASS' if not errors else 'FAIL',
        'errors': errors,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
