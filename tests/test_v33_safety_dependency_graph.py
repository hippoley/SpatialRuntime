import pytest
from spatialruntime.safety.dependency_graph import *

CAT={
 'window_kitchen':{'kind':'window','exterior':True,'room':'kitchen','facade':'east'},
 'window_bed':{'kind':'window','exterior':True,'room':'bedroom','facade':'west'},
 'hood_kitchen':{'kind':'hood','room':'kitchen'},
}

def graph():
 return {'schema':SCHEMA,'rules':[
  {'id':'rain_closes_exterior','priority':90,'when':{'path':'sensors.rain.value','op':'eq','value':'wet'},'effects':[{'kind':'constrain','selector':{'where':{'kind':'window','exterior':True}},'property':'open_ratio','op':'max','value':0.0}]},
  {'id':'east_wind','priority':80,'when':{'path':'sensors.wind_east_m_s.value','op':'gt','value':12},'effects':[{'kind':'constrain','selector':{'where':{'kind':'window','facade':'east'}},'property':'open_ratio','op':'max','value':0.0}]},
  {'id':'cooking_fact','priority':50,'when':{'path':'sensors.cooking.value','op':'eq','value':True},'effects':[{'kind':'set_fact','key':'need_makeup_air','value':True}]},
  {'id':'cooking_actions','priority':45,'when':{'path':'facts.need_makeup_air','op':'truthy'},'effects':[{'kind':'emit_change','selector':{'ids':['hood_kitchen']},'changes':{'fan_level':1}},{'kind':'emit_change','selector':{'ids':['window_kitchen']},'changes':{'open_ratio':0.2}}]},
  {'id':'fire_mode','priority':100,'when':{'path':'modes.fire','op':'eq','value':True},'effects':[{'kind':'set_context','path':'emergency_close','value':True}]},
 ]}

def ctx(**extra):
 d={'source_step':3,'source_revision':8,'sensors':{'rain':{'value':'dry'},'wind_east_m_s':{'value':0},'cooking':{'value':False}},'modes':{'fire':False}}
 for k,v in extra.items(): d[k]=v
 return d

def test_rain_scopes_all_exterior_windows_and_clamps():
 c=ctx(); c['sensors']['rain']['value']='wet'; comp=compile_safety_graph(graph(),CAT); e=evaluate_safety_graph(compiled=comp,source_step=3,source_revision=8,context=c,entity_catalog=CAT)
 a=apply_graph_constraints(action={'source_step':3,'source_revision':8,'changes':{'window_kitchen':{'open_ratio':.8},'window_bed':{'open_ratio':.6}}},evaluation=e)
 assert a['changes']['window_kitchen']['open_ratio']==0 and a['changes']['window_bed']['open_ratio']==0

def test_east_wind_only_east_facade():
 c=ctx(); c['sensors']['wind_east_m_s']['value']=15; e=evaluate_safety_graph(compiled=compile_safety_graph(graph(),CAT),source_step=3,source_revision=8,context=c,entity_catalog=CAT)
 a=apply_graph_constraints(action={'source_step':3,'source_revision':8,'changes':{'window_kitchen':{'open_ratio':.8},'window_bed':{'open_ratio':.6}}},evaluation=e)
 assert a['changes']['window_kitchen']['open_ratio']==0 and a['changes']['window_bed']['open_ratio']==.6

def test_multihop_cooking_fact_generates_hood_and_makeup_air():
 c=ctx(); c['sensors']['cooking']['value']=True; e=evaluate_safety_graph(compiled=compile_safety_graph(graph(),CAT),source_step=3,source_revision=8,context=c,entity_catalog=CAT)
 assert e['generated_changes']['hood_kitchen']['fan_level']==1 and e['generated_changes']['window_kitchen']['open_ratio']==.2

def test_fire_derives_emergency_context_for_v30_supervisor():
 c=ctx(); c['modes']['fire']=True; e=evaluate_safety_graph(compiled=compile_safety_graph(graph(),CAT),source_step=3,source_revision=8,context=c,entity_catalog=CAT)
 assert e['expanded_context']['emergency_close'] is True

def test_conflicting_constraints_fail_closed():
 g={'rules':[{'id':'a','when':{'path':'modes.x','op':'truthy'},'effects':[{'kind':'constrain','selector':{'ids':['window_kitchen']},'property':'open_ratio','op':'min','value':.8}]},{'id':'b','when':{'path':'modes.x','op':'truthy'},'effects':[{'kind':'constrain','selector':{'ids':['window_kitchen']},'property':'open_ratio','op':'max','value':.2}]}]}
 c={'source_step':3,'source_revision':8,'modes':{'x':True}}
 with pytest.raises(SafetyConstraintConflict): evaluate_safety_graph(compiled=compile_safety_graph(g,CAT),source_step=3,source_revision=8,context=c,entity_catalog=CAT)

def test_cycle_detected():
 # A produces x and reads y; B produces y and reads x.
 g={'rules':[{'id':'a','when':{'path':'facts.y','op':'truthy'},'effects':[{'kind':'set_fact','key':'x','value':True}]},{'id':'b','when':{'path':'facts.x','op':'truthy'},'effects':[{'kind':'set_fact','key':'y','value':True}]}]}
 with pytest.raises(SafetyGraphCycleError): compile_safety_graph(g,CAT)
