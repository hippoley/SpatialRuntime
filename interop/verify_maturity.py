#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MATURITY = ROOT / "interop" / "conformance-maturity.v0.1.json"
CATALOG = ROOT / "interop" / "conformance" / "manifest.v0.1.json"
SEMANTIC = {"experimental","candidate","stable","deprecated"}
EVIDENCE = {"self-tested","external-source-reviewed","externally-executed","externally-reproduced","externally-consumed"}
def main() -> None:
    maturity=json.loads(MATURITY.read_text(encoding="utf-8"))
    catalog=json.loads(CATALOG.read_text(encoding="utf-8"))
    errors=[]
    modes=[p.get("mode") for p in catalog.get("profiles",[]) if isinstance(p,dict)]
    modes=[m for m in modes if isinstance(m,str) and m]
    counts=Counter()
    for i,s in enumerate(maturity.get("surfaces",[])):
        sid=s.get("id",f"surfaces[{i}]")
        if s.get("semantic_maturity") not in SEMANTIC: errors.append(f"{sid}: invalid semantic_maturity")
        if s.get("evidence_maturity") not in EVIDENCE: errors.append(f"{sid}: invalid evidence_maturity")
        covered=s.get("catalog_modes",[])
        if not isinstance(covered,list):
            errors.append(f"{sid}: catalog_modes must be a list"); continue
        for mode in covered:
            if not isinstance(mode,str) or not mode: errors.append(f"{sid}: invalid catalog mode {mode!r}")
            else: counts[mode]+=1
    for mode in modes:
        if counts[mode]==0: errors.append(f"{mode}: missing maturity coverage")
        elif counts[mode]>1: errors.append(f"{mode}: maturity coverage duplicated {counts[mode]} times")
    unknown=sorted(set(counts)-set(modes))
    if unknown: errors.append("maturity references unknown catalog modes: "+", ".join(unknown))
    if errors: raise SystemExit("\n".join(errors))
    print(json.dumps({"catalog_modes":len(modes),"covered_once":sorted(modes),"status":"PASS"},sort_keys=True))
if __name__=="__main__": main()
