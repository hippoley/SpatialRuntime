import pytest
from spatialruntime.safety.arbitrator import arbitrate_actions, ActionArbitrationError

def policy(ch): return {"source_step":2,"source_revision":4,"changes":ch}
def rec(kind,eid='w1',state=None): return {"schema":"fault_recovery_action_v2.8","source_step":2,"source_revision":4,"entity_id":eid,"device_id":"d1","kind":kind,"target_state":state or {},"reason":"test","requires_commit_gate":True}

def test_policy_passes_through():
 r=arbitrate_actions(source_step=2,source_revision=4,policy_action=policy({'w1':{'open_ratio':.7}}))
 assert r['changes']['w1']['open_ratio']==.7 and r['origins']['w1']=='policy'

def test_recovery_motion_overrides_policy_for_same_entity():
 r=arbitrate_actions(source_step=2,source_revision=4,policy_action=policy({'w1':{'open_ratio':.9}}),recovery_actions=[rec('set_state',state={'open_ratio':.3})])
 assert r['changes']['w1']['open_ratio']==.3 and r['origins']['w1']=='recovery_motion'

def test_stop_preempts_policy_and_motion_in_same_batch():
 r=arbitrate_actions(source_step=2,source_revision=4,policy_action=policy({'w1':{'open_ratio':.9}}),recovery_actions=[rec('stop'),rec('set_state',state={'open_ratio':.3})])
 assert 'w1' not in r['changes']
 assert r['control_actions'][0]['kind']=='stop'

def test_other_entity_policy_untouched():
 r=arbitrate_actions(source_step=2,source_revision=4,policy_action=policy({'w1':{'open_ratio':.9},'w2':{'open_ratio':.2}}),recovery_actions=[rec('stop','w1')])
 assert r['changes']['w2']['open_ratio']==.2

def test_stale_recovery_rejected():
 a=rec('stop'); a['source_revision']=3
 with pytest.raises(ActionArbitrationError): arbitrate_actions(source_step=2,source_revision=4,policy_action=policy({}),recovery_actions=[a])
