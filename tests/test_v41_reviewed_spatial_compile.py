from spatialruntime.spatial.reviewed_compile import *

def setup_case():
 scene={'entities':[]}
 topo={'rooms':[{'id':'r','floor_polygon_xz':[[0,0],[10,0],[10,8],[0,8]]}],
       'boundaries':[{'id':'w','room_id':'r','segment_xz':[[0,8],[10,8]]}],
       'openings':[{'id':'win','kind':'window','boundary_id':'w','connects':['r','exterior'],'position_xz':[5,8]}]}
 sensors=[{'sensor_id':'wind_n','position_xz':[2,2]}]
 templates={'wind_paths':{'north':'weather.wind_north_m_s'},'wind_thresholds_m_s':{'north':12}}
 decisions=[{'entity_id':'win','relation':'facade','action':'accept','actor':'qa','reason':'wall geometry checked'},
            {'entity_id':'wind_n','relation':'covers_room','action':'accept','actor':'qa','reason':'sensor location checked'}]
 return scene,topo,sensors,templates,decisions

def test_reviewed_facade_enters_auto_safety_graph():
 scene,t,s,tm,d=setup_case(); b=build_reviewed_spatial_compile_bundle(scene,topology=t,sensor_bindings=s,templates=tm,review_decisions=d)
 ids={r['id'] for r in b['spatial_compile_bundle']['graph']['rules']}
 assert 'auto.wind.north' in ids
 assert verify_reviewed_spatial_compile_bundle(b,scene,topology=t,sensor_bindings=s,templates=tm)['verified']

def test_geometry_drift_invalidates_reviewed_bundle():
 scene,t,s,tm,d=setup_case(); b=build_reviewed_spatial_compile_bundle(scene,topology=t,sensor_bindings=s,templates=tm,review_decisions=d)
 t2=copy.deepcopy(t); t2['boundaries'][0]['segment_xz']=[[0,0],[10,10]]
 try: verify_reviewed_spatial_compile_bundle(b,scene,topology=t2,sensor_bindings=s,templates=tm); assert False
 except ReviewedSpatialDrift: pass

def test_review_decision_tamper_is_detected():
 scene,t,s,tm,d=setup_case(); b=build_reviewed_spatial_compile_bundle(scene,topology=t,sensor_bindings=s,templates=tm,review_decisions=d)
 bad=copy.deepcopy(b); bad['review_decisions'][0]['reason']='tampered'
 try: verify_reviewed_spatial_compile_bundle(bad,scene,topology=t,sensor_bindings=s,templates=tm); assert False
 except ReviewedSpatialDrift: pass
