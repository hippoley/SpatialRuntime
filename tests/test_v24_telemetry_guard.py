from spatialruntime.hardware.telemetry import *

def evt(seq,at,state=None):
    return {"schema":TELEMETRY_SCHEMA,"source_step":2,"source_revision":4,"device_id":"d1","sequence":seq,
            "observed_at_ms":at,"state":state or {"open_ratio":0.5},"quality":0.98,"command_id":"cmd1"}

def test_order_dedupe_and_feedback():
    l=TelemetryLedger(); l.ingest(evt(1,1000),expected_step=2,expected_revision=4)
    l.ingest(evt(1,1000),expected_step=2,expected_revision=4)
    l.ingest(evt(2,1100,{"open_ratio":0.6}),expected_step=2,expected_revision=4)
    f=l.build_device_feedback(case_id="c",source_step=2,source_revision=4,entity_by_device={"d1":"window"},max_age_ms=500,now_ms=1200)
    assert f["complete"] and f["devices"]["window"]["state"]["open_ratio"]==0.6

def test_regression_and_conflict_rejected():
    l=TelemetryLedger(); l.ingest(evt(2,1100),expected_step=2,expected_revision=4)
    try: l.ingest(evt(1,1200),expected_step=2,expected_revision=4); assert False
    except TelemetryStaleError: pass
    try: l.ingest(evt(2,1100,{"open_ratio":0.9}),expected_step=2,expected_revision=4); assert False
    except TelemetryConflictError: pass

def test_stale_not_promoted():
    l=TelemetryLedger(); l.ingest(evt(1,1000),expected_step=2,expected_revision=4)
    f=l.build_device_feedback(case_id="c",source_step=2,source_revision=4,entity_by_device={"d1":"window"},max_age_ms=100,now_ms=1300)
    assert not f["complete"] and not f["devices"] and f["incomplete"][0]["reason"]=="stale_telemetry"

def test_wrong_revision_rejected():
    l=TelemetryLedger()
    try: l.ingest(evt(1,1000),expected_step=2,expected_revision=5); assert False
    except TelemetryStaleError: pass
