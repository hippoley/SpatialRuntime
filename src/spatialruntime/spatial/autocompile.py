from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
import copy, hashlib, json

SCHEMA='spatial_safety_autocompile_v3.6'
CATALOG_SCHEMA='spatial_entity_catalog_v3.6'
GRAPH_SCHEMA='whole_home_safety_graph_v3.3'

class SpatialCompileError(RuntimeError): pass


def _canon(x:Any)->str:
    return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)

def _fingerprint(x:Any)->str:
    return hashlib.sha256(_canon(x).encode()).hexdigest()

def _prov(source:str,confidence:float,kind:str='derived',note:str|None=None)->dict[str,Any]:
    out={'source':source,'confidence':float(confidence),'kind':kind}
    if note: out['note']=note
    return out

def _room_conf(entity:Mapping[str,Any])->float:
    p=((entity.get('semantics') or {}).get('provenance') or {})
    try:return float(p.get('confidence',0.0))
    except:return 0.0

def build_spatial_entity_catalog(scene:Mapping[str,Any], *, topology:Mapping[str,Any]|None=None,
                                 sensor_bindings:Sequence[Mapping[str,Any]]|None=None)->dict[str,Any]:
    """Build conservative selector metadata from executable scene/topology.

    Only explicit or provenance-backed facts become selector attributes. Unknown facade/coverage
    is left unresolved instead of guessed from object position.
    """
    topo=topology or scene.get('topology') or {}
    catalog:dict[str,dict[str,Any]]={}
    evidence:dict[str,dict[str,Any]]={}
    unresolved:list[dict[str,Any]]=[]
    boundaries={str(x.get('id')):x for x in topo.get('boundaries') or [] if x.get('id')}

    for room in topo.get('rooms') or []:
        rid=str(room.get('id') or '')
        if not rid: continue
        catalog[rid]={'kind':'room','room':rid,'name':room.get('name')}
        evidence[rid]={'room':_prov('topology.rooms',1.0,'explicit')}

    for op in topo.get('openings') or []:
        eid=str(op.get('id') or '')
        if not eid: continue
        connects=list(op.get('connects') or [])
        rooms=[x for x in connects if x!='exterior']
        exterior='exterior' in connects
        meta={'kind':str(op.get('kind') or 'opening'),'exterior':exterior}
        ev={'kind':_prov('topology.openings.kind',1.0,'explicit'),'exterior':_prov('topology.openings.connects',1.0,'explicit')}
        if len(rooms)==1:
            meta['room']=rooms[0]; ev['room']=_prov('topology.openings.connects',1.0,'explicit')
        elif len(rooms)>1:
            meta['rooms']=sorted(rooms); ev['rooms']=_prov('topology.openings.connects',1.0,'explicit')
        bid=op.get('boundary_id')
        if bid:
            meta['boundary_id']=bid; ev['boundary_id']=_prov('topology.openings.boundary_id',1.0,'explicit')
            b=boundaries.get(str(bid)) or {}
            # A reviewed/explicit opening-level facade is more specific than the wall default.
            if op.get('facade'):
                meta['facade']=op['facade']; ev['facade']=_prov('topology.openings.facade',1.0,'explicit')
            elif b.get('facade'):
                meta['facade']=b['facade']; ev['facade']=_prov('topology.boundaries.facade',1.0,'explicit')
            elif exterior:
                unresolved.append({'entity_id':eid,'field':'facade','reason':'exterior opening has no explicit/reviewed facade'})
        catalog[eid]=meta; evidence[eid]=ev

    for ent in scene.get('entities') or []:
        eid=str(ent.get('id') or '')
        if not eid: continue
        sem=ent.get('semantics') or {}; typ=str(sem.get('type') or '')
        kind='object'
        if typ=='appliance.range_hood' or bool((ent.get('physics') or {}).get('airflow_source')): kind='hood'
        elif typ.startswith('appliance.'): kind='appliance'
        elif typ.startswith('sensor.'): kind='sensor'
        meta={'kind':kind,'semantic_type':typ or None}; ev={'kind':_prov('scene.entities.semantics.type',float((ent.get('source') or {}).get('confidence',0.5)),'derived')}
        room=sem.get('room_id')
        if room:
            conf=_room_conf(ent)
            if conf>=0.8:
                meta['room']=room; ev['room']=_prov('scene.entities.semantics.room_id',conf,'derived')
            else:
                unresolved.append({'entity_id':eid,'field':'room','reason':'room assignment below auto-promotion confidence','confidence':conf})
        caps=((ent.get('thing_model') or {}).get('capabilities') or [])
        if caps: meta['capabilities']=sorted(set(map(str,caps))); ev['capabilities']=_prov('scene.entities.thing_model.capabilities',1.0,'explicit')
        catalog[eid]=meta; evidence[eid]=ev

    # Device bindings may expose operational device IDs distinct from scene entity IDs.
    for b in topo.get('device_bindings') or []:
        did=str(b.get('device_id') or '')
        sid=str(b.get('scene_entity_id') or '')
        if not did: continue
        base=copy.deepcopy(catalog.get(sid) or {'kind':'device'})
        if base.get('kind')=='object': base['kind']='device'
        base['scene_entity_id']=sid or None
        base['device_id']=did
        catalog[did]=base
        evidence[did]=copy.deepcopy(evidence.get(sid) or {})
        evidence[did]['device_id']=_prov('topology.device_bindings.device_id',1.0,'explicit')
        if sid: evidence[did]['scene_entity_id']=_prov('topology.device_bindings.scene_entity_id',1.0,'explicit')

    for s in sensor_bindings or []:
        sid=str(s.get('sensor_id') or '')
        if not sid: continue
        meta=catalog.setdefault(sid,{'kind':'sensor'})
        ev=evidence.setdefault(sid,{'kind':_prov('sensor_bindings',1.0,'explicit')})
        room=s.get('room_id'); facade=s.get('facade'); covers=s.get('covers')
        if room: meta['room']=room; ev['room']=_prov('sensor_bindings.room_id',1.0,'explicit')
        if facade: meta['facade']=facade; ev['facade']=_prov('sensor_bindings.facade',1.0,'explicit')
        if covers:
            meta['covers']=sorted(set(map(str,covers))); ev['covers']=_prov('sensor_bindings.covers',1.0,'explicit')

    payload={'schema':CATALOG_SCHEMA,'entities':dict(sorted(catalog.items())),'evidence':dict(sorted(evidence.items())),'unresolved':sorted(unresolved,key=lambda x:(x['entity_id'],x['field']))}
    payload['fingerprint']=_fingerprint({k:payload[k] for k in ['schema','entities','evidence','unresolved']})
    return payload


