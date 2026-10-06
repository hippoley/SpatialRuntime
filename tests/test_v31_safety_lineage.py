import json, pytest
from spatialruntime.safety.lineage import DurableSafetyLatch, SafetyJournalIntegrityError, SafetyRuleDriftError

def test_latches_survive_restart(tmp_path):
 p=tmp_path/'safety.journal'
 s=DurableSafetyLatch(journal_path=p)
 s.set_latches(maintenance_lock=True,child_lock=True,reason='service',actor='operator')
 s2=DurableSafetyLatch(journal_path=p)
 assert s2.maintenance_lock and s2.child_lock and s2.reason=='service'

def test_manual_hold_is_folded_into_maintenance_lock_context(tmp_path):
 s=DurableSafetyLatch(journal_path=tmp_path/'j')
 s.set_latches(manual_global_hold=True)
 c=s.apply_to_context({"source_step":1,"source_revision":2})
 assert c['maintenance_lock'] is True and c['manual_global_hold'] is True

def test_tamper_rejected(tmp_path):
 p=tmp_path/'j'; s=DurableSafetyLatch(journal_path=p); s.set_latches(emergency_close=True)
 lines=p.read_text().splitlines(); e=json.loads(lines[-1]); e['payload']['changes']['emergency_close']=False; lines[-1]=json.dumps(e)
 p.write_text('\n'.join(lines)+'\n')
 with pytest.raises(SafetyJournalIntegrityError): DurableSafetyLatch(journal_path=p)

def test_policy_drift_requires_approval(tmp_path):
 p=tmp_path/'j'; DurableSafetyLatch(journal_path=p)
 with pytest.raises(SafetyRuleDriftError): DurableSafetyLatch(journal_path=p,policy={"max_wind_m_s_for_opening":5})

def test_approved_policy_revision_recorded(tmp_path):
 p=tmp_path/'j'; s=DurableSafetyLatch(journal_path=p)
 snap=s.approve_policy_change({"max_wind_m_s_for_opening":5},actor='safety_admin',reason='site calibration')
 assert snap['policy_revision']==1
 # must restart with the approved policy content
 s2=DurableSafetyLatch(journal_path=p,policy={"max_wind_m_s_for_opening":5})
 assert s2.policy_revision==1
