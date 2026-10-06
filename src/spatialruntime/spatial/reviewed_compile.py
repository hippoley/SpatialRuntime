from __future__ import annotations
from typing import Any, Mapping, Sequence
import copy, hashlib, json
from spatialruntime.spatial.resolver import resolve_spatial_relations
from spatialruntime.spatial.review import build_review_bundle, apply_reviewed_relations
from spatialruntime.spatial.compile_lineage import build_spatial_compile_bundle, verify_spatial_compile_bundle

SCHEMA='reviewed_spatial_compile_bundle_v4.1'
class ReviewedSpatialDrift(RuntimeError): pass

def _canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def _fp(x):return hashlib.sha256(_canon(x).encode()).hexdigest()

def build_reviewed_spatial_compile_bundle(scene:Mapping[str,Any], *, topology:Mapping[str,Any],
                                          sensor_bindings:Sequence[Mapping[str,Any]]|None=None,
                                          templates:Mapping[str,Any]|None=None,
                                          review_decisions:Sequence[Mapping[str,Any]]|None=None,
                                          min_candidate_confidence:float=.90,
                                          min_evidence_confidence:float=.95)->dict[str,Any]:
    topo=copy.deepcopy(topology); sensors=copy.deepcopy(list(sensor_bindings or [])); decisions=copy.deepcopy(list(review_decisions or []))
    candidates=resolve_spatial_relations(scene,topology=topo,sensor_bindings=sensors)
    review=build_review_bundle(candidates,decisions,min_candidate_confidence=min_candidate_confidence)
    reviewed_topo,reviewed_sensors=apply_reviewed_relations(topo,sensors,review)
    compiled=build_spatial_compile_bundle(scene,topology=reviewed_topo,sensor_bindings=reviewed_sensors,
                                          templates=templates,min_evidence_confidence=min_evidence_confidence)
    out={'schema':SCHEMA,
         'source_fingerprints':{'scene':_fp(scene),'topology':_fp(topo),'sensor_bindings':_fp(sensors),'templates':_fp(dict(templates or {}))},
         'candidate_fingerprint':candidates['fingerprint'],'review_fingerprint':review['fingerprint'],
         'review_decisions':decisions,'min_candidate_confidence':float(min_candidate_confidence),
         'reviewed_topology_fingerprint':_fp(reviewed_topo),'reviewed_sensor_bindings_fingerprint':_fp(reviewed_sensors),
         'spatial_compile_bundle':compiled,
         'summary':{'candidate_relations':len(candidates.get('relations') or []),'accepted_relations':len(review.get('accepted') or []),
                    'rejected_relations':len(review.get('rejected') or []),'graph_rules':len((compiled.get('graph') or {}).get('rules') or [])}}
    out['fingerprint']=_fp({k:out[k] for k in ['schema','source_fingerprints','candidate_fingerprint','review_fingerprint','review_decisions','min_candidate_confidence','reviewed_topology_fingerprint','reviewed_sensor_bindings_fingerprint','spatial_compile_bundle']})
    return out

def verify_reviewed_spatial_compile_bundle(bundle:Mapping[str,Any], scene:Mapping[str,Any], *, topology:Mapping[str,Any],
                                           sensor_bindings:Sequence[Mapping[str,Any]]|None=None,
                                           templates:Mapping[str,Any]|None=None)->dict[str,Any]:
    if bundle.get('schema')!=SCHEMA: raise ReviewedSpatialDrift('unsupported reviewed spatial compile schema')
    topo=copy.deepcopy(topology); sensors=copy.deepcopy(list(sensor_bindings or [])); tmpl=dict(templates or {})
    current={'scene':_fp(scene),'topology':_fp(topo),'sensor_bindings':_fp(sensors),'templates':_fp(tmpl)}
    if current!=bundle.get('source_fingerprints'): raise ReviewedSpatialDrift('source drift before reviewed spatial compile')
    candidates=resolve_spatial_relations(scene,topology=topo,sensor_bindings=sensors)
    if candidates['fingerprint']!=bundle.get('candidate_fingerprint'): raise ReviewedSpatialDrift('spatial relation candidate drift')
    review=build_review_bundle(candidates,bundle.get('review_decisions') or [],min_candidate_confidence=float(bundle.get('min_candidate_confidence',.90)))
    if review['fingerprint']!=bundle.get('review_fingerprint'): raise ReviewedSpatialDrift('review decision drift')
    reviewed_topo,reviewed_sensors=apply_reviewed_relations(topo,sensors,review)
    if _fp(reviewed_topo)!=bundle.get('reviewed_topology_fingerprint') or _fp(reviewed_sensors)!=bundle.get('reviewed_sensor_bindings_fingerprint'):
        raise ReviewedSpatialDrift('review application drift')
    verify_spatial_compile_bundle(bundle['spatial_compile_bundle'],scene,topology=reviewed_topo,sensor_bindings=reviewed_sensors,templates=tmpl)
    rebuilt=build_reviewed_spatial_compile_bundle(scene,topology=topo,sensor_bindings=sensors,templates=tmpl,
        review_decisions=bundle.get('review_decisions') or [],min_candidate_confidence=float(bundle.get('min_candidate_confidence',.90)),
        min_evidence_confidence=float((bundle.get('spatial_compile_bundle') or {}).get('min_evidence_confidence',.95)))
    if rebuilt['fingerprint']!=bundle.get('fingerprint'): raise ReviewedSpatialDrift('reviewed spatial artifact is stale or non-deterministic')
    return {'verified':True,'fingerprint':bundle['fingerprint'],'graph_fingerprint':bundle['spatial_compile_bundle']['graph_fingerprint']}
