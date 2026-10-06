from __future__ import annotations
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from spatialruntime.safety.supervisor import SafetyPolicy, SafetySupervisorError

SCHEMA="safety_latch_journal_v3.1"
STATE_SCHEMA="safety_latch_state_v3.1"

class SafetyJournalIntegrityError(SafetySupervisorError): pass
class SafetyRuleDriftError(SafetySupervisorError): pass

def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",",":"), ensure_ascii=False, default=list)

def _hash(prev: str, body: dict[str,Any]) -> str:
    return sha256((prev+"\n"+_canonical(body)).encode()).hexdigest()

def policy_fingerprint(policy: SafetyPolicy|Mapping[str,Any]|None) -> str:
    p=policy if isinstance(policy,SafetyPolicy) else SafetyPolicy.from_mapping(policy)
    data=asdict(p); data["wet_values"]=sorted([repr(x) for x in p.wet_values])
    return sha256(_canonical(data).encode()).hexdigest()

class DurableSafetyLatch:
    """Persist operator/safety latches with tamper-evident history and rule lineage."""
    def __init__(self, *, journal_path: str|Path, policy: SafetyPolicy|Mapping[str,Any]|None=None, recover: bool=True):
        self.journal_path=Path(journal_path); self.journal_path.parent.mkdir(parents=True,exist_ok=True)
        self.policy=policy if isinstance(policy,SafetyPolicy) else SafetyPolicy.from_mapping(policy)
        self.policy_fingerprint=policy_fingerprint(self.policy)
        self.policy_revision=0
        self.maintenance_lock=False
        self.child_lock=False
        self.emergency_close=False
        self.manual_global_hold=False
        self.reason: str|None=None
        self._last_hash="0"*64
        if recover and self.journal_path.exists(): self._recover()
        elif not self.journal_path.exists(): self._append("init", {"policy_fingerprint":self.policy_fingerprint,"policy_revision":0})

    def snapshot(self)->dict[str,Any]:
        return {"schema":STATE_SCHEMA,"policy_fingerprint":self.policy_fingerprint,"policy_revision":self.policy_revision,
                "maintenance_lock":self.maintenance_lock,"child_lock":self.child_lock,"emergency_close":self.emergency_close,
                "manual_global_hold":self.manual_global_hold,"reason":self.reason}

    def set_latches(self, *, maintenance_lock: bool|None=None, child_lock: bool|None=None,
                    emergency_close: bool|None=None, manual_global_hold: bool|None=None,
                    reason: str|None=None, actor: str="system") -> dict[str,Any]:
        changes={}
        for name,val in (("maintenance_lock",maintenance_lock),("child_lock",child_lock),("emergency_close",emergency_close),("manual_global_hold",manual_global_hold)):
            if val is not None and bool(val)!=getattr(self,name):
                setattr(self,name,bool(val)); changes[name]=bool(val)
        if reason is not None: self.reason=str(reason)
        if changes or reason is not None:
            self._append("set_latches",{"changes":changes,"reason":self.reason,"actor":actor})
        return self.snapshot()

    def approve_policy_change(self, new_policy: SafetyPolicy|Mapping[str,Any], *, actor: str, reason: str)->dict[str,Any]:
        p=new_policy if isinstance(new_policy,SafetyPolicy) else SafetyPolicy.from_mapping(new_policy)
        fp=policy_fingerprint(p)
        if fp==self.policy_fingerprint: return self.snapshot()
        old=self.policy_fingerprint; self.policy=p; self.policy_fingerprint=fp; self.policy_revision+=1
        self._append("policy_change",{"old_fingerprint":old,"new_fingerprint":fp,"policy_revision":self.policy_revision,"actor":actor,"reason":reason})
        return self.snapshot()

    def assert_policy_matches(self, policy: SafetyPolicy|Mapping[str,Any]|None)->None:
        fp=policy_fingerprint(policy)
        if fp!=self.policy_fingerprint:
            raise SafetyRuleDriftError("safety policy fingerprint mismatch; explicit approval required")

    def apply_to_context(self, ctx: Mapping[str,Any])->dict[str,Any]:
        out=dict(ctx)
        out["maintenance_lock"]=bool(out.get("maintenance_lock",False) or self.maintenance_lock or self.manual_global_hold)
        out["child_lock"]=bool(out.get("child_lock",False) or self.child_lock)
        out["emergency_close"]=bool(out.get("emergency_close",False) or self.emergency_close)
        out["safety_policy_revision"]=self.policy_revision
        out["safety_policy_fingerprint"]=self.policy_fingerprint
        if self.manual_global_hold: out["manual_global_hold"]=True
        return out

    def _append(self, kind: str, payload: dict[str,Any])->None:
        seq=1
        if self.journal_path.exists(): seq=sum(1 for l in self.journal_path.read_text(encoding='utf-8').splitlines() if l.strip())+1
        body={"schema":SCHEMA,"seq":seq,"kind":kind,"payload":payload}
        h=_hash(self._last_hash,body); e={**body,"prev_hash":self._last_hash,"hash":h}
        with self.journal_path.open('a',encoding='utf-8') as f:f.write(_canonical(e)+'\n')
        self._last_hash=h

    def verify_journal(self)->dict[str,Any]:
        prev='0'*64; seq=1; count=0
        for lineno,line in enumerate(self.journal_path.read_text(encoding='utf-8').splitlines() if self.journal_path.exists() else [],1):
            if not line.strip():continue
            try:e=json.loads(line)
            except Exception as exc: raise SafetyJournalIntegrityError(f"invalid JSON at line {lineno}") from exc
            if e.get("schema")!=SCHEMA or int(e.get("seq",-1))!=seq: raise SafetyJournalIntegrityError(f"sequence/schema mismatch at line {lineno}")
            if e.get("prev_hash")!=prev: raise SafetyJournalIntegrityError(f"prev_hash mismatch at line {lineno}")
            body={k:e[k] for k in ("schema","seq","kind","payload")}
            h=_hash(prev,body)
            if h!=e.get("hash"): raise SafetyJournalIntegrityError(f"hash mismatch at line {lineno}")
            prev=h;seq+=1;count+=1
        return {"valid":True,"entries":count,"last_hash":prev}

    def _recover(self)->None:
        meta=self.verify_journal(); self._last_hash=meta["last_hash"]
        approved_fp=None
        for line in self.journal_path.read_text(encoding='utf-8').splitlines():
            if not line.strip():continue
            e=json.loads(line); p=e["payload"]
            if e["kind"]=="init":
                approved_fp=p["policy_fingerprint"]
                self.policy_revision=int(p.get("policy_revision",0))
            elif e["kind"]=="set_latches":
                for k,v in (p.get("changes") or {}).items(): setattr(self,k,bool(v))
                self.reason=p.get("reason")
            elif e["kind"]=="policy_change":
                approved_fp=p["new_fingerprint"]; self.policy_revision=int(p["policy_revision"])
            else: raise SafetyJournalIntegrityError(f"unsupported journal kind: {e['kind']}")
        if approved_fp is None:
            raise SafetyJournalIntegrityError("journal missing init policy fingerprint")
        supplied=policy_fingerprint(self.policy)
        self.policy_fingerprint=approved_fp
        if supplied!=approved_fp:
            raise SafetyRuleDriftError("supplied safety policy does not match approved journal lineage")
