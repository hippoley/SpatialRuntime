from __future__ import annotations
from typing import Any, Mapping, Sequence
import hashlib, json
from collections import defaultdict, deque

SCHEMA='spatial_relation_graph_v4.2'
QUERY_SCHEMA='spatial_relation_query_v4.2'

class SpatialRelationGraphError(RuntimeError): pass


def _canon(x:Any)->str:
    return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)

def _fp(x:Any)->str:
    return hashlib.sha256(_canon(x).encode()).hexdigest()

def _edge(src:str, rel:str, dst:str, *, confidence:float, source:str, kind:str='derived', evidence:Mapping[str,Any]|None=None)->dict[str,Any]:
    if not src or not dst: raise SpatialRelationGraphError('edge endpoints required')
    c=float(confidence)
    if not (0.0<=c<=1.0): raise SpatialRelationGraphError('confidence must be in [0,1]')
    out={'src':src,'rel':rel,'dst':dst,'confidence':c,'provenance':{'source':source,'kind':kind}}
    if evidence: out['evidence']=dict(evidence)
    return out


def build_spatial_relation_graph(*, catalog_doc:Mapping[str,Any], topology:Mapping[str,Any]|None=None,
                                 sensor_bindings:Sequence[Mapping[str,Any]]|None=None)->dict[str,Any]:
    """Build an explainable relation graph from reviewed/explicit spatial facts.

    The graph does not invent facade, coverage, airflow or control thresholds. It only lifts facts
    already present in the reviewed catalog/topology into traversable typed edges.
    """
    cat=catalog_doc.get('entities') or {}
    evdoc=catalog_doc.get('evidence') or {}
    topo=topology or {}
    edges=[]
    seen=set()
    def add(e):
        k=(e['src'],e['rel'],e['dst'])
        if k in seen: return
        seen.add(k); edges.append(e)

    # Entity -> room membership and inverse containment.
    for eid,meta in sorted(cat.items()):
        room=meta.get('room')
        if room:
            conf=float((((evdoc.get(eid) or {}).get('room') or {}).get('confidence',1.0)))
            add(_edge(eid,'belongs_to',str(room),confidence=conf,source='spatial_entity_catalog.room'))
            add(_edge(str(room),'contains',eid,confidence=conf,source='inverse:belongs_to'))
        for room in meta.get('rooms') or []:
            conf=float((((evdoc.get(eid) or {}).get('rooms') or {}).get('confidence',1.0)))
            add(_edge(eid,'connects_room',str(room),confidence=conf,source='spatial_entity_catalog.rooms'))
        if meta.get('facade'):
            conf=float((((evdoc.get(eid) or {}).get('facade') or {}).get('confidence',1.0)))
            facade=f"facade::{meta['facade']}"
            add(_edge(eid,'lies_on',facade,confidence=conf,source='spatial_entity_catalog.facade'))
        if meta.get('kind')=='window' and meta.get('exterior') is True and room:
            add(_edge(eid,'supplies_air_to',str(room),confidence=1.0,source='topology.exterior_window',kind='explicit'))
        if meta.get('kind')=='hood' and room:
            add(_edge(eid,'exhausts',str(room),confidence=1.0,source='scene/topology.hood_room'))

    # Sensor coverage is stronger when explicitly reviewed as covers_room/covers.
    for s in sensor_bindings or []:
        sid=str(s.get('sensor_id') or '')
        if not sid: continue
        covers=[]
        if s.get('room_id'): covers.append(str(s['room_id']))
        covers.extend(str(x) for x in (s.get('covers') or []))
        # apply_reviewed_relations may write covers_room.
        if s.get('covers_room'): covers.append(str(s['covers_room']))
        for rid in sorted(set(covers)):
            add(_edge(sid,'covers',rid,confidence=1.0,source='reviewed_sensor_binding',kind='reviewed'))

    # Interior openings make room connectivity explicit.
    for op in topo.get('openings') or []:
        oid=str(op.get('id') or '')
        rooms=[str(x) for x in (op.get('connects') or []) if x!='exterior']
        if len(rooms)==2:
            a,b=rooms
            add(_edge(a,'connected_to',b,confidence=1.0,source=f'topology.openings:{oid}',kind='explicit',evidence={'opening_id':oid}))
            add(_edge(b,'connected_to',a,confidence=1.0,source=f'topology.openings:{oid}',kind='explicit',evidence={'opening_id':oid}))
            add(_edge(oid,'connects_room',a,confidence=1.0,source='topology.openings.connects',kind='explicit'))
            add(_edge(oid,'connects_room',b,confidence=1.0,source='topology.openings.connects',kind='explicit'))

    # Scene entity -> operational device aliases from topology bindings.
    for b in topo.get('device_bindings') or []:
        sid=str(b.get('scene_entity_id') or ''); did=str(b.get('device_id') or '')
        if sid and did:
            add(_edge(sid,'operated_as',did,confidence=1.0,source='topology.device_bindings',kind='explicit'))
            add(_edge(did,'represents',sid,confidence=1.0,source='inverse:operated_as',kind='explicit'))

    edges=sorted(edges,key=lambda e:(e['src'],e['rel'],e['dst']))
    nodes=sorted(set(cat)|{e['src'] for e in edges}|{e['dst'] for e in edges})
    out={'schema':SCHEMA,'nodes':nodes,'edges':edges,
         'summary':{'nodes':len(nodes),'edges':len(edges)}}
    out['fingerprint']=_fp({'schema':SCHEMA,'nodes':nodes,'edges':edges})
    return out


