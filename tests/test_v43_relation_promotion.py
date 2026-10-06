from spatialruntime.spatial.relation_graph import *
from spatialruntime.spatial.relation_promotion import *
from spatialruntime.spatial.autocompile import build_spatial_entity_catalog

def derived():
    scene={'entities':[{'id':'hood','semantics':{'type':'appliance.range_hood','room_id':'k','provenance':{'confidence':1.0}}}]}
    topo={'rooms':[{'id':'k'}],'openings':[{'id':'w','kind':'window','connects':['k','exterior']} ]}
    sensors=[{'sensor_id':'rain','room_id':'k','covers_room':'k'}]
    c=build_spatial_entity_catalog(scene,topology=topo,sensor_bindings=sensors)
    return derive_semantic_relations(build_spatial_relation_graph(catalog_doc=c,topology=topo,sensor_bindings=sensors))

def test_high_confidence_derived_can_auto_promote_but_candidate_cannot():
    d=derived(); p=promote_relations(d,min_auto_confidence=.95)
    keys={(x['src'],x['rel'],x['dst']) for x in p['promoted']}
    assert ('rain','affects_exterior_window','w') in keys
    assert not any(x['rel']=='makeup_air_candidate' for x in p['promoted'])

def test_candidate_requires_explicit_review():
    d=derived(); dec=[{'src':'hood','rel':'makeup_air_candidate','dst':'w','action':'accept','actor':'hvac','reason':'verified airflow design'}]
    p=promote_relations(d,decisions=dec)
    assert any(x['rel']=='makeup_air_candidate' and x['promotion']['mode']=='reviewed' for x in p['promoted'])

def test_accept_requires_audit_fields():
    d=derived(); dec=[{'src':'hood','rel':'makeup_air_candidate','dst':'w','action':'accept'}]
    try: promote_relations(d,decisions=dec); assert False
    except SpatialRelationPromotionError: pass
