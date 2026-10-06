import json, pytest
from spatialruntime.safety.graph_lineage import *
from spatialruntime.safety.dependency_graph import SCHEMA
CAT={'w':{'kind':'window','exterior':True}}
def graph(limit=0): return {'schema':SCHEMA,'rules':[{'id':'rain','when':{'path':'sensors.rain.value','op':'eq','value':'wet'},'effects':[{'kind':'constrain','selector':{'ids':['w']},'property':'open_ratio','op':'max','value':limit}]}]}

def test_unapproved_rule_change_rejected(tmp_path):
 p=tmp_path/'g.journal'; DurableSafetyGraphLineage(journal_path=p,graph=graph(0),entity_catalog=CAT)
 with pytest.raises(SafetyGraphDriftError): DurableSafetyGraphLineage(journal_path=p,graph=graph(.2),entity_catalog=CAT)

def test_approved_change_advances_revision_and_recovers(tmp_path):
 p=tmp_path/'g.journal'; d=DurableSafetyGraphLineage(journal_path=p,graph=graph(0),entity_catalog=CAT); s=d.approve_graph_change(graph(.2),actor='ops',reason='approved calibration')
 assert s['graph_revision']==1
 d2=DurableSafetyGraphLineage(journal_path=p,graph=graph(.2),entity_catalog=CAT); assert d2.graph_revision==1

def test_tamper_detected(tmp_path):
 p=tmp_path/'g.journal'; d=DurableSafetyGraphLineage(journal_path=p,graph=graph(0),entity_catalog=CAT)
 rows=p.read_text().splitlines(); e=json.loads(rows[0]); e['payload']['graph_revision']=99; rows[0]=json.dumps(e); p.write_text('\n'.join(rows)+'\n')
 with pytest.raises(SafetyGraphJournalIntegrityError): DurableSafetyGraphLineage(journal_path=p,graph=graph(0),entity_catalog=CAT)
