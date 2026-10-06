from spatialruntime.safety.dependency_graph import compile_safety_graph, SCHEMA as GRAPH_SCHEMA
from spatialruntime.safety.pipeline import run_safety_pipeline

CAT={'wk':{'kind':'window','exterior':True,'facade':'east','room':'kitchen'},'wb':{'kind':'window','exterior':True,'facade':'west','room':'bed'},'hood':{'kind':'hood','room':'kitchen'}}
RUNTIME={'wk':{'executed_state':{'open_ratio':.5}},'wb':{'executed_state':{'open_ratio':.4}},'hood':{'executed_state':{'fan_level':0}}}
GRAPH={'schema':GRAPH_SCHEMA,'rules':[
 {'id':'rain','priority':90,'when':{'path':'sensors.rain.value','op':'eq','value':'wet'},'effects':[{'kind':'constrain','selector':{'where':{'kind':'window','exterior':True}},'property':'open_ratio','op':'max','value':0}]},
 {'id':'cook_fact','when':{'path':'sensors.cooking.value','op':'eq','value':True},'effects':[{'kind':'set_fact','key':'makeup','value':True}]},
 {'id':'cook','when':{'path':'facts.makeup','op':'truthy'},'effects':[{'kind':'emit_change','selector':{'ids':['hood']},'changes':{'fan_level':1}},{'kind':'emit_change','selector':{'ids':['wk']},'changes':{'open_ratio':.2}}]},
 {'id':'fire','priority':100,'when':{'path':'modes.fire','op':'truthy'},'effects':[{'kind':'set_context','path':'emergency_close','value':True}]},
]}

def context(rain='dry',cooking=False,fire=False): return {'source_step':5,'source_revision':9,'sensors':{'rain':{'value':rain},'cooking':{'value':cooking}},'modes':{'fire':fire}}
def policy(ch): return {'source_step':5,'source_revision':9,'changes':ch}
def recovery(kind,target=None): return {'schema':'fault_recovery_action_v2.8','source_step':5,'source_revision':9,'entity_id':'wk','device_id':'d1','kind':kind,'target_state':target or {},'reason':'test','requires_commit_gate':True}

def run(ctx,pol=None,recs=None): return run_safety_pipeline(source_step=5,source_revision=9,policy_action=pol or policy({}),recovery_actions=recs or [],runtime_state=RUNTIME,safety_context=ctx,entity_catalog=CAT,compiled_graph=compile_safety_graph(GRAPH,CAT))

def test_rain_clamps_policy_before_supervisor():
 r=run(context(rain='wet'),policy({'wk':{'open_ratio':.9}})); assert r['motion_changes']['wk']['open_ratio']==0

def test_rain_also_clamps_recovery_motion_no_bypass():
 r=run(context(rain='wet'),policy({'wk':{'open_ratio':.9}}),[recovery('set_state',{'open_ratio':.3})]); assert r['motion_changes']['wk']['open_ratio']==0

def test_recovery_stop_preserved_and_motion_removed():
 r=run(context(),policy({'wk':{'open_ratio':.9}}),[recovery('stop')]); assert 'wk' not in r['motion_changes'] and r['control_actions'][0]['kind']=='stop'

def test_fire_context_closes_all_windows_even_unmentioned():
 r=run(context(fire=True),policy({'hood':{'fan_level':1}})); assert r['motion_changes']['wk']['open_ratio']==0 and r['motion_changes']['wb']['open_ratio']==0

def test_cooking_generated_actions_still_pass_supervisor():
 r=run(context(cooking=True)); assert r['motion_changes']['hood']['fan_level']==1 and r['motion_changes']['wk']['open_ratio']==.2
