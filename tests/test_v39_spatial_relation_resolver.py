from spatialruntime.spatial.resolver import *

def _topo():
 return {'rooms':[{'id':'room_k','floor_polygon_xz':[[0,0],[10,0],[10,8],[0,8]]}],
 'boundaries':[{'id':'northwall','kind':'exterior_wall','room_id':'room_k','segment_xz':[[0,8],[10,8]]}],
 'openings':[{'id':'win1','kind':'window','boundary_id':'northwall','connects':['room_k','exterior'],'position_xz':[5,8.02]}]}

def test_facade_candidate_from_wall_geometry_is_explainable():
 d=resolve_spatial_relations({},topology=_topo())
 r=next(x for x in d['relations'] if x['entity_id']=='win1')
 assert r['value']=='north' and r['status']=='candidate' and r['confidence']>=.9
 assert r['evidence'][0]['outward_normal_xz']==[0.0,1.0]

def test_facade_far_from_wall_fails_closed():
 t=_topo(); t['openings'][0]['position_xz']=[5,6]
 r=resolve_facade_candidates(t)[0]
 assert r['status']=='unresolved' and 'too far' in r['reason']

def test_diagonal_wall_is_ambiguous_not_hard_promoted():
 t=_topo(); t['boundaries'][0]['segment_xz']=[[0,0],[10,10]]; t['openings'][0]['position_xz']=[5,5]
 r=resolve_facade_candidates(t,min_axis_dominance=.9)[0]
 assert r['status']=='ambiguous'

def test_sensor_position_resolves_polygon_room():
 t=_topo(); d=resolve_spatial_relations({},topology=t,sensor_bindings=[{'sensor_id':'rain1','position_xz':[2,2]}])
 r=next(x for x in d['relations'] if x['entity_id']=='rain1')
 assert r['relation']=='covers_room' and r['value']=='room_k' and r['confidence']>=.95

def test_sensor_outside_remains_unresolved():
 r=resolve_sensor_coverage_candidates(_topo(),[{'sensor_id':'s','position_xz':[20,20]}])[0]
 assert r['status']=='unresolved'
