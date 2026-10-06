from __future__ import annotations
from typing import Any, Mapping, Sequence
import hashlib, json, copy
from spatialruntime.spatial.autocompile import compile_safety_graph_skeleton
from spatialruntime.spatial.promotion import promote_autocompiled_graph

SCHEMA='spatial_compile_bundle_v3.8'
class SpatialSourceDrift(RuntimeError): pass

def _canon(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def _fp(x): return hashlib.sha256(_canon(x).encode()).hexdigest()

def build_spatial_compile_bundle(scene:Mapping[str,Any], *, topology:Mapping[str,Any]|None=None,
                                 sensor_bindings:Sequence[Mapping[str,Any]]|None=None,
                                 templates:Mapping[str,Any]|None=None,
                                 min_evidence_confidence:float=.95)->dict[str,Any]:
    topo=topology or scene.get('topology') or {}
    sensors=list(sensor_bindings or []); tmpl=dict(templates or {})
    source_fingerprints={
        'scene':_fp(scene),
        'topology':_fp(topo),
        'sensor_bindings':_fp(sensors),
        'templates':_fp(tmpl),
    }
    report=compile_safety_graph_skeleton(scene,topology=topo,sensor_bindings=sensors,templates=tmpl)
    promoted=promote_autocompiled_graph(report,min_evidence_confidence=min_evidence_confidence)
    return {'schema':SCHEMA,'source_fingerprints':source_fingerprints,'autocompile_fingerprint':report['fingerprint'],
            'catalog_fingerprint':report['catalog']['fingerprint'],'graph_fingerprint':promoted['graph_fingerprint'],
            'graph':copy.deepcopy(report['graph']),'warnings':copy.deepcopy(promoted['warnings']),
            'min_evidence_confidence':float(min_evidence_confidence),
            'summary':copy.deepcopy(report['summary'])}

def verify_spatial_compile_bundle(bundle:Mapping[str,Any], scene:Mapping[str,Any], *, topology:Mapping[str,Any]|None=None,
                                  sensor_bindings:Sequence[Mapping[str,Any]]|None=None,
                                  templates:Mapping[str,Any]|None=None)->dict[str,Any]:
    if bundle.get('schema')!=SCHEMA: raise SpatialSourceDrift('unsupported bundle schema')
    topo=topology or scene.get('topology') or {}; sensors=list(sensor_bindings or []); tmpl=dict(templates or {})
    current={'scene':_fp(scene),'topology':_fp(topo),'sensor_bindings':_fp(sensors),'templates':_fp(tmpl)}
    expected=dict(bundle.get('source_fingerprints') or {})
    drift={k:{'expected':expected.get(k),'actual':v} for k,v in current.items() if expected.get(k)!=v}
    if drift: raise SpatialSourceDrift(f'spatial safety source drift: {drift}')
    threshold=float(bundle.get('min_evidence_confidence',.95))
    rebuilt=build_spatial_compile_bundle(scene,topology=topo,sensor_bindings=sensors,templates=tmpl,min_evidence_confidence=threshold)
    for k in ('autocompile_fingerprint','catalog_fingerprint','graph_fingerprint'):
        if rebuilt[k]!=bundle.get(k): raise SpatialSourceDrift(f'non-deterministic or stale compiled artifact: {k}')
    return {'verified':True,'graph_fingerprint':bundle['graph_fingerprint'],'source_fingerprints':current}
