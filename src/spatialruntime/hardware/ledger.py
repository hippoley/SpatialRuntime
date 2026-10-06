from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from spatialruntime.hardware.contract import CommandLedger, CommandRecord, HardwareContractError, _canonical

SCHEMA="hardware_command_journal_v2.1"

class JournalIntegrityError(HardwareContractError): pass


def _hash_entry(prev_hash: str, body: dict[str, Any]) -> str:
    return sha256((prev_hash + "\n" + _canonical(body)).encode()).hexdigest()


class DurableCommandLedger(CommandLedger):
    """Append-only JSONL journal with a hash chain and replay-based recovery."""
    def __init__(self, journal_path: str | Path, *, recover: bool=True):
        super().__init__()
        self.journal_path=Path(journal_path)
        self.journal_path.parent.mkdir(parents=True,exist_ok=True)
        self._last_hash="0"*64
        self._replaying=False
        if recover and self.journal_path.exists():
            self._recover()

    def _append(self, kind: str, payload: dict[str, Any]) -> None:
        if self._replaying: return
        body={"schema":SCHEMA,"seq":self._next_seq(),"kind":kind,"payload":payload}
        h=_hash_entry(self._last_hash,body)
        entry={**body,"prev_hash":self._last_hash,"hash":h}
        with self.journal_path.open("a",encoding="utf-8") as f:
            f.write(_canonical(entry)+"\n")
            f.flush()
        self._last_hash=h

    def _next_seq(self)->int:
        if not self.journal_path.exists(): return 1
        with self.journal_path.open("r",encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())+1

    def register_batch(self,batch:dict[str,Any])->None:
        before=set(self.records)
        super().register_batch(batch)
        added=[self.records[c].command for c in self.records if c not in before]
        if added: self._append("register_batch",{"commands":added})

    def mark_dispatched(self,command_id:str,*,now_ms:int)->dict[str,Any]:
        pre=self.snapshot(command_id)
        out=super().mark_dispatched(command_id,now_ms=now_ms)
        if out!=pre: self._append("mark_dispatched",{"command_id":command_id,"now_ms":int(now_ms)})
        return out

    def ingest_event(self,event:dict[str,Any],*,expected_step:int,expected_revision:int)->dict[str,Any]:
        before=self.snapshot(event.get("command_id"))
        out=super().ingest_event(event,expected_step=expected_step,expected_revision=expected_revision)
        if out!=before:
            self._append("ingest_event",{"event":event,"expected_step":int(expected_step),"expected_revision":int(expected_revision)})
        return out

    def due_retries(self,*,now_ms:int)->list[str]:
        before={cid:self.snapshot(cid) for cid in self.records}
        out=super().due_retries(now_ms=now_ms)
        changed=[cid for cid in self.records if self.snapshot(cid)!=before[cid]]
        if changed: self._append("due_retries",{"now_ms":int(now_ms),"changed":changed})
        return out

    def feedback_timeouts(self,*,now_ms:int)->list[str]:
        before={cid:self.snapshot(cid) for cid in self.records}
        out=super().feedback_timeouts(now_ms=now_ms)
        changed=[cid for cid in self.records if self.snapshot(cid)!=before[cid]]
        if changed: self._append("feedback_timeouts",{"now_ms":int(now_ms),"changed":changed})
        return out

    def verify_journal(self)->dict[str,Any]:
        prev="0"*64; expected_seq=1; count=0
        if not self.journal_path.exists(): return {"valid":True,"entries":0,"last_hash":prev}
        for lineno,line in enumerate(self.journal_path.read_text(encoding="utf-8").splitlines(),1):
            if not line.strip(): continue
            try: e=json.loads(line)
            except Exception as exc: raise JournalIntegrityError(f"invalid JSON at line {lineno}") from exc
            if e.get("schema")!=SCHEMA or int(e.get("seq",-1))!=expected_seq:
                raise JournalIntegrityError(f"journal sequence/schema mismatch at line {lineno}")
            if e.get("prev_hash")!=prev:
                raise JournalIntegrityError(f"prev_hash mismatch at line {lineno}")
            body={k:e[k] for k in ("schema","seq","kind","payload")}
            h=_hash_entry(prev,body)
            if e.get("hash")!=h:
                raise JournalIntegrityError(f"hash mismatch at line {lineno}")
            prev=h; expected_seq+=1; count+=1
        return {"valid":True,"entries":count,"last_hash":prev}

    def _recover(self)->None:
        meta=self.verify_journal(); self._last_hash=meta["last_hash"]; self._replaying=True
        try:
            for line in self.journal_path.read_text(encoding="utf-8").splitlines():
                if not line.strip(): continue
                e=json.loads(line); kind=e["kind"]; p=e["payload"]
                if kind=="register_batch":
                    super().register_batch({"schema":"hardware_dispatch_batch_v2.0","commands":p["commands"]})
                elif kind=="mark_dispatched":
                    super().mark_dispatched(p["command_id"],now_ms=p["now_ms"])
                elif kind=="ingest_event":
                    super().ingest_event(p["event"],expected_step=p["expected_step"],expected_revision=p["expected_revision"])
                elif kind=="due_retries":
                    super().due_retries(now_ms=p["now_ms"])
                elif kind=="feedback_timeouts":
                    super().feedback_timeouts(now_ms=p["now_ms"])
                else:
                    raise JournalIntegrityError(f"unsupported journal kind: {kind}")
        finally:
            self._replaying=False
