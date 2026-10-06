from __future__ import annotations
from typing import Any, Mapping, Sequence
import hashlib, json, math

SCHEMA='spatial_relation_candidates_v3.9'
class SpatialRelationError(RuntimeError): pass

def _canon(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def _fp(x): return hashlib.sha256(_canon(x).encode()).hexdigest()
def _dist(a,b): return math.hypot(float(a[0])-float(b[0]),float(a[1])-float(b[1]))
def _centroid(poly):
    return [sum(float(p[0]) for p in poly)/len(poly),sum(float(p[1]) for p in poly)/len(poly)]
def _room_center(room):
    poly=room.get('floor_polygon_xz')
    if poly and len(poly)>=3:return _centroid(poly)
    b=room.get('bounds_floor') or {}; lo=b.get('min'); hi=b.get('max')
    if lo and hi:return [(float(lo[0])+float(hi[0]))/2,(float(lo[2])+float(hi[2]))/2]
    return None

def point_in_polygon(p, poly):
    x,z=float(p[0]),float(p[1]); inside=False
    n=len(poly)
    for i in range(n):
        x1,z1=map(float,poly[i]); x2,z2=map(float,poly[(i+1)%n])
        if ((z1>z)!=(z2>z)):
            xin=(x2-x1)*(z-z1)/(z2-z1)+x1
            if x<xin: inside=not inside
    return inside

def _contains(room,p):
    poly=room.get('floor_polygon_xz')
    if poly and len(poly)>=3:return point_in_polygon(p,poly),'floor_polygon_xz',.98
    b=room.get('bounds_floor') or {}; lo=b.get('min'); hi=b.get('max')
    if lo and hi:
        ok=float(lo[0])<=float(p[0])<=float(hi[0]) and float(lo[2])<=float(p[1])<=float(hi[2])
        return ok,'bounds_floor_xz',.90
    return False,'none',0.0

def _distance_point_segment(p,a,b):
    px,pz=map(float,p); ax,az=map(float,a); bx,bz=map(float,b)
    vx,vz=bx-ax,bz-az; den=vx*vx+vz*vz
    if den<=1e-12:return _dist(p,a),0.0
    t=max(0.0,min(1.0,((px-ax)*vx+(pz-az)*vz)/den))
    q=[ax+t*vx,az+t*vz]
    return _dist(p,q),t

def _facade_from_segment(seg,room_center):
    a,b=seg; ax,az=map(float,a); bx,bz=map(float,b)
    dx,dz=bx-ax,bz-az; L=math.hypot(dx,dz)
    if L<=1e-9: raise SpatialRelationError('zero-length boundary segment')
    # Two normals. Choose the one pointing away from the adjacent room center.
    n1=[-dz/L,dx/L]; n2=[dz/L,-dx/L]
    mid=[(ax+bx)/2,(az+bz)/2]
    to_room=[float(room_center[0])-mid[0],float(room_center[1])-mid[1]]
    dot1=n1[0]*to_room[0]+n1[1]*to_room[1]
    outward=n1 if dot1<0 else n2
    x,z=outward
    dominance=max(abs(x),abs(z))
    if abs(x)>=abs(z): facade='east' if x>0 else 'west'
    else: facade='north' if z>0 else 'south'
    return facade,outward,dominance,L,mid

def resolve_facade_candidates(topology:Mapping[str,Any], *, max_opening_wall_distance_m:float=.35,
                              min_axis_dominance:float=.85)->list[dict[str,Any]]:
    rooms={str(r.get('id')):r for r in topology.get('rooms') or [] if r.get('id')}
    bounds={str(b.get('id')):b for b in topology.get('boundaries') or [] if b.get('id')}
    out=[]
    for op in topology.get('openings') or []:
        eid=str(op.get('id') or '')
        con=list(op.get('connects') or [])
        if not eid or 'exterior' not in con: continue
        if op.get('facade'):
            out.append({'entity_id':eid,'relation':'facade','value':op['facade'],'status':'explicit','confidence':1.0,'evidence':[{'kind':'explicit','source':'topology.openings.facade'}]}); continue
        b=bounds.get(str(op.get('boundary_id') or '')) or {}
        if b.get('facade'):
            out.append({'entity_id':eid,'relation':'facade','value':b['facade'],'status':'explicit','confidence':1.0,'evidence':[{'kind':'explicit','source':'topology.boundaries.facade'}]}); continue
        seg=b.get('segment_xz') or b.get('wall_segment_xz')
        room_ids=[x for x in con if x!='exterior']
        room=rooms.get(str(room_ids[0])) if len(room_ids)==1 else None
        center=_room_center(room or {}) if room else None
        if not seg or len(seg)!=2 or center is None:
            out.append({'entity_id':eid,'relation':'facade','status':'unresolved','confidence':0.0,'reason':'missing exterior wall segment or unique adjacent room geometry'}); continue
        try: facade,n,dom,L,mid=_facade_from_segment(seg,center)
        except SpatialRelationError as e:
            out.append({'entity_id':eid,'relation':'facade','status':'unresolved','confidence':0.0,'reason':str(e)}); continue
        pos=op.get('position_xz')
        wall_distance=None; endpoint_margin=None
        if pos is not None:
            wall_distance,t=_distance_point_segment(pos,seg[0],seg[1]); endpoint_margin=min(t,1-t)
            if wall_distance>max_opening_wall_distance_m:
                out.append({'entity_id':eid,'relation':'facade','status':'unresolved','confidence':0.0,'reason':'opening position too far from referenced wall segment','evidence':[{'wall_distance_m':wall_distance,'max_m':max_opening_wall_distance_m}]}); continue
        # Confidence deliberately penalizes diagonal facade and openings too close to segment endpoints.
        conf=.92
        conf*=min(1.0,dom/max(min_axis_dominance,1e-9)) if dom<min_axis_dominance else 1.0
        if endpoint_margin is not None and endpoint_margin<.08: conf*=.75
        if wall_distance is not None: conf*=max(.75,1.0-wall_distance/max(max_opening_wall_distance_m,1e-9)*.15)
        status='candidate' if dom>=min_axis_dominance else 'ambiguous'
        out.append({'entity_id':eid,'relation':'facade','value':facade,'status':status,'confidence':round(conf,6),
                    'evidence':[{'kind':'geometry','source':'boundary.segment_xz','segment_xz':seg,'room_center_xz':center,
                                 'outward_normal_xz':[round(n[0],6),round(n[1],6)],'axis_dominance':round(dom,6),
                                 'wall_length_m':round(L,6),'wall_midpoint_xz':mid,'opening_wall_distance_m':wall_distance,
                                 'endpoint_margin':endpoint_margin}]})
    return out

def resolve_sensor_coverage_candidates(topology:Mapping[str,Any], sensor_bindings:Sequence[Mapping[str,Any]]|None)->list[dict[str,Any]]:
    rooms=[r for r in topology.get('rooms') or [] if r.get('id')]
    out=[]
    for s in sensor_bindings or []:
        sid=str(s.get('sensor_id') or '')
        if not sid: continue
        if s.get('room_id'):
            out.append({'entity_id':sid,'relation':'covers_room','value':s['room_id'],'status':'explicit','confidence':1.0,'evidence':[{'kind':'explicit','source':'sensor_bindings.room_id'}]}); continue
        pos=s.get('position_xz')
        if pos is None:
            out.append({'entity_id':sid,'relation':'covers_room','status':'unresolved','confidence':0.0,'reason':'no explicit room_id or position_xz'}); continue
        hits=[]
        for r in rooms:
            ok,method,conf=_contains(r,pos)
            if ok:hits.append((str(r['id']),method,conf))
        if len(hits)==1:
            rid,method,conf=hits[0]
            out.append({'entity_id':sid,'relation':'covers_room','value':rid,'status':'candidate','confidence':conf,
                        'evidence':[{'kind':'geometry','source':method,'position_xz':list(pos),'room_id':rid}]})
        elif len(hits)>1:
            out.append({'entity_id':sid,'relation':'covers_room','status':'ambiguous','confidence':0.0,'reason':'sensor position lies in multiple room geometries','candidates':[x[0] for x in hits]})
        else:
            out.append({'entity_id':sid,'relation':'covers_room','status':'unresolved','confidence':0.0,'reason':'sensor position is outside all room geometries'})
    return out

def resolve_spatial_relations(scene:Mapping[str,Any], *, topology:Mapping[str,Any]|None=None,
                              sensor_bindings:Sequence[Mapping[str,Any]]|None=None)->dict[str,Any]:
    topo=topology or scene.get('topology') or {}
    rels=resolve_facade_candidates(topo)+resolve_sensor_coverage_candidates(topo,sensor_bindings)
    rels=sorted(rels,key=lambda x:(x['relation'],x['entity_id'],str(x.get('value',''))))
    doc={'schema':SCHEMA,'relations':rels,'summary':{
        'total':len(rels),'explicit':sum(r.get('status')=='explicit' for r in rels),'candidate':sum(r.get('status')=='candidate' for r in rels),
        'ambiguous':sum(r.get('status')=='ambiguous' for r in rels),'unresolved':sum(r.get('status')=='unresolved' for r in rels)}}
    doc['fingerprint']=_fp({'schema':SCHEMA,'relations':rels})
    return doc
