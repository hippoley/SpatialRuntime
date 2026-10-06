from __future__ import annotations
from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any

from spatialruntime.hardware.contract import HardwareContractError, _canonical

TELEMETRY_SCHEMA="device_telemetry_v2.4"

class TelemetryError(HardwareContractError): pass
class TelemetryStaleError(TelemetryError): pass
class TelemetryConflictError(TelemetryError): pass

@dataclass
class DeviceTelemetryState:
    last_sequence: int = -1
    last_observed_at_ms: int = -1
    last_digest: str | None = None
    state: dict[str,Any] = field(default_factory=dict)
    command_id: str | None = None
    quality: float = 1.0

class TelemetryLedger:
    def __init__(self): self.devices: dict[str,DeviceTelemetryState]={}

    def ingest(self,event:dict[str,Any],*,expected_step:int,expected_revision:int)->dict[str,Any]:
        if event.get("schema")!=TELEMETRY_SCHEMA: raise TelemetryError("invalid telemetry schema")
        if int(event.get("source_step",-1))!=int(expected_step) or int(event.get("source_revision",-1))!=int(expected_revision):
            raise TelemetryStaleError("telemetry step/revision mismatch")
        dev=event.get("device_id"); state=event.get("state")
        if not dev or not isinstance(state,dict): raise TelemetryError("device_id/state required")
        seq=int(event.get("sequence",-1)); at=int(event.get("observed_at_ms",-1)); q=float(event.get("quality",1.0))
        if seq<0 or at<0 or not (0.0<=q<=1.0): raise TelemetryError("invalid sequence/time/quality")
        digest=sha256(_canonical(event).encode()).hexdigest()
        cur=self.devices.get(dev)
        if cur:
            if digest==cur.last_digest: return self.snapshot(dev)
            if seq < cur.last_sequence: raise TelemetryStaleError("telemetry sequence regressed")
            if seq == cur.last_sequence:
                raise TelemetryConflictError("same telemetry sequence with different payload")
            if at < cur.last_observed_at_ms: raise TelemetryStaleError("telemetry observed_at regressed")
        self.devices[dev]=DeviceTelemetryState(seq,at,digest,dict(state),event.get("command_id"),q)
        return self.snapshot(dev)

    def snapshot(self,device_id:str)->dict[str,Any]:
        s=self.devices[device_id]
        return {"device_id":device_id,"sequence":s.last_sequence,"observed_at_ms":s.last_observed_at_ms,
                "state":dict(s.state),"command_id":s.command_id,"quality":s.quality}

    def build_device_feedback(self,*,case_id:str,source_step:int,source_revision:int,entity_by_device:dict[str,str],
                              max_age_ms:int,now_ms:int)->dict[str,Any]:
        devices={}; incomplete=[]
        for device_id,entity_id in entity_by_device.items():
            s=self.devices.get(device_id)
            if s is None:
                incomplete.append({"device_id":device_id,"entity_id":entity_id,"reason":"no_telemetry"}); continue
            age=int(now_ms)-s.last_observed_at_ms
            if age<0 or age>int(max_age_ms):
                incomplete.append({"device_id":device_id,"entity_id":entity_id,"reason":"stale_telemetry","age_ms":age}); continue
            devices[entity_id]={"quality":s.quality,"state":dict(s.state),"device_id":device_id,
                                "command_id":s.command_id,"transport_status":"telemetry_confirmed",
                                "telemetry_sequence":s.last_sequence,"observed_at_ms":s.last_observed_at_ms}
        return {"schema":"device_feedback_v2.0","case_id":case_id,"source_step":int(source_step),"source_revision":int(source_revision),
                "devices":devices,"incomplete":incomplete,"complete":len(incomplete)==0}
