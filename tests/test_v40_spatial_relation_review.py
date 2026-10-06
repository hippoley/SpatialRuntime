from spatialruntime.spatial.resolver import resolve_spatial_relations
from spatialruntime.spatial.review import *

def base():
 t={'rooms':[{'id':'r','floor_polygon_xz':[[0,0],[10,0],[10,8],[0,8]]}], 'boundaries':[{'id':'w','room_id':'r','segment_xz':[[0,8],[10,8]]}], 'openings':[{'id':'win','kind':'window','boundary_id':'w','connects':['r','exterior'],'position_xz':[5,8]}]}
 s=[{'sensor_id':'rain','position_xz':[2,2]}]; return t,s

def test_review_accept_and_apply():
 t,s=base(); c=resolve_spatial_relations({},topology=t,sensor_bindings=s)
 b=build_review_bundle(c,[{'entity_id':'win','relation':'facade','action':'accept','actor':'reviewer','reason':'geometry checked'},{'entity_id':'rain','relation':'covers_room','action':'accept','actor':'reviewer','reason':'plan checked'}])
 t2,s2=apply_reviewed_relations(t,s,b)
 assert t2['openings'][0]['facade']=='north' and s2[0]['room_id']=='r'

def test_ambiguous_requires_override():
 t,s=base(); t['boundaries'][0]['segment_xz']=[[0,0],[10,10]]; t['openings'][0]['position_xz']=[5,5]
 c=resolve_spatial_relations({},topology=t,sensor_bindings=s)
 try: build_review_bundle(c,[{'entity_id':'win','relation':'facade','action':'accept','actor':'r','reason':'x'}]); assert False
 except SpatialReviewError: pass
 b=build_review_bundle(c,[{'entity_id':'win','relation':'facade','action':'override','value':'north','actor':'r','reason':'verified drawing'}])
 assert b['accepted'][0]['value']=='north'

def test_review_requires_actor_reason_and_no_duplicates():
 t,s=base(); c=resolve_spatial_relations({},topology=t,sensor_bindings=s)
 try: build_review_bundle(c,[{'entity_id':'win','relation':'facade','action':'accept','actor':'','reason':'x'}]); assert False
 except SpatialReviewError: pass
