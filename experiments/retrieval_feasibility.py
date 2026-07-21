from __future__ import annotations

import dataclasses
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "external" / "toolmisusebench"))

from failure_memory.boundary import sanitize_observation_payload  # noqa: E402
from failure_memory.contracts import PolicyKind, RecoveryPolicy  # noqa: E402
from failure_memory.retrieval import (  # noqa: E402
    Experience,
    FailureQuery,
    SourceBlindTfidfRetriever,
    aggregate_funnel,
    measure_retrieval_funnel,
)
from toolmisusebench.baselines import build_agent  # noqa: E402
from toolmisusebench.dataset import load_tasks  # noqa: E402
from toolmisusebench.harness.runner import make_env_for_task  # noqa: E402
from toolmisusebench.types import Action, Task  # noqa: E402


SAMPLE = ROOT / "work" / "toolmisusebench_sample"
CONFIG = ROOT / "configs" / "retrieval_feasibility.json"
OUTPUT = ROOT / "outputs" / "retrieval_feasibility.json"
PER_CLASS = 24


RETRY_POLICY = RecoveryPolicy(PolicyKind.RETRY, {"max_attempts": 1})
REVISE_POLICY = RecoveryPolicy(
    PolicyKind.REVISE_ARGUMENTS,
    {
        "operation": "repeat_failed_operation",
        "fields": ["$error.missing"],
        "bindings": {"$error.missing": "$instruction.binding"},
    },
)
STOP_POLICY = RecoveryPolicy(
    PolicyKind.STOP_AND_REPORT,
    {"reason_code": "persistent_authorization_denial"},
)
POLICIES = (RETRY_POLICY, REVISE_POLICY, STOP_POLICY)


@dataclasses.dataclass
class PilotInstance:
    instance_id: str
    source_task_id: str
    provenance: str
    task: Task
    correct_action: Action
    failure_action: Action
    query_text: str
    recommended_policy: RecoveryPolicy
    applicability: dict[str, bool]
    released_condition: bool


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def policy_signature(policy: RecoveryPolicy) -> str:
    return canonical({"kind": policy.kind.value, "parameters": dict(policy.parameters)})


def initial_action(task: Task) -> Action | None:
    env = make_env_for_task(task)
    observation = env.reset(task)
    agent = build_agent("instruction_parser")
    agent.reset()
    return agent.act(observation)


def first_failure(task: Task, action: Action) -> tuple[Any, dict[str, Any]]:
    env = make_env_for_task(task)
    env.reset(task)
    result = env.step(action)
    sanitized = sanitize_observation_payload(env.observation().model_dump(mode="json"))
    return result, sanitized


def observed_fault_types(result: Any) -> set[str]:
    if result.error is not None:
        faults = result.error.details.get("faults", [])
    else:
        faults = (result.output or {}).get("faults", [])
    return {
        str(fault["fault_type"])
        for fault in faults
        if isinstance(fault, dict) and "fault_type" in fault
    }


def query_text(task: Task, action: Action, observation: dict[str, Any]) -> str:
    error = observation.get("last_error") or {}
    details = error.get("details") or {}
    detail_text = canonical(details) if details else "none"
    return (
        f"While trying to {task.instruction} the {action.tool_name} tool failed. "
        f"Error {error.get('code')}: {error.get('message')} Details: {detail_text}."
    )


def experience_text(instance: PilotInstance) -> str:
    if instance.recommended_policy.kind == PolicyKind.RETRY:
        recovery = "I retried the original tool call once and the task goal was satisfied."
    elif instance.recommended_policy.kind == PolicyKind.REVISE_ARGUMENTS:
        recovery = (
            "I corrected the missing arguments from the user instruction "
            "and the task goal was satisfied."
        )
    else:
        recovery = (
            "I stopped without another tool call and reported that "
            "authorization was persistently denied."
        )
    return f"{instance.query_text} {recovery}"


def task_success_after(task: Task, first_action: Action, recovery_action: Action) -> bool:
    env = make_env_for_task(task)
    env.reset(task)
    first = env.step(first_action)
    if first.error is None:
        return False
    second = env.step(recovery_action)
    return second.error is None and env.check_success().success


def evaluate_policy_applicability(instance: PilotInstance, policy: RecoveryPolicy) -> bool:
    if policy.kind == PolicyKind.STOP_AND_REPORT:
        return instance.provenance == "authorization_persistent_extension"
    if policy.kind == PolicyKind.RETRY:
        return task_success_after(instance.task, instance.failure_action, instance.failure_action)
    if policy.kind == PolicyKind.REVISE_ARGUMENTS:
        first, observation = first_failure(instance.task, instance.failure_action)
        error = observation.get("last_error") or {}
        missing = (error.get("details") or {}).get("missing")
        if first.error is None or not missing:
            return False
        return task_success_after(instance.task, instance.failure_action, instance.correct_action)
    raise AssertionError(f"unhandled policy: {policy.kind}")


