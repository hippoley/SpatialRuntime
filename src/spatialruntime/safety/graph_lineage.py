from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping
from spatialruntime.safety.dependency_graph import compile_safety_graph, graph_fingerprint, SafetyGraphError

SCHEMA='safety_graph_lineage_v3.5'
STATE_SCHEMA='safety_graph_state_v3.5'

class SafetyGraphJournalIntegrityError(SafetyGraphError): pass
class SafetyGraphDriftError(SafetyGraphError): pass

def _canon(obj:Any)->str: return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def _hash(prev:str, body:Mapping[str,Any])->str: return sha256((prev+'\n'+_canon(body)).encode()).hexdigest()

class DurableSafetyGraphLineage:
    def __init__(self, *, journal_path:str|Path, graph:Mapping[str,Any], entity_catalog:Mapping[str,Mapping[str,Any]], recover:bool=True):
        self.path=Path(journal_path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.entity_catalog=dict(entity_catalog)
        self.graph=dict(graph)
        self.compiled=compile_safety_graph(self.graph,self.entity_catalog)
        self.graph_fingerprint=self.compiled.fingerprint
        self.graph_revision=0; self._last_hash='0'*64
        if recover and self.path.exists(): self._recover()
        elif not self.path.exists(): self._append('init',{'graph_fingerprint':self.graph_fingerprint,'graph_revision':0})

    def snapshot(self)->dict[str,Any]:
        return {'schema':STATE_SCHEMA,'graph_fingerprint':self.graph_fingerprint,'graph_revision':self.graph_revision,'rule_count':len(self.compiled.rules)}

    def assert_graph_matches(self, graph:Mapping[str,Any])->None:
        fp=compile_safety_graph(graph,self.entity_catalog).fingerprint
        if fp!=self.graph_fingerprint: raise SafetyGraphDriftError('safety graph fingerprint mismatch; explicit approval required')

    def approve_graph_change(self, graph:Mapping[str,Any], *, actor:str, reason:str)->dict[str,Any]:
        compiled=compile_safety_graph(graph,self.entity_catalog); fp=compiled.fingerprint
        if fp==self.graph_fingerprint: return self.snapshot()
        old=self.graph_fingerprint; self.graph=dict(graph); self.compiled=compiled; self.graph_fingerprint=fp; self.graph_revision+=1
        self._append('graph_change',{'old_fingerprint':old,'new_fingerprint':fp,'graph_revision':self.graph_revision,'actor':actor,'reason':reason})
        return self.snapshot()

    def _append(self, kind:str, payload:dict[str,Any])->None:
        seq=1
        if self.path.exists(): seq=sum(1 for x in self.path.read_text(encoding='utf-8').splitlines() if x.strip())+1
        body={'schema':SCHEMA,'seq':seq,'kind':kind,'payload':payload}; h=_hash(self._last_hash,body)
        event={**body,'prev_hash':self._last_hash,'hash':h}
        with self.path.open('a',encoding='utf-8') as f:f.write(_canon(event)+'\n')
        self._last_hash=h

    def verify_journal(self)->dict[str,Any]:
        prev='0'*64; seq=1; count=0
        for lineno,line in enumerate(self.path.read_text(encoding='utf-8').splitlines() if self.path.exists() else [],1):
            if not line.strip(): continue
            try:e=json.loads(line)
            except Exception as exc: raise SafetyGraphJournalIntegrityError(f'invalid JSON at line {lineno}') from exc
            if e.get('schema')!=SCHEMA or int(e.get('seq',-1))!=seq: raise SafetyGraphJournalIntegrityError(f'sequence/schema mismatch at line {lineno}')
            if e.get('prev_hash')!=prev: raise SafetyGraphJournalIntegrityError(f'prev_hash mismatch at line {lineno}')
            body={k:e[k] for k in ('schema','seq','kind','payload')}; h=_hash(prev,body)
            if h!=e.get('hash'): raise SafetyGraphJournalIntegrityError(f'hash mismatch at line {lineno}')
            prev=h; seq+=1; count+=1
        return {'valid':True,'entries':count,'last_hash':prev}

    def _recover(self)->None:
        meta=self.verify_journal(); self._last_hash=meta['last_hash']; approved=None
        for line in self.path.read_text(encoding='utf-8').splitlines():
            if not line.strip():continue
            e=json.loads(line); p=e['payload']
            if e['kind']=='init': approved=p['graph_fingerprint']; self.graph_revision=int(p.get('graph_revision',0))
            elif e['kind']=='graph_change': approved=p['new_fingerprint']; self.graph_revision=int(p['graph_revision'])
            else: raise SafetyGraphJournalIntegrityError(f"unsupported journal kind: {e['kind']}")
        if approved is None: raise SafetyGraphJournalIntegrityError('journal missing init graph fingerprint')
        supplied=self.compiled.fingerprint; self.graph_fingerprint=approved
        if supplied!=approved: raise SafetyGraphDriftError('supplied safety graph does not match approved journal lineage')
