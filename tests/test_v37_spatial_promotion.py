import json, pytest
from pathlib import Path
from spatialruntime.spatial.autocompile import compile_safety_graph_skeleton
from spatialruntime.spatial.promotion import *
ROOT=Path(__file__).resolve().parents[1]
SCENE=json.loads((ROOT/'tests/fixtures/world_snapshot.json').read_text()); TOPO=json.loads((ROOT/'tests/fixtures/topology.json').read_text())

def test_promotion_allows_unresolved_unreferenced_facade_as_warning():
 r=compile_safety_graph_skeleton(SCENE,topology=TOPO); p=promote_autocompiled_graph(r)
 assert p['compiled_graph'].fingerprint==p['graph_fingerprint'] and p['warnings']

def test_strict_promotion_can_block_any_unresolved_relation():
 r=compile_safety_graph_skeleton(SCENE,topology=TOPO)
 with pytest.raises(UnsafeAutoPromotion): promote_autocompiled_graph(r,require_no_unresolved=True)

def test_weak_referenced_room_evidence_blocks_promotion():
 scene=json.loads(json.dumps(SCENE)); hood=next(x for x in scene['entities'] if x['id']=='hood_visual_01'); hood['semantics']['provenance']['confidence']=.5
 # Reviewed makeup uses hood + window, but low-confidence hood room should prevent the relation from being generated at all.
 r=compile_safety_graph_skeleton(scene,topology=TOPO,templates={'cooking_paths':{'room_kitchen':'sensors.cooking.value'},'makeup_air_min_open_ratio':{'room_kitchen':.2},'makeup_air_min_fan_level':{'room_kitchen':1}})
 ids={x['id'] for x in r['graph']['rules']}; assert 'auto.makeup.apply.room_kitchen' not in ids
