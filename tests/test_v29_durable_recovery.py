from pathlib import Path
import json
from spatialruntime.safety.recovery_ledger import *

CAP={"writable_properties":["open_ratio"],"actions":["stop"]}
CMD={"command_id":"cmd1","entity_id":"window_1","device_id":"d1","target_state":{"open_ratio":0.8}}
POL={"obstruction_fault_codes":[101],"max_recovery_attempts":1,"release_delta":.1}
def tel(pos=.4,fault=101): return {"device_id":"d1","state":{"open_ratio":pos},"health":{"fault_code":fault}}

def test_restart_during_release_preserves_attempt(tmp_path):
    p=tmp_path/'recovery.jsonl'
    m=DurableRecoveryStateMachine(entity_id='window_1',device_id='d1',journal_path=p,policy=POL)
    m.observe(source_step=1,source_revision=1,command=CMD,telemetry=tel(),convergence={'converged':False},capability=CAP)
    assert m.state=='release_pending' and m.recovery_attempts==1
    m2=DurableRecoveryStateMachine(entity_id='window_1',device_id='d1',journal_path=p,policy=POL)
    assert m2.state=='release_pending' and m2.recovery_attempts==1
    r=m2.confirm_release(source_step=1,source_revision=1,telemetry=tel(.3,0),capability=CAP)
    assert r['state']=='retry_pending'

def test_restart_after_manual_latch_stays_latched(tmp_path):
    p=tmp_path/'r.jsonl'; m=DurableRecoveryStateMachine(entity_id='window_1',device_id='d1',journal_path=p,policy=POL)
    m.observe(source_step=1,source_revision=1,command=CMD,telemetry=tel(.4,777),convergence={'converged':False},capability=CAP)
    m2=DurableRecoveryStateMachine(entity_id='window_1',device_id='d1',journal_path=p,policy=POL)
    assert m2.state=='manual_service_required' and m2.latched_fault_code==777

def test_tamper_detected(tmp_path):
    p=tmp_path/'r.jsonl'; m=DurableRecoveryStateMachine(entity_id='window_1',device_id='d1',journal_path=p,policy=POL)
    m.observe(source_step=1,source_revision=1,command=CMD,telemetry=tel(),convergence={'converged':False},capability=CAP)
    rows=p.read_text().splitlines(); e=json.loads(rows[0]); e['payload']['source_revision']=99; rows[0]=json.dumps(e)
    p.write_text('\n'.join(rows)+'\n')
    try: DurableRecoveryStateMachine(entity_id='window_1',device_id='d1',journal_path=p,policy=POL); assert False
    except RecoveryJournalIntegrityError: pass
