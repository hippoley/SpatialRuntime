from spatialruntime.spatial.relation_graph import *
from spatialruntime.spatial.autocompile import build_spatial_entity_catalog

def case():
    scene={'entities':[{'id':'hood_scene','semantics':{'type':'appliance.range_hood','room_id':'k','provenance':{'confidence':1.0}}}]}
    topo={'rooms':[{'id':'k'},{'id':'l'}],
          'openings':[{'id':'wk','kind':'window','connects':['k','exterior'],'facade':'north'},
                      {'id':'wl','kind':'window','connects':['l','exterior'],'facade':'south'},
                      {'id':'door','kind':'door','connects':['k','l']}],
          'device_bindings':[{'scene_entity_id':'hood_scene','device_id':'hood_dev'}]}
    sensors=[{'sensor_id':'rain_k','room_id':'k','covers_room':'k'}]
    cat=build_spatial_entity_catalog(scene,topology=topo,sensor_bindings=sensors)
    return scene,topo,sensors,cat

def test_relation_graph_and_transitive_sensor_effect():
    _,t,s,c=case(); g=build_spatial_relation_graph(catalog_doc=c,topology=t,sensor_bindings=s)
    d=derive_semantic_relations(g)
    rel={(x['src'],x['rel'],x['dst']):x for x in d['relations']}
    assert ('rain_k','affects_exterior_window','wk') in rel
    assert rel[('rain_k','affects_exterior_window','wk')]['status']=='derived'
    assert ('rain_k','affects_exterior_window','wl') not in rel

def test_makeup_candidates_keep_direct_vs_adjacent_scope():
    _,t,s,c=case(); g=build_spatial_relation_graph(catalog_doc=c,topology=t,sensor_bindings=s)
    d=derive_semantic_relations(g)
    xs={(x['src'],x['dst'],x.get('scope')):x for x in d['relations'] if x['rel']=='makeup_air_candidate'}
    assert ('hood_dev','wk','same_room') in xs
    assert ('hood_dev','wl','adjacent_room') in xs
    assert xs[('hood_dev','wl','adjacent_room')]['confidence']<=.80

def test_query_path_is_explainable():
    _,t,s,c=case(); g=build_spatial_relation_graph(catalog_doc=c,topology=t,sensor_bindings=s)
    q=find_relation_paths(g,src='k',dst='l',allowed_rels=['connected_to'])
    assert q['summary']['matches']==1
    assert q['paths'][0]['edges'][0]['evidence']['opening_id']=='door'
