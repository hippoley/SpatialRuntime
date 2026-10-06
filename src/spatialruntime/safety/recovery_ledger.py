from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable

from spatialruntime.safety.recovery import RecoveryStateMachine, RecoveryPolicy, RecoveryError

SCHEMA="fault_recovery_journal_v2.9"

class RecoveryJournalIntegrityError(RecoveryError): pass


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",",":"), ensure_ascii=False)

def _hash(prev: str, body: dict[str, Any]) -> str:
    return sha256((prev+"\n"+_canonical(body)).encode()).hexdigest()


class DurableRecoveryStateMachine(RecoveryStateMachine):
    def __init__(self, *, entity_id: str, device_id: str, journal_path: str|Path,
                 policy: RecoveryPolicy|dict[str,Any]|None=None, recover: bool=True):
        super().__init__(entity_id=entity_id,device_id=device_id,policy=policy)
        self.journal_path=Path(journal_path); self.journal_path.parent.mkdir(parents=True,exist_ok=True)
        self._last_hash="0"*64; self._replaying=False
        if recover and self.journal_path.exists(): self._recover()

    def _append(self, kind: str, payload: dict[str,Any]) -> None:
        if self._replaying: return
        seq=1
        if self.journal_path.exists():
            seq=sum(1 for l in self.journal_path.read_text(encoding='utf-8').splitlines() if l.strip())+1
        body={"schema":SCHEMA,"seq":seq,"kind":kind,"payload":payload}
        h=_hash(self._last_hash,body)
        e={**body,"prev_hash":self._last_hash,"hash":h}
        with self.journal_path.open('a',encoding='utf-8') as f: f.write(_canonical(e)+'\n')
        self._last_hash=h

    def observe(self, **kwargs):
        out=super().observe(**kwargs); self._append('observe',kwargs); return out
    def confirm_release(self, **kwargs):
        out=super().confirm_release(**kwargs); self._append('confirm_release',kwargs); return out
    def confirm_retry(self, **kwargs):
        out=super().confirm_retry(**kwargs); self._append('confirm_retry',kwargs); return out

    def verify_journal(self)->dict[str,Any]:
        prev='0'*64; seq=1; count=0
        if not self.journal_path.exists(): return {"valid":True,"entries":0,"last_hash":prev}
        for lineno,line in enumerate(self.journal_path.read_text(encoding='utf-8').splitlines(),1):
            if not line.strip(): continue
            try:e=json.loads(line)
            except Exception as exc: raise RecoveryJournalIntegrityError(f'invalid JSON at line {lineno}') from exc
            if e.get('schema')!=SCHEMA or int(e.get('seq',-1))!=seq: raise RecoveryJournalIntegrityError(f'sequence/schema mismatch at line {lineno}')
            if e.get('prev_hash')!=prev: raise RecoveryJournalIntegrityError(f'prev_hash mismatch at line {lineno}')
            body={k:e[k] for k in ('schema','seq','kind','payload')}
            h=_hash(prev,body)
            if h!=e.get('hash'): raise RecoveryJournalIntegrityError(f'hash mismatch at line {lineno}')
            prev=h; seq+=1; count+=1
        return {"valid":True,"entries":count,"last_hash":prev}

    def _recover(self)->None:
        meta=self.verify_journal(); self._last_hash=meta['last_hash']; self._replaying=True
        try:
            for line in self.journal_path.read_text(encoding='utf-8').splitlines():
                if not line.strip(): continue
                e=json.loads(line); k=e['kind']; p=e['payload']
                if k=='observe': super().observe(**p)
                elif k=='confirm_release': super().confirm_release(**p)
                elif k=='confirm_retry': super().confirm_retry(**p)
                else: raise RecoveryJournalIntegrityError(f'unsupported journal kind: {k}')
        finally:self._replaying=False