def compile_safety_graph_skeleton(scene:Mapping[str,Any], *, topology:Mapping[str,Any]|None=None,
                                  sensor_bindings:Sequence[Mapping[str,Any]]|None=None,
                                  templates:Mapping[str,Any]|None=None)->dict[str,Any]:
    """Compile only evidence-backed safety graph skeleton rules.

    Default rules require runtime context paths but never invent sensors or device semantics.
    """
    catdoc=build_spatial_entity_catalog(scene,topology=topology,sensor_bindings=sensor_bindings)
    cat=catdoc['entities']; rules=[]; skipped=[]
    t=dict(templates or {})

    ext_windows=sorted(e for e,m in cat.items() if m.get('kind')=='window' and m.get('exterior') is True)
    if ext_windows:
        rules.append({'id':'auto.rain.exterior_windows','priority':90,
                      'when':{'path':t.get('rain_path','sensors.rain.value'),'op':'eq','value':t.get('rain_wet_value','wet')},
                      'effects':[{'kind':'constrain','selector':{'ids':ext_windows},'property':'open_ratio','op':'max','value':0.0}],
                      'provenance':_prov('spatial_autocompile: explicit exterior opening connectivity',1.0,'generated')})
    else: skipped.append({'template':'rain','reason':'no explicit exterior windows'})

    # Facade wind rules only when facade is explicit, never inferred from coordinates.
    by_facade:dict[str,list[str]]={}
    for eid,m in cat.items():
        if m.get('kind')=='window' and m.get('exterior') is True and m.get('facade'):
            by_facade.setdefault(str(m['facade']),[]).append(eid)
    for facade,ids in sorted(by_facade.items()):
        path=(t.get('wind_paths') or {}).get(facade)
        threshold=(t.get('wind_thresholds_m_s') or {}).get(facade)
        if path is None or threshold is None:
            skipped.append({'template':'facade_wind','facade':facade,'reason':'explicit facade exists but no configured wind path/threshold'})
            continue
        rules.append({'id':f'auto.wind.{facade}','priority':85,
                      'when':{'path':path,'op':'gt','value':float(threshold)},
                      'effects':[{'kind':'constrain','selector':{'ids':sorted(ids)},'property':'open_ratio','op':'max','value':0.0}],
                      'provenance':_prov('spatial_autocompile: explicit boundary facade + configured threshold',1.0,'generated')})

    # Mechanical make-up-air skeleton is generated only if hood room and an exterior window in the same room are explicit.
    # Group hoods by room. Prefer an operational device binding over its scene-entity alias so
    # one physical hood cannot create duplicate room-level rules.
    hoods_by_room:dict[str,list[tuple[str,dict[str,Any]]]]={}
    for e,m in cat.items():
        if m.get('kind')=='hood' and m.get('room'):
            hoods_by_room.setdefault(str(m['room']),[]).append((e,m))
    for room,candidates in sorted(hoods_by_room.items()):
        candidates=sorted(candidates,key=lambda x:(0 if x[1].get('device_id') else 1,x[0]))
        hid,hm=candidates[0]
        aliases=[e for e,_ in candidates[1:]]
        wins=sorted(e for e,m in cat.items() if m.get('kind')=='window' and m.get('exterior') is True and m.get('room')==room)
        if not wins:
            skipped.append({'template':'makeup_air','hood':hid,'room':room,'aliases':aliases,'reason':'no explicit same-room exterior window'}); continue
        # Actual trigger and operating values are reviewed policy, never derived from geometry.
        min_open=(t.get('makeup_air_min_open_ratio') or {}).get(room)
        min_fan=(t.get('makeup_air_min_fan_level') or {}).get(room)
        trigger=(t.get('cooking_paths') or {}).get(room)
        if trigger is None or min_open is None or min_fan is None:
            skipped.append({'template':'makeup_air','hood':hid,'room':room,'aliases':aliases,'candidate_windows':wins,
                            'reason':'spatial relation is known but operating thresholds/trigger are not reviewed'})
            continue
        fact=f'auto_makeup_{room}'
        rules.append({'id':f'auto.makeup.fact.{room}','when':{'path':trigger,'op':'truthy'},
                      'effects':[{'kind':'set_fact','key':fact,'value':True}],
                      'provenance':_prov('spatial_autocompile: reviewed trigger + explicit room relation',1.0,'generated')})
        rules.append({'id':f'auto.makeup.apply.{room}','when':{'path':f'facts.{fact}','op':'truthy'},
                      'effects':[{'kind':'emit_change','selector':{'ids':[hid]},'changes':{'fan_level':min_fan}},
                                 {'kind':'constrain','selector':{'ids':wins},'property':'open_ratio','op':'min','value':float(min_open)}],
                      'provenance':_prov('spatial_autocompile: explicit hood/window room co-membership + reviewed values',1.0,'generated')})

    graph={'schema':GRAPH_SCHEMA,'rules':rules}
    report={'schema':SCHEMA,'catalog':catdoc,'graph':graph,'skipped':skipped,
            'summary':{'entities':len(cat),'rules_generated':len(rules),'unresolved':len(catdoc['unresolved']),'skipped_templates':len(skipped)}}
    report['fingerprint']=_fingerprint({'catalog_fingerprint':catdoc['fingerprint'],'graph':graph,'skipped':skipped})
    return report
