from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from failure_memory.intervention_gate import (  # noqa: E402
    applicability_intervention_label,
    extract_gate_features,
    ordered_top10,
    selected_applicability,
)


CONFIG = ROOT / "configs" / "applicability_intervention_gate.runtime.yaml"
LOCK = ROOT / "configs" / "applicability_intervention_gate.runtime.lock.json"
DEFAULT_OUTPUT = ROOT / "outputs" / "proper_gate" / "cross_validation.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def load_config() -> dict[str, Any]:
    payload = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if payload.get("status") != "refactored_runtime_after_completed_cross_validation":
        raise RuntimeError("intervention-gate runtime configuration has an invalid status")
    return payload


def verify_lock() -> dict[str, Any]:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    if lock.get("status") != "refactored_runtime_lock_after_completed_cross_validation":
        raise RuntimeError("intervention-gate runtime lock has an invalid status")
    for key in ("config", "feature_source", "evaluation_runner"):
        item = lock[key]
        if sha256_file(ROOT / item["path"]) != item["sha256"]:
            raise RuntimeError(f"locked gate file changed: {key}")
    return lock


def make_model(config: dict[str, Any]) -> LogisticRegression:
    model = config["model"]
    return LogisticRegression(
        penalty=str(model["penalty"]),
        solver=str(model["solver"]),
        C=float(model["C"]),
        class_weight=str(model["class_weight"]),
        max_iter=int(model["max_iter"]),
        random_state=int(model["random_state"]),
    )


def safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def run_cross_validation() -> dict[str, Any]:
    lock = verify_lock()
    config = load_config()
    manifest_path = ROOT / config["input"]["selection_manifest"]
    if sha256_file(manifest_path) != config["input"]["selection_manifest_sha256"]:
        raise RuntimeError("frozen v1 selection manifest changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = list(manifest["records"])
    if len(records) != int(config["input"]["target_count"]):
        raise RuntimeError("unexpected intervention-gate population")

    feature_rows = [extract_gate_features(record) for record in records]
    labels = np.asarray(
        [int(applicability_intervention_label(record)) for record in records],
        dtype=np.int64,
    )
    cv_config = config["cross_validation"]
    splitter = StratifiedKFold(
        n_splits=int(cv_config["folds"]),
        shuffle=bool(cv_config["shuffle"]),
        random_state=int(cv_config["random_state"]),
    )
    probabilities = np.full(len(records), np.nan, dtype=np.float64)
    fold_ids = np.full(len(records), -1, dtype=np.int64)
    fold_summaries = []
    for fold, (train_indices, test_indices) in enumerate(
        splitter.split(np.zeros(len(records)), labels), start=1
    ):
        vectorizer = DictVectorizer(sparse=True, sort=True)
        train_matrix = vectorizer.fit_transform(
            [feature_rows[index] for index in train_indices]
        )
        test_matrix = vectorizer.transform(
            [feature_rows[index] for index in test_indices]
        )
        model = make_model(config)
        model.fit(train_matrix, labels[train_indices])
        probabilities[test_indices] = model.predict_proba(test_matrix)[:, 1]
        fold_ids[test_indices] = fold
        fold_summaries.append(
            {
                "fold": fold,
                "train_count": len(train_indices),
                "test_count": len(test_indices),
                "test_positive_count": int(labels[test_indices].sum()),
                "feature_count": len(vectorizer.feature_names_),
            }
        )

    all_predicted_once = bool(
        np.isfinite(probabilities).all()
        and (fold_ids >= 1).all()
        and (fold_ids <= int(cv_config["folds"])).all()
    )
    threshold = float(config["model"]["decision_probability_at_least"])
    predictions = probabilities >= threshold
    true_positive = int(np.logical_and(predictions, labels == 1).sum())
    false_positive = int(np.logical_and(predictions, labels == 0).sum())
    false_negative = int(np.logical_and(~predictions, labels == 1).sum())
    true_negative = int(np.logical_and(~predictions, labels == 0).sum())
    recall = safe_rate(true_positive, true_positive + false_negative)
    precision = safe_rate(true_positive, true_positive + false_positive)

    evaluation_rows = []
    for index, record in enumerate(records):
        candidates = ordered_top10(record)
        baseline_id = str(candidates[0]["candidate"]["experience_id"])
        predicted_positive = bool(predictions[index])
        selected_id = (
            str(record["proper_selected_experience_id"])
            if predicted_positive
            else baseline_id
        )
        evaluation_rows.append(
            {
                "instance_id": record["instance_id"],
                "source_task_id": record["source_task_id"],
                "development_partition": record["development_partition"],
                "fold": int(fold_ids[index]),
                "oof_probability": float(probabilities[index]),
                "predicted_intervention": predicted_positive,
                "evaluator_only_intervention_label": bool(labels[index]),
                "baseline_experience_id": baseline_id,
                "selected_experience_id": selected_id,
                "selection_changed": selected_id != baseline_id,
                "evaluator_only_baseline_applicable": bool(
                    candidates[0]["evaluator_only_environment_applicable"]
                ),
                "evaluator_only_selected_applicable": selected_applicability(
                    record, selected_id
                ),
            }
        )

    rank1_applicable = [
        row for row in evaluation_rows if row["evaluator_only_baseline_applicable"]
    ]
    conflicts = [
        row for row in evaluation_rows if not row["evaluator_only_baseline_applicable"]
    ]
    exact_preserved = sum(not row["selection_changed"] for row in rank1_applicable)
    conflict_selected_applicable = sum(
        row["evaluator_only_selected_applicable"] for row in conflicts
    )
    preservation_rate = safe_rate(exact_preserved, len(rank1_applicable))
    conflict_rate = safe_rate(conflict_selected_applicable, len(conflicts))
    gate_config = config["go_no_go"]
    gate_results = {
        "rank1_applicable_exact_preservation": preservation_rate
        >= float(gate_config["rank1_applicable_exact_preservation_rate_at_least"]),
        "conflict_selected_applicable": conflict_rate
        >= float(
            gate_config[
                "rank1_inapplicable_conflict_selected_applicable_rate_at_least"
            ]
        ),
        "positive_label_recall": recall
        >= float(gate_config["positive_label_recall_at_least"]),
        "intervention_precision": precision
        >= float(gate_config["intervention_precision_at_least"]),
        "all_oof_predictions": all_predicted_once,
    }
    gate_pass = all(gate_results.values())

    final_model = None
    if gate_pass:
        vectorizer = DictVectorizer(sparse=True, sort=True)
        matrix = vectorizer.fit_transform(feature_rows)
        model = make_model(config)
        model.fit(matrix, labels)
        coefficients = [
            {"feature": feature, "coefficient": float(coefficient)}
            for feature, coefficient in zip(
                vectorizer.feature_names_, model.coef_[0], strict=True
            )
            if coefficient != 0.0
        ]
        final_model = {
            "feature_count": len(vectorizer.feature_names_),
            "nonzero_coefficient_count": len(coefficients),
            "intercept": float(model.intercept_[0]),
            "decision_probability_at_least": threshold,
            "nonzero_coefficients": coefficients,
            "model_payload_sha256": hashlib.sha256(
                canonical(
                    {
                        "feature_names": vectorizer.feature_names_,
                        "coefficients": [float(value) for value in model.coef_[0]],
                        "intercept": float(model.intercept_[0]),
                        "threshold": threshold,
                    }
                ).encode("utf-8")
            ).hexdigest(),
        }

    return {
        "schema_version": 1,
        "run_kind": "applicability_intervention_gate_cross_validation",
        "identities": {
            "config_sha256": lock["config"]["sha256"],
            "feature_source_sha256": lock["feature_source"]["sha256"],
            "evaluation_runner_sha256": lock["evaluation_runner"]["sha256"],
            "source_lock_sha256": sha256_file(LOCK),
            "selection_manifest_sha256": sha256_file(manifest_path),
        },
        "boundary": {
            "model_loaded": False,
            "model_outputs_read": False,
            "validation_model_outcomes_read": False,
            "evaluator_labels_excluded_from_features": True,
            "threshold_tuned_after_results": False,
            "exploratory_development_only": True,
        },
        "population": {
            "target_count": len(records),
            "positive_label_count": int(labels.sum()),
            "negative_label_count": int((labels == 0).sum()),
            "rank1_applicable_count": len(rank1_applicable),
            "rank1_inapplicable_conflict_count": len(conflicts),
        },
        "cross_validation": {
            "folds": fold_summaries,
            "decision_probability_at_least": threshold,
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "true_negative": true_negative,
            "recall": recall,
            "precision": precision,
            "all_targets_predicted_once": all_predicted_once,
        },
        "offline_selection": {
            "selection_changed_count": sum(row["selection_changed"] for row in evaluation_rows),
            "rank1_applicable_exact_preserved_count": exact_preserved,
            "rank1_applicable_exact_preservation_rate": preservation_rate,
            "conflict_selected_applicable_count": conflict_selected_applicable,
            "conflict_selected_applicable_rate": conflict_rate,
            "gate_results": gate_results,
            "gate_pass": gate_pass,
        },
        "final_model": final_model,
        "records": evaluation_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = run_cross_validation()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "population": payload["population"],
                "cross_validation": payload["cross_validation"],
                "offline_selection": payload["offline_selection"],
                "final_model_fitted": payload["final_model"] is not None,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    if payload["offline_selection"]["gate_pass"]:
        print("RESULT=PASS_APPLICABILITY_INTERVENTION_GATE")
        return 0
    print("RESULT=STOP_APPLICABILITY_INTERVENTION_GATE")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
