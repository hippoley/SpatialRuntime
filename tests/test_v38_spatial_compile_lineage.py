import json, pytest
from pathlib import Path
from spatialruntime.spatial.compile_lineage import *
ROOT=Path(__file__).resolve().parents[1]
SCENE=json.loads((ROOT/'tests/fixtures/world_snapshot.json').read_text()); TOPO=json.loads((ROOT/'tests/fixtures/topology.json').read_text())

def test_bundle_roundtrip_verifies():
 b=build_spatial_compile_bundle(SCENE,topology=TOPO); assert verify_spatial_compile_bundle(b,SCENE,topology=TOPO)['verified']

def test_topology_change_invalidates_bundle():
 b=build_spatial_compile_bundle(SCENE,topology=TOPO); t=json.loads(json.dumps(TOPO)); t['openings'][0]['connects']=['room_living','exterior']
 with pytest.raises(SpatialSourceDrift): verify_spatial_compile_bundle(b,SCENE,topology=t)

def test_reviewed_template_change_invalidates_bundle():
 tmpl={'cooking_paths':{'room_kitchen':'sensors.cooking.value'},'makeup_air_min_open_ratio':{'room_kitchen':.2},'makeup_air_min_fan_level':{'room_kitchen':1}}
 b=build_spatial_compile_bundle(SCENE,topology=TOPO,templates=tmpl,min_evidence_confidence=.9); t=json.loads(json.dumps(tmpl)); t['makeup_air_min_open_ratio']['room_kitchen']=.3
 with pytest.raises(SpatialSourceDrift): verify_spatial_compile_bundle(b,SCENE,topology=TOPO,templates=t)
