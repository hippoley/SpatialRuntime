from __future__ import annotations
from typing import Any, Mapping, Sequence
import hashlib,json

SCHEMA='reviewed_spatial_relations_v4.0'
class SpatialReviewError(RuntimeError): pass

def _canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def _fp(x):return hashlib.sha256(_canon(x).encode()).hexdigest()

def build_review_bundle(candidate_doc:Mapping[str,Any], decisions:Sequence[Mapping[str,Any]], *, min_candidate_confidence:float=.90)->dict[str,Any]:
    bykey={(r['entity_id'],r['relation']):r for r in candidate_doc.get('relations') or []}
    accepted=[]; rejected=[]; seen=set()
    for d in decisions:
        key=(str(d.get('entity_id') or ''),str(d.get('relation') or ''))
        if key in seen: raise SpatialReviewError(f'duplicate review decision {key}')
        seen.add(key); c=bykey.get(key)
        if not c: raise SpatialReviewError(f'review target not found {key}')
        action=str(d.get('action') or '')
        if action not in {'accept','reject','override'}: raise SpatialReviewError(f'invalid review action {action}')
        actor=str(d.get('actor') or '')
        reason=str(d.get('reason') or '')
        if not actor or not reason: raise SpatialReviewError('review requires actor and reason')
        if action=='accept':
            if c.get('status') not in {'explicit','candidate'}: raise SpatialReviewError(f'cannot accept {c.get("status")} relation without override')
            if c.get('status')=='candidate' and float(c.get('confidence',0))<min_candidate_confidence: raise SpatialReviewError('candidate below review auto-accept threshold; use override with evidence')
            value=c.get('value')
        elif action=='override':
            if 'value' not in d: raise SpatialReviewError('override requires value')
            value=d['value']
        else:
            rejected.append({'entity_id':key[0],'relation':key[1],'candidate':c,'actor':actor,'reason':reason}); continue
        accepted.append({'entity_id':key[0],'relation':key[1],'value':value,'status':'reviewed','confidence':1.0,
                         'review':{'action':action,'actor':actor,'reason':reason,'candidate_fingerprint':_fp(c)},'candidate':c})
    accepted=sorted(accepted,key=lambda x:(x['relation'],x['entity_id']))
    out={'schema':SCHEMA,'candidate_fingerprint':candidate_doc.get('fingerprint'),'min_candidate_confidence':float(min_candidate_confidence),
         'accepted':accepted,'rejected':sorted(rejected,key=lambda x:(x['relation'],x['entity_id']))}
    out['fingerprint']=_fp({k:out[k] for k in ['schema','candidate_fingerprint','min_candidate_confidence','accepted','rejected']})
    return out

def apply_reviewed_relations(topology:Mapping[str,Any], sensor_bindings:Sequence[Mapping[str,Any]]|None, review_bundle:Mapping[str,Any])->tuple[dict[str,Any],list[dict[str,Any]]]:
    topo=json.loads(json.dumps(topology)); sensors=json.loads(json.dumps(list(sensor_bindings or [])))
    bounds={str(b.get('id')):b for b in topo.get('boundaries') or [] if b.get('id')}
    opens={str(o.get('id')):o for o in topo.get('openings') or [] if o.get('id')}
    sens={str(s.get('sensor_id')):s for s in sensors if s.get('sensor_id')}
    for r in review_bundle.get('accepted') or []:
        eid,rel,val=str(r['entity_id']),str(r['relation']),r.get('value')
        if rel=='facade':
            op=opens.get(eid)
            if not op: raise SpatialReviewError(f'facade target opening missing {eid}')
            op['facade']=val
            op.setdefault('reviewed_relations',{})['facade']={'review_bundle_fingerprint':review_bundle.get('fingerprint'),'provenance':'reviewed spatial relation v4.0'}
        elif rel=='covers_room':
            s=sens.get(eid)
            if not s: raise SpatialReviewError(f'sensor target missing {eid}')
            s['room_id']=val
            s.setdefault('reviewed_relations',{})['room_id']={'review_bundle_fingerprint':review_bundle.get('fingerprint'),'provenance':'reviewed spatial relation v4.0'}
        else: raise SpatialReviewError(f'unsupported reviewed relation {rel}')
    return topo,sensors
