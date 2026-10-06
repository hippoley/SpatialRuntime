from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
import copy, hashlib, json

SCHEMA = "whole_home_safety_graph_v3.3"
DECISION_SCHEMA = "whole_home_safety_evaluation_v3.3"

class SafetyGraphError(RuntimeError): pass
class SafetyGraphCycleError(SafetyGraphError): pass
class SafetyConstraintConflict(SafetyGraphError): pass
class StaleSafetyGraphContext(SafetyGraphError): pass


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",",":"), ensure_ascii=False)

def graph_fingerprint(graph: Mapping[str,Any]) -> str:
    return hashlib.sha256(_canon(graph).encode()).hexdigest()

def _path_get(root: Mapping[str,Any], path: str) -> Any:
    cur: Any = root
    for part in path.split('.'):
        if not isinstance(cur, Mapping) or part not in cur: return None
        cur = cur[part]
    return cur

def _match(value: Any, pred: Mapping[str,Any]) -> bool:
    op=pred.get('op','eq'); expected=pred.get('value')
    if op=='eq': return value==expected
    if op=='ne': return value!=expected
    if value is None: return False
    if op=='gt': return float(value)>float(expected)
    if op=='gte': return float(value)>=float(expected)
    if op=='lt': return float(value)<float(expected)
    if op=='lte': return float(value)<=float(expected)
    if op=='in': return value in (expected or [])
    if op=='truthy': return bool(value)
    raise SafetyGraphError(f"unsupported predicate op: {op}")

def _select(catalog: Mapping[str,Mapping[str,Any]], selector: Mapping[str,Any]) -> list[str]:
    ids=selector.get('ids')
    if ids is not None:
        out=[]
        for eid in ids:
            if eid not in catalog: raise SafetyGraphError(f"selector references unknown entity: {eid}")
            out.append(eid)
        return sorted(set(out))
    where=selector.get('where') or {}
    if not isinstance(where,Mapping): raise SafetyGraphError('selector.where must be object')
    out=[]
    for eid,meta in catalog.items():
        if all(meta.get(k)==v for k,v in where.items()): out.append(eid)
    return sorted(out)

@dataclass(frozen=True)
class CompiledSafetyGraph:
    graph: Mapping[str,Any]
    fingerprint: str
    order: tuple[str,...]
    rules: Mapping[str,Mapping[str,Any]]


def compile_safety_graph(graph: Mapping[str,Any], entity_catalog: Mapping[str,Mapping[str,Any]]) -> CompiledSafetyGraph:
    if graph.get('schema') not in {None,SCHEMA}: raise SafetyGraphError('unsupported graph schema')
    rules_in=graph.get('rules') or []
    if not isinstance(rules_in,Sequence): raise SafetyGraphError('rules must be array')
    rules: dict[str,Mapping[str,Any]]={}
    producers: dict[str,str]={}
    for raw in rules_in:
        if not isinstance(raw,Mapping): raise SafetyGraphError('rule must be object')
        rid=str(raw.get('id') or '')
        if not rid or rid in rules: raise SafetyGraphError(f'invalid/duplicate rule id: {rid}')
        cond=raw.get('when') or {}
        if not isinstance(cond,Mapping) or not cond.get('path'): raise SafetyGraphError(f'{rid}: when.path required')
        for eff in raw.get('effects') or []:
            if not isinstance(eff,Mapping): raise SafetyGraphError(f'{rid}: effect must be object')
            kind=eff.get('kind')
            if kind in {'constrain','emit_change'}: _select(entity_catalog, eff.get('selector') or {})
            if kind=='set_fact':
                key=str(eff.get('key') or '')
                if not key: raise SafetyGraphError(f'{rid}: set_fact key required')
                if key in producers: raise SafetyGraphError(f'fact has multiple producers: {key}')
                producers[key]=rid
            elif kind=='set_context':
                if not eff.get('path'): raise SafetyGraphError(f'{rid}: set_context path required')
            elif kind=='constrain':
                if eff.get('op') not in {'max','min','eq'}: raise SafetyGraphError(f'{rid}: bad constraint op')
                if not eff.get('property'): raise SafetyGraphError(f'{rid}: constraint property required')
            elif kind=='emit_change':
                if not isinstance(eff.get('changes'),Mapping): raise SafetyGraphError(f'{rid}: changes required')
            else: raise SafetyGraphError(f'{rid}: unsupported effect kind {kind}')
        rules[rid]=dict(raw)
    # Dependencies are explicit through facts.<name> produced by set_fact.
    deps={rid:set() for rid in rules}
    for rid,r in rules.items():
        p=str((r.get('when') or {}).get('path'))
        if p.startswith('facts.'):
            key=p.split('.',1)[1]
            if key in producers: deps[rid].add(producers[key])
    # Kahn, deterministic.
    order=[]; pending={k:set(v) for k,v in deps.items()}
    while pending:
        ready=sorted(k for k,v in pending.items() if not v)
        if not ready: raise SafetyGraphCycleError(f"cyclic safety graph: {sorted(pending)}")
        for rid in ready:
            order.append(rid); pending.pop(rid)
        for v in pending.values(): v.difference_update(ready)
    normalized={'schema':SCHEMA,'rules':[rules[r] for r in sorted(rules)]}
    return CompiledSafetyGraph(normalized,graph_fingerprint(normalized),tuple(order),rules)


