"""PROPER v2.3 execution-aware lifecycle development namespace.

The frozen v2.2 and v2.2.1 implementations remain in their own packages.
No v2.3 model run is authorized merely by importing this namespace.
"""

from .contracts import (
    ActionEffectClass,
    ActionEffectContract,
    ActionPurpose,
    ActionSpec,
    BudgetPolicy,
    BudgetState,
    ControllerDecision,
    ControllerDisposition,
    ControllerState,
    EvidenceRecord,
    EvidenceSource,
    ExecutionStatus,
)
from .controller import (
    controller_state_from_selection,
    initial_controller_state,
    observe_execution,
    resolve_verification,
    review_action_proposal,
    review_invalid_decision,
    stop_for_agent_decision,
    stop_for_task_completion,
)
from .boundary import (
    action_effect_contract_from_mapping,
    execution_ledger_from_mapping,
    observable_action_from_mapping,
)
from .ledger import ActionExecutionLedger, LedgerEntry
from .continuation import (
    ContinuationDecision,
    ContinuationDisposition,
    ExecutionProgressState,
    ObservableProgressEvidence,
    ProgressStatus,
    SubgoalContract,
    SubgoalStatus,
    initial_progress_state,
    progress_state_from_mapping,
    route_observable_progress,
)
from .acquisition_runtime_protocol import AcquisitionProtocolMachine
from .acquisition_runtime import (
    AttemptSpec,
    EnvironmentExecution,
    JsonlSubprocessWorker,
    run_attempt,
    run_stage,
)

__all__ = [
    "ActionEffectClass",
    "ActionEffectContract",
    "ActionExecutionLedger",
    "ActionPurpose",
    "ActionSpec",
    "AcquisitionProtocolMachine",
    "AttemptSpec",
    "BudgetPolicy",
    "BudgetState",
    "ControllerDecision",
    "ControllerDisposition",
    "ControllerState",
    "EvidenceRecord",
    "EvidenceSource",
    "ExecutionStatus",
    "EnvironmentExecution",
    "JsonlSubprocessWorker",
    "LedgerEntry",
    "ContinuationDecision",
    "ContinuationDisposition",
    "ExecutionProgressState",
    "ObservableProgressEvidence",
    "ProgressStatus",
    "SubgoalContract",
    "SubgoalStatus",
    "initial_controller_state",
    "controller_state_from_selection",
    "action_effect_contract_from_mapping",
    "execution_ledger_from_mapping",
    "observable_action_from_mapping",
    "observe_execution",
    "resolve_verification",
    "review_action_proposal",
    "review_invalid_decision",
    "stop_for_agent_decision",
    "stop_for_task_completion",
    "initial_progress_state",
    "progress_state_from_mapping",
    "route_observable_progress",
    "run_attempt",
    "run_stage",
]
