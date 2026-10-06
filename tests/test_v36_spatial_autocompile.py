import json
from pathlib import Path
from spatialruntime.spatial.autocompile import *
ROOT=Path(__file__).resolve().parents[1]
SCENE=json.loads((ROOT/'tests/fixtures/world_snapshot.json').read_text())
TOPO=json.loads((ROOT/'tests/fixtures/topology.json').read_text())

def test_catalog_promotes_only_evidence_backed_relations():
 r=build_spatial_entity_catalog(SCENE,topology=TOPO); c=r['entities']
 assert c['window_kitchen_01']['room']=='room_kitchen' and c['window_kitchen_01']['exterior'] is True
 assert c['hood_visual_01']['room']=='room_kitchen' and c['hood_visual_01']['kind']=='hood'
 assert 'facade' not in c['window_kitchen_01']
 assert any(x['entity_id']=='window_kitchen_01' and x['field']=='facade' for x in r['unresolved'])

def test_rain_rule_auto_generated_but_facade_wind_not_guessed():
 r=compile_safety_graph_skeleton(SCENE,topology=TOPO); ids={x['id'] for x in r['graph']['rules']}
 assert 'auto.rain.exterior_windows' in ids
 assert not any(x.startswith('auto.wind.') for x in ids)

def test_makeup_air_requires_reviewed_operating_values():
 r=compile_safety_graph_skeleton(SCENE,topology=TOPO)
 assert any(x['template']=='makeup_air' and 'operating thresholds' in x['reason'] for x in r['skipped'])

def test_explicit_facade_can_generate_scoped_wind_rule():
 topo=json.loads(json.dumps(TOPO)); topo['boundaries'][0]['facade']='north'
 r=compile_safety_graph_skeleton(SCENE,topology=topo,templates={'wind_paths':{'north':'weather.wind_north_m_s'},'wind_thresholds_m_s':{'north':12}})
 rule=next(x for x in r['graph']['rules'] if x['id']=='auto.wind.north')
 assert rule['effects'][0]['selector']['ids']==['window_kitchen_01']

def test_reviewed_makeup_template_generates_multihop_rules():
 r=compile_safety_graph_skeleton(SCENE,topology=TOPO,templates={'cooking_paths':{'room_kitchen':'sensors.cooking.value'},'makeup_air_min_open_ratio':{'room_kitchen':.2},'makeup_air_min_fan_level':{'room_kitchen':1}})
 ids={x['id'] for x in r['graph']['rules']}; assert 'auto.makeup.fact.room_kitchen' in ids and 'auto.makeup.apply.room_kitchen' in ids