def evaluate_safety_graph(*, compiled: CompiledSafetyGraph, source_step:int, source_revision:int,
                          context: Mapping[str,Any], entity_catalog: Mapping[str,Mapping[str,Any]]) -> dict[str,Any]:
    if int(context.get('source_step',-1))!=int(source_step) or int(context.get('source_revision',-1))!=int(source_revision):
        raise StaleSafetyGraphContext('context step/revision mismatch')
    work=copy.deepcopy(dict(context)); work.setdefault('facts',{})
    constraints: dict[str,dict[str,dict[str,Any]]]={}
    generated: dict[str,dict[str,Any]]={}
    activations=[]
    for rid in compiled.order:
        r=compiled.rules[rid]; cond=r['when']; observed=_path_get(work,str(cond['path']))
        if not _match(observed,cond): continue
        priority=int(r.get('priority',50)); activations.append({'rule_id':rid,'priority':priority,'observed':observed})
        for eff in r.get('effects') or []:
            kind=eff['kind']
            if kind=='set_fact': work.setdefault('facts',{})[str(eff['key'])]=eff.get('value')
            elif kind=='set_context':
                path=str(eff['path'])
                if '.' in path: raise SafetyGraphError('set_context currently supports top-level paths only')
                work[path]=eff.get('value')
            elif kind=='emit_change':
                for eid in _select(entity_catalog,eff.get('selector') or {}):
                    dst=generated.setdefault(eid,{})
                    for prop,val in (eff.get('changes') or {}).items():
                        old=dst.get(prop)
                        if old is not None and old!=val: raise SafetyConstraintConflict(f'conflicting generated change for {eid}.{prop}')
                        dst[prop]=val
            elif kind=='constrain':
                prop=str(eff['property']); op=str(eff['op']); val=float(eff['value'])
                for eid in _select(entity_catalog,eff.get('selector') or {}):
                    c=constraints.setdefault(eid,{}).setdefault(prop,{'min':None,'max':None,'eq':None,'rules':[]})
                    if op=='min': c['min']=val if c['min'] is None else max(float(c['min']),val)
                    elif op=='max': c['max']=val if c['max'] is None else min(float(c['max']),val)
                    else:
                        if c['eq'] is not None and float(c['eq'])!=val: raise SafetyConstraintConflict(f'conflicting eq for {eid}.{prop}')
                        c['eq']=val
                    c['rules'].append(rid)
                    if c['eq'] is not None:
                        if c['min'] is not None and float(c['eq'])<float(c['min']): raise SafetyConstraintConflict(f'eq below min for {eid}.{prop}')
                        if c['max'] is not None and float(c['eq'])>float(c['max']): raise SafetyConstraintConflict(f'eq above max for {eid}.{prop}')
                    if c['min'] is not None and c['max'] is not None and float(c['min'])>float(c['max']): raise SafetyConstraintConflict(f'min exceeds max for {eid}.{prop}')
    return {'schema':DECISION_SCHEMA,'source_step':int(source_step),'source_revision':int(source_revision),
            'graph_fingerprint':compiled.fingerprint,'expanded_context':work,'constraints':constraints,
            'generated_changes':generated,'activations':sorted(activations,key=lambda x:(-x['priority'],x['rule_id']))}


def apply_graph_constraints(*, action: Mapping[str,Any], evaluation: Mapping[str,Any]) -> dict[str,Any]:
    if int(action.get('source_step',-1))!=int(evaluation.get('source_step',-1)) or int(action.get('source_revision',-1))!=int(evaluation.get('source_revision',-1)):
        raise StaleSafetyGraphContext('action/evaluation mismatch')
    changes={k:dict(v) for k,v in (action.get('changes') or {}).items() if isinstance(v,Mapping)}
    # Generated safety changes override policy; constraints then clamp both.
    for eid,ch in (evaluation.get('generated_changes') or {}).items(): changes.setdefault(eid,{}).update(ch)
    decisions={}
    for eid,ch in list(changes.items()):
        for prop,val in list(ch.items()):
            c=((evaluation.get('constraints') or {}).get(eid) or {}).get(prop)
            if not c: continue
            v=float(val); original=v
            if c.get('eq') is not None: v=float(c['eq'])
            if c.get('min') is not None: v=max(v,float(c['min']))
            if c.get('max') is not None: v=min(v,float(c['max']))
            if v!=original:
                ch[prop]=v; decisions[f'{eid}.{prop}']={'decision':'clamp','requested':original,'committed':v,'rules':list(c.get('rules') or [])}
    return {'schema':'safety_graph_action_v3.3','source_step':evaluation['source_step'],'source_revision':evaluation['source_revision'],
            'kind':'safety_graph_applied','changes':changes,'decisions':decisions,'graph_fingerprint':evaluation['graph_fingerprint']}