def _adj(graph:Mapping[str,Any], allowed_rels:set[str]|None=None):
    d=defaultdict(list)
    for e in graph.get('edges') or []:
        if allowed_rels is None or e['rel'] in allowed_rels: d[e['src']].append(e)
    for k in d: d[k].sort(key=lambda x:(x['rel'],x['dst']))
    return d


def find_relation_paths(graph:Mapping[str,Any], *, src:str, dst:str|None=None,
                        target_rel:str|None=None, allowed_rels:Sequence[str]|None=None,
                        max_hops:int=4, min_confidence:float=0.0)->dict[str,Any]:
    if graph.get('schema')!=SCHEMA: raise SpatialRelationGraphError('unsupported relation graph schema')
    allowed=set(allowed_rels) if allowed_rels is not None else None
    adj=_adj(graph,allowed)
    q=deque([(src,[],1.0,{src})]); paths=[]
    while q:
        node,path,conf,visited=q.popleft()
        if len(path)>=int(max_hops): continue
        for e in adj.get(node,[]):
            nc=min(conf,float(e['confidence']))
            if nc<float(min_confidence): continue
            np=path+[e]
            match_dst=(dst is not None and e['dst']==dst)
            match_rel=(target_rel is not None and e['rel']==target_rel)
            if (dst is not None and target_rel is not None and match_dst and match_rel) or (dst is not None and target_rel is None and match_dst) or (dst is None and target_rel is not None and match_rel):
                paths.append({'src':src,'dst':e['dst'],'relation':e['rel'],'hops':len(np),'confidence':nc,'edges':np})
            if e['dst'] not in visited:
                q.append((e['dst'],np,nc,visited|{e['dst']}))
    paths.sort(key=lambda p:(p['hops'],-p['confidence'],p['dst'],_canon(p['edges'])))
    out={'schema':QUERY_SCHEMA,'graph_fingerprint':graph['fingerprint'],'src':src,'dst':dst,'target_rel':target_rel,
         'paths':paths,'summary':{'matches':len(paths)}}
    out['fingerprint']=_fp({k:out[k] for k in ['schema','graph_fingerprint','src','dst','target_rel','paths']})
    return out


def derive_semantic_relations(graph:Mapping[str,Any], *, max_connected_room_hops:int=1)->dict[str,Any]:
    """Derive only explainable relations with complete paths.

    - sensor affects window: sensor covers room -> room contains exterior window
    - hood has direct make-up candidate: hood exhausts room <- window supplies room
    - one-hop make-up candidate: hood room connected_to adjacent room <- exterior window supplies adjacent room
      This remains `candidate`, never a hard safety rule by itself.
    """
    edges=graph.get('edges') or []
    by_src=defaultdict(list); incoming=defaultdict(list)
    for e in edges: by_src[e['src']].append(e); incoming[e['dst']].append(e)
    derived=[]; seen=set()
    def add(rel):
        k=(rel['src'],rel['rel'],rel['dst'],tuple((e['src'],e['rel'],e['dst']) for e in rel['path']))
        if k in seen:return
        seen.add(k); derived.append(rel)

    # sensor -> room -> windows in room
    for e in edges:
        if e['rel']!='covers': continue
        sensor,room=e['src'],e['dst']
        for c in by_src.get(room,[]):
            if c['rel']!='contains': continue
            wid=c['dst']
            # require explicit evidence that window supplies that room (i.e. exterior)
            supply=next((x for x in by_src.get(wid,[]) if x['rel']=='supplies_air_to' and x['dst']==room),None)
            if not supply: continue
            path=[e,c,supply]
            add({'src':sensor,'rel':'affects_exterior_window','dst':wid,'status':'derived','confidence':min(x['confidence'] for x in path),'path':path})

    # hood -> room and windows supplying same / adjacent room.
    for h in edges:
        if h['rel']!='exhausts': continue
        hood,room=h['src'],h['dst']
        # Direct candidates.
        for s in incoming.get(room,[]):
            if s['rel']!='supplies_air_to': continue
            path=[h,s]
            add({'src':hood,'rel':'makeup_air_candidate','dst':s['src'],'status':'candidate','scope':'same_room','confidence':min(x['confidence'] for x in path),'path':path})
        if max_connected_room_hops>=1:
            for conn in by_src.get(room,[]):
                if conn['rel']!='connected_to': continue
                adj=conn['dst']
                for s in incoming.get(adj,[]):
                    if s['rel']!='supplies_air_to': continue
                    path=[h,conn,s]
                    # penalty for cross-room inference: useful candidate, not hard relation.
                    conf=min(min(x['confidence'] for x in path),0.80)
                    add({'src':hood,'rel':'makeup_air_candidate','dst':s['src'],'status':'candidate','scope':'adjacent_room','confidence':conf,'path':path})
    derived=sorted(derived,key=lambda x:(x['rel'],x['src'],x['dst'],x.get('scope','')))
    out={'schema':'derived_spatial_semantics_v4.2','graph_fingerprint':graph['fingerprint'],'relations':derived,
         'summary':{'relations':len(derived),'derived':sum(x['status']=='derived' for x in derived),'candidates':sum(x['status']=='candidate' for x in derived)}}
    out['fingerprint']=_fp({k:out[k] for k in ['schema','graph_fingerprint','relations']})
    return out