def make_actual_instance(
    task: Task, provenance: str, recommended: RecoveryPolicy
) -> PilotInstance | None:
    action = initial_action(task)
    if action is None:
        return None
    first, observation = first_failure(task, action)
    expected_fault = task.fault_plan[0].fault_type
    if first.error is None or expected_fault not in observed_fault_types(first):
        return None
    instance = PilotInstance(
        instance_id=f"{task.task_id}::{provenance}",
        source_task_id=task.task_id,
        provenance=provenance,
        task=task,
        correct_action=action,
        failure_action=action,
        query_text=query_text(task, action, observation),
        recommended_policy=recommended,
        applicability={},
        released_condition=True,
    )
    instance.applicability = {
        policy_signature(policy): evaluate_policy_applicability(instance, policy)
        for policy in POLICIES
    }
    if not instance.applicability[policy_signature(recommended)]:
        return None
    return instance


def required_field_for(task: Task, action: Action) -> str | None:
    env = make_env_for_task(task)
    env.reset(task)
    schemas = env.registry.get_toolset(env.TOOLSET_ID)
    schema = next((item for item in schemas if item.get("name") == action.tool_name), None)
    if not isinstance(schema, dict):
        return None
    for field in schema.get("required", []):
        if field in action.args:
            return str(field)
    return None


def make_argument_omission_instance(task: Task) -> PilotInstance | None:
    correct = initial_action(task)
    if correct is None:
        return None
    field = required_field_for(task, correct)
    if field is None:
        return None
    invalid_args = dict(correct.args)
    invalid_args.pop(field)
    invalid = Action(tool_name=correct.tool_name, args=invalid_args)
    first, observation = first_failure(task, invalid)
    if first.error is None or first.error.code != "missing_required_arg":
        return None
    instance = PilotInstance(
        instance_id=f"{task.task_id}::argument_omission_extension",
        source_task_id=task.task_id,
        provenance="argument_omission_extension",
        task=task,
        correct_action=correct,
        failure_action=invalid,
        query_text=query_text(task, invalid, observation),
        recommended_policy=REVISE_POLICY,
        applicability={},
        released_condition=False,
    )
    instance.applicability = {
        policy_signature(policy): evaluate_policy_applicability(instance, policy)
        for policy in POLICIES
    }
    if not instance.applicability[policy_signature(REVISE_POLICY)]:
        return None
    return instance


def persistent_authz_task(task: Task) -> Task:
    payload = task.model_dump(mode="python")
    payload["task_id"] = f"{task.task_id}__persistent_authz_extension"
    payload["budget"]["max_steps"] = max(4, payload["budget"]["max_steps"])
    payload["budget"]["max_tool_calls"] = max(4, payload["budget"]["max_tool_calls"])
    payload["budget"]["max_retries"] = max(3, payload["budget"]["max_retries"])
    for fault in payload["fault_plan"]:
        if fault["fault_type"] == "authz":
            fault["trigger"].pop("on_nth_call", None)
            fault["payload"]["deny"] = True
            fault["payload"]["recoverability"] = "persistent_local_extension"
    return Task.model_validate(payload)


def make_persistent_authz_instance(task: Task) -> PilotInstance | None:
    extension = persistent_authz_task(task)
    action = initial_action(extension)
    if action is None:
        return None
    first, observation = first_failure(extension, action)
    if first.error is None or first.error.code != "authz_denied":
        return None
    env = make_env_for_task(extension)
    env.reset(extension)
    first_probe = env.step(action)
    second_probe = env.step(action)
    if (
        first_probe.error is None
        or second_probe.error is None
        or first_probe.error.code != "authz_denied"
        or second_probe.error.code != "authz_denied"
    ):
        return None
    instance = PilotInstance(
        instance_id=f"{task.task_id}::authorization_persistent_extension",
        source_task_id=task.task_id,
        provenance="authorization_persistent_extension",
        task=extension,
        correct_action=action,
        failure_action=action,
        query_text=query_text(extension, action, observation),
        recommended_policy=STOP_POLICY,
        applicability={},
        released_condition=False,
    )
    instance.applicability = {
        policy_signature(policy): evaluate_policy_applicability(instance, policy)
        for policy in POLICIES
    }
    return instance


def collect(
    instances: list[PilotInstance], candidates: list[Task], builder: Any, quota: int
) -> None:
    for task in candidates:
        if sum(item.provenance == builder.provenance for item in instances) >= quota:
            return
        instance = builder(task)
        if instance is not None:
            instances.append(instance)


