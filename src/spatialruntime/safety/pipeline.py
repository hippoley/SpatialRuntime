from __future__ import annotations
from typing import Any, Mapping, Sequence
from spatialruntime.safety.arbitrator import arbitrate_actions
from spatialruntime.safety.dependency_graph import CompiledSafetyGraph, evaluate_safety_graph, apply_graph_constraints
from spatialruntime.safety.supervisor import supervise_actions, SafetyPolicy

SCHEMA='whole_home_safety_pipeline_v3.4'

class SafetyPipelineError(RuntimeError): pass

def run_safety_pipeline(*, source_step:int, source_revision:int,
                        policy_action:Mapping[str,Any]|None,
                        recovery_actions:Sequence[Mapping[str,Any]]|None,
                        runtime_state:Mapping[str,Any], safety_context:Mapping[str,Any],
                        entity_catalog:Mapping[str,Mapping[str,Any]], compiled_graph:CompiledSafetyGraph,
                        supervisor_policy:SafetyPolicy|Mapping[str,Any]|None=None)->dict[str,Any]:
    """Single safe entrypoint for whole-home actions.

    Order is intentional: policy/recovery arbitration -> dependency graph propagation ->
    graph constraints/generated changes -> physical safety supervisor. STOP control actions
    remain non-motion intents and are preserved; every generated motion still reaches supervisor.
    """
    arb=arbitrate_actions(source_step=source_step,source_revision=source_revision,
                          policy_action=policy_action,recovery_actions=recovery_actions)
    ev=evaluate_safety_graph(compiled=compiled_graph,source_step=source_step,source_revision=source_revision,
                             context=safety_context,entity_catalog=entity_catalog)
    constrained=apply_graph_constraints(action=arb,evaluation=ev)
    supervised=supervise_actions(source_step=source_step,source_revision=source_revision,
                                 proposed_action=constrained,runtime_state=runtime_state,
                                 safety_context=ev['expanded_context'],policy=supervisor_policy)
    # STOP is deliberately not converted into motion. It must use the control-action dispatch path.
    controls=list(arb.get('control_actions') or [])
    return {
        'schema':SCHEMA,'source_step':int(source_step),'source_revision':int(source_revision),
        'graph_fingerprint':compiled_graph.fingerprint,
        'motion_changes':supervised['changes'],'control_actions':controls,
        'safe_to_forward':bool(supervised['summary']['safe_to_forward']),
        'trace':{
            'arbitration':arb,
            'graph_evaluation':ev,
            'graph_constrained_action':constrained,
            'supervisor':supervised,
        }
    }
