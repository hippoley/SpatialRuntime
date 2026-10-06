from __future__ import annotations
from typing import Any, Mapping
import copy, hashlib, json
from spatialruntime.safety.dependency_graph import compile_safety_graph

SCHEMA='spatial_safety_promotion_v3.7'
class UnsafeAutoPromotion(RuntimeError): pass

def _canon(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def _fp(x): return hashlib.sha256(_canon(x).encode()).hexdigest()

def promote_autocompiled_graph(report:Mapping[str,Any], *, min_evidence_confidence:float=0.95,
                               require_no_unresolved:bool=False)->dict[str,Any]:
    """Turn a v3.6 skeleton into a compiled graph only when evidence gates are satisfied."""
    catdoc=report.get('catalog') or {}; cat=catdoc.get('entities') or {}; ev=catdoc.get('evidence') or {}
    unresolved=list(catdoc.get('unresolved') or [])
    if require_no_unresolved and unresolved:
        raise UnsafeAutoPromotion(f'unresolved spatial relations remain: {len(unresolved)}')
    # Rules may only reference explicit entity IDs that exist. Any evidence-backed selector entity
    # must have all fields used for identity/room/exterior/facade at or above threshold.
    graph=copy.deepcopy(report.get('graph') or {})
    referenced=set()
    for r in graph.get('rules') or []:
        for eff in r.get('effects') or []:
            sel=eff.get('selector') or {}
            referenced.update(sel.get('ids') or [])
    weak=[]
    for eid in sorted(referenced):
        if eid not in cat: raise UnsafeAutoPromotion(f'rule references unknown entity {eid}')
        for fld in ('kind','room','exterior','facade'):
            if fld not in cat[eid]: continue
            p=(ev.get(eid) or {}).get(fld) or {}
            if float(p.get('confidence',0)) < float(min_evidence_confidence): weak.append({'entity_id':eid,'field':fld,'confidence':p.get('confidence')})
    if weak: raise UnsafeAutoPromotion(f'weak evidence blocks promotion: {weak}')
    compiled=compile_safety_graph(graph,cat)
    return {'schema':SCHEMA,'catalog_fingerprint':catdoc.get('fingerprint'),'autocompile_fingerprint':report.get('fingerprint'),
            'graph_fingerprint':compiled.fingerprint,'compiled_graph':compiled,'warnings':unresolved,
            'promotion_fingerprint':_fp({'catalog':catdoc.get('fingerprint'),'graph':compiled.fingerprint})}
