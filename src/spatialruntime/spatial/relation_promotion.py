from __future__ import annotations
from typing import Any, Mapping, Sequence
import hashlib, json

SCHEMA='spatial_relation_promotion_v4.3'
class SpatialRelationPromotionError(RuntimeError): pass

def _canon(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def _fp(x): return hashlib.sha256(_canon(x).encode()).hexdigest()

def promote_relations(derived_doc:Mapping[str,Any], *, decisions:Sequence[Mapping[str,Any]]|None=None,
                      min_auto_confidence:float=.95)->dict[str,Any]:
    decisions=list(decisions or [])
    dmap={(str(d.get('src')),str(d.get('rel')),str(d.get('dst'))):d for d in decisions}
    promoted=[]; held=[]
    for r in derived_doc.get('relations') or []:
        key=(r['src'],r['rel'],r['dst']); d=dmap.get(key)
        # Only pure derived relations can auto-promote at high confidence. Candidates always need review.
        if r.get('status')=='derived' and float(r.get('confidence',0))>=float(min_auto_confidence) and d is None:
            x=dict(r); x['promotion']={'mode':'auto','threshold':float(min_auto_confidence)}; promoted.append(x); continue
        if d is None:
            held.append({'relation':r,'reason':'review_required'}); continue
        action=d.get('action')
        if action=='reject': held.append({'relation':r,'reason':'review_rejected','decision':dict(d)}); continue
        if action!='accept': raise SpatialRelationPromotionError(f'unsupported decision action: {action}')
        if not d.get('actor') or not d.get('reason'): raise SpatialRelationPromotionError('accepted relation requires actor and reason')
        x=dict(r); x['promotion']={'mode':'reviewed','actor':d['actor'],'reason':d['reason']}; promoted.append(x)
    out={'schema':SCHEMA,'source_fingerprint':derived_doc.get('fingerprint'),'min_auto_confidence':float(min_auto_confidence),
         'decisions':decisions,'promoted':promoted,'held':held,
         'summary':{'promoted':len(promoted),'held':len(held)}}
    out['fingerprint']=_fp({k:out[k] for k in ['schema','source_fingerprint','min_auto_confidence','decisions','promoted','held']})
    return out