def with_provenance(provenance: str, function: Any) -> Any:
    function.provenance = provenance
    return function


def build_instances(tasks: list[Task]) -> tuple[list[PilotInstance], dict[str, int]]:
    by_fault: dict[str, list[Task]] = defaultdict(list)
    for task in tasks:
        fault = task.fault_plan[0].fault_type if task.fault_plan else "clean"
        by_fault[fault].append(task)
    for values in by_fault.values():
        values.sort(key=lambda task: task.task_id)

    instances: list[PilotInstance] = []
    builders = [
        (
            by_fault["timeout"],
            with_provenance(
                "timeout_transient",
                lambda task: make_actual_instance(task, "timeout_transient", RETRY_POLICY),
            ),
        ),
        (
            by_fault["schema_drift"],
            with_provenance(
                "schema_backend_one_shot",
                lambda task: make_actual_instance(task, "schema_backend_one_shot", RETRY_POLICY),
            ),
        ),
        (
            by_fault["clean"],
            with_provenance("argument_omission_extension", make_argument_omission_instance),
        ),
        (
            by_fault["authz"][: len(by_fault["authz"]) // 2],
            with_provenance(
                "authorization_transient",
                lambda task: make_actual_instance(task, "authorization_transient", RETRY_POLICY),
            ),
        ),
        (
            by_fault["authz"][len(by_fault["authz"]) // 2 :],
            with_provenance(
                "authorization_persistent_extension",
                make_persistent_authz_instance,
            ),
        ),
    ]
    for candidates, builder in builders:
        collect(instances, candidates, builder, PER_CLASS)
    counts = Counter(instance.provenance for instance in instances)
    return instances, dict(sorted(counts.items()))


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    tasks = load_tasks(SAMPLE, "dev")
    instances, class_counts = build_instances(tasks)
    if any(class_counts.get(name, 0) < PER_CLASS for name in (
        "timeout_transient",
        "schema_backend_one_shot",
        "argument_omission_extension",
        "authorization_transient",
        "authorization_persistent_extension",
    )):
        raise RuntimeError(f"could not build balanced validated pilot: {class_counts}")

    experiences = [
        Experience(
            experience_id=f"experience::{instance.instance_id}",
            source_instance_id=instance.instance_id,
            natural_text=experience_text(instance),
            policy=instance.recommended_policy,
            provenance=instance.provenance,
        )
        for instance in instances
    ]
    retriever = SourceBlindTfidfRetriever(experiences)
    records = []
    confusion: Counter[str] = Counter()
    selected_policy_counts: Counter[str] = Counter()

    by_id = {experience.experience_id: experience for experience in experiences}
    instance_by_id = {instance.instance_id: instance for instance in instances}
    for instance in instances:
        query = FailureQuery(
            instance_id=instance.instance_id,
            natural_text=instance.query_text,
            provenance=instance.provenance,
        )
        candidates = retriever.retrieve(query, top_k=int(config["top_k"]))
        labels = {
            candidate.experience.experience_id: instance.applicability[
                policy_signature(candidate.experience.policy)
            ]
            for candidate in candidates
        }
        selected_id = candidates[0].experience.experience_id
        record = measure_retrieval_funnel(
            query=query,
            candidates=candidates,
            applicability=labels,
            exposed_experience_ids=[selected_id],
        )
        records.append(record)
        selected = by_id[selected_id]
        confusion[f"{instance.provenance} -> {selected.provenance}"] += 1
        selected_policy_counts[selected.policy.kind.value] += 1

    aggregate = aggregate_funnel(records)
    minimum_count = int(config["continue_if"]["selected_inapplicability_count_at_least"])
    minimum_rate = float(config["continue_if"]["selected_inapplicability_rate_at_least"])
    continue_pilot = (
        aggregate["query_count"] >= int(config["minimum_query_count"])
        and aggregate["selected_inapplicability_count"] >= minimum_count
        and aggregate["selected_inapplicability_rate"] >= minimum_rate
    )
    report = {
        "schema_version": 1,
        "retriever": config["retriever"],
        "query_and_experience_count": len(instances),
        "class_counts": class_counts,
        "released_condition_count": sum(instance.released_condition for instance in instances),
        "local_extension_count": sum(not instance.released_condition for instance in instances),
        "funnel": aggregate,
        "selected_policy_counts": dict(sorted(selected_policy_counts.items())),
        "provenance_confusion": dict(sorted(confusion.items())),
        "continue_to_agent_utilization_gate": continue_pilot,
        "not_measured": ["followed_inapplicability", "harmful_utilization"],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    result = "PASS_RETRIEVAL_FEASIBILITY" if continue_pilot else "STOP_RETRIEVAL_FEASIBILITY"
    print(f"RESULT={result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
