from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from spatialruntime.hardware.gateway import capability_fingerprint, DeviceCapabilityError

SCHEMA="capability_lineage_v2.3"

class CapabilityDriftError(DeviceCapabilityError): pass

@dataclass
class CapabilityRecord:
    device_id: str
    fingerprint: str
    revision: int
    capability: dict[str,Any]

class CapabilityRegistry:
    """Pins reviewed device capability. Silent firmware/ThingModel drift fails closed."""
    def __init__(self): self.records: dict[str,CapabilityRecord]={}

    def approve(self, capability: dict[str,Any]) -> dict[str,Any]:
        dev=capability["device_id"]; fp=capability_fingerprint(capability)
        old=self.records.get(dev)
        rev=0 if old is None else old.revision+1
        self.records[dev]=CapabilityRecord(dev,fp,rev,dict(capability))
        return self.snapshot(dev)

    def verify(self, capability: dict[str,Any]) -> dict[str,Any]:
        dev=capability["device_id"]
        rec=self.records.get(dev)
        if rec is None: raise CapabilityDriftError(f"unapproved capability for {dev}")
        fp=capability_fingerprint(capability)
        if fp!=rec.fingerprint:
            raise CapabilityDriftError(f"capability drift for {dev}: reviewed={rec.fingerprint[:12]} current={fp[:12]}")
        return self.snapshot(dev)

    def snapshot(self,device_id:str)->dict[str,Any]:
        r=self.records[device_id]
        return {"schema":SCHEMA,"device_id":device_id,"revision":r.revision,"fingerprint":r.fingerprint,
                "writable_properties":r.capability.get("writable_properties",[]),"thing_model":r.capability.get("thing_model")}
