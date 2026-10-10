from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "paper"

# Explicit P0--E5/V1 whitelist. Never replace this with a recursive outputs scan.
SOURCES = {
    "e1_analysis": (
        "outputs/paper_2026/e1_selection/analysis.json",
        "5c84d3aeda8de387e840ec289c08ea7626e2e66c7d9a112fdd6fd4dcd57d6d8b",
    ),
    "e2e3_tables": (
        "outputs/paper_2026/e2_e3_formal_analysis/tables.json",
        "b14119e7eee348c085cb6bcbefca9e8a2ab2db8c4e283265799680acc232bf35",
    ),
    "e4_diagnostics": (
        "outputs/paper_2026/e4_diagnostics/diagnostics.json",
        "b74f355fff9cef82c257fe7ef2d887017526e3093122dc0d2de555a5734991d4",
    ),
    "e5_concentration": (
        "outputs/paper_2026/e5_concentration/concentration.json",
        "782b7d8f257d01efa93d5b70e59b3d87f662b474e227649c8409c31db964b5a2",
    ),
    "v1_manifest": (
        "outputs/paper_2026/evaluator_blind_audit/manifest.json",
        "8bbea707aa71a9f897ef7ee0fef1251e0c6f65344d253d89c0e21c3b2c38c3d9",
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_sources() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payloads: dict[str, Any] = {}
    provenance = []
    for name, (relative, expected) in SOURCES.items():
        if "e6" in relative.lower() or "tau3" in relative.lower():
            raise RuntimeError(f"out-of-scope source in whitelist: {relative}")
        path = ROOT / relative
        observed = sha256(path)
        if observed != expected:
            raise RuntimeError(f"frozen source hash mismatch: {relative}: {observed}")
        payloads[name] = json.loads(path.read_text(encoding="utf-8"))
        provenance.append({"name": name, "path": relative, "sha256": observed})
    return payloads, provenance


def pct(value: float) -> str:
    return f"{100 * value:.1f}"


def model_label(value: str) -> str:
    return {"qwen3_8b": "Qwen3-8B", "mistral_7b_instruct_v0_3": "Mistral-7B-Instruct-v0.3"}[value]


def tex_escape(value: str) -> str:
    return value.replace("_", r"\_").replace("%", r"\%")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def table_main(rows: list[dict[str, Any]]) -> str:
    selected = [
        row for row in rows
        if row["population"] == "changed_target_union" and row["stratum"] == "all_strata"
    ]
    lines = [
        r"\begin{center}",
        r"\refstepcounter{table}\label{tab:main-results}",
        r"\textbf{Table \thetable:} Recovery Validity on the frozen changed-target union ($n=403$ per model). Counts are successes; percentages are in parentheses. Oracle is descriptive.\par\smallskip",
        r"\small",
        r"\begin{tabular}{llrr}",
        r"\toprule",
        r"Model & Condition & Success & Rate (\%) \\",
        r"\midrule",
    ]
    for model in ("qwen3_8b", "mistral_7b_instruct_v0_3"):
        for row in [item for item in selected if item["model_name"] == model]:
            lines.append(
                f"{model_label(model)} & {tex_escape(row['condition'])} & "
                f"{row['recovery_validity_count']}/{row['n']} & {pct(row['recovery_validity_rate'])} \\\\"
            )
        lines.append(r"\midrule")
    lines[-1] = r"\bottomrule"
    lines += [r"\end{tabular}", r"\end{center}"]
    return "\n".join(lines)


def table_primary_and_strata(rows: list[dict[str, Any]]) -> str:
    selected = [
        row for row in rows
        if row["family"] in {"primary_proper_vs_tfidf", "stratified_primary_exploratory"}
    ]
    lines = [
        r"\begin{center}",
        r"\refstepcounter{table}\label{tab:primary-effects}",
        r"\textbf{Table \thetable:} Paired PROPER--TF-IDF effects. The all-strata rows are the pre-frozen primary family; failure-stratum rows are exploratory. RD is the paired risk difference in percentage points.\par\smallskip",
        r"\small",
        r"\begin{tabular}{llrrrrrr}",
        r"\toprule",
        r"Model & Stratum & $n$ & TF-IDF & PROPER & $+/-$ & RD & 95\% CI \\",
        r"\midrule",
    ]
    order = {"all_strata": 0, "argument_omission": 1, "transient_authorization": 2, "timeout": 3}
    for row in sorted(selected, key=lambda item: (item["model_name"], order[item["stratum"]])):
        ci = row["paired_bootstrap_ci"]
        lines.append(
            f"{model_label(row['model_name'])} & {tex_escape(row['stratum'])} & {row['pair_count']} & "
            f"{row['baseline_successes']} & {row['treatment_successes']} & "
            f"{row['positive_discordant']}/{row['negative_discordant']} & "
            f"{100 * row['paired_risk_difference']:.1f} & "
            f"[{100 * ci['lower']:.1f}, {100 * ci['upper']:.1f}] \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{center}"]
    return "\n".join(lines)


def table_ablations(rows: list[dict[str, Any]]) -> str:
    selected = [row for row in rows if row["family"] == "core_ablations"]
    lines = [
        r"\begin{center}",
        r"\refstepcounter{table}\label{tab:ablations}",
        r"\textbf{Table \thetable:} Core ablations on the changed-target union. Positive RD favors full PROPER. Holm correction is within the pre-frozen ablation family.\par\smallskip",
        r"\small",
        r"\begin{tabular}{llrrr}",
        r"\toprule",
        r"Model & Removed component & $+/-$ & RD (pp) & Holm $p$ \\",
        r"\midrule",
    ]
    component = {"proper_no_gate": "gate", "proper_no_contradiction": "contradiction"}
    for row in sorted(selected, key=lambda item: (item["model_name"], item["baseline"])):
        lines.append(
            f"{model_label(row['model_name'])} & {component[row['baseline']]} & "
            f"{row['positive_discordant']}/{row['negative_discordant']} & "
            f"{100 * row['paired_risk_difference']:.1f} & {row['holm_adjusted_p']:.3g} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{center}"]
    return "\n".join(lines)


def table_risk(rows: list[dict[str, Any]]) -> str:
    selected = [
        row for row in rows
        if row["population"] == "changed_target_union"
        and row["stratum"] == "all_strata"
        and row["baseline"] == "no_memory"
        and row["treatment"] in {"tfidf", "proper"}
    ]
    lines = [
        r"\begin{center}",
        r"\refstepcounter{table}\label{tab:risk}",
        r"\textbf{Table \thetable:} Descriptive transfer relative to No Memory on the changed-target union.\par\smallskip",
        r"\small",
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        r"Model & Method & $+/-$ & RD (pp) & Repeat regress. & Parse regress. \\",
        r"\midrule",
    ]
    for row in selected:
        lines.append(
            f"{model_label(row['model_name'])} & {tex_escape(row['treatment'])} & "
            f"{row['positive_transfer']}/{row['negative_transfer']} & "
            f"{100 * row['paired_risk_difference']:.1f} & "
            f"{row['additional_repeated_invalid_call']} & {row['parse_failure_introduced']} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{center}"]
    return "\n".join(lines)


def table_concentration(payload: dict[str, Any]) -> str:
    summaries = [
        row for row in payload["concentration_summaries"]
        if row["comparison"] == "primary_proper_vs_tfidf"
        and row["group_type"] in {"failed_tool", "task_domain", "proper_selected_memory"}
    ]
    lines = [
        r"\begin{center}",
        r"\refstepcounter{table}\label{tab:concentration}",
        r"\textbf{Table \thetable:} Descriptive concentration and leave-one-group-out sensitivity. Min RD is the smallest paired effect after excluding one group; no selector is retrained.\par\smallskip",
        r"\small",
        r"\begin{tabular}{llrrr}",
        r"\toprule",
        r"Model & Grouping & Groups & Largest $+$ share & Min RD (pp) \\",
        r"\midrule",
    ]
    for row in summaries:
        lines.append(
            f"{model_label(row['model_name'])} & {tex_escape(row['group_type'])} & "
            f"{row['group_count']} & {100 * row['largest_positive_transfer_share']:.1f} & "
            f"{100 * row['leave_one_out_min_risk_difference']:.1f} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{center}"]
    return "\n".join(lines)


def main() -> None:
    data, provenance = load_sources()
    tables = data["e2e3_tables"]
    write(PAPER / "tables" / "main_results.tex", table_main(tables["descriptive_rows"]))
    write(PAPER / "tables" / "primary_effects.tex", table_primary_and_strata(tables["inference_rows"]))
    write(PAPER / "tables" / "ablations.tex", table_ablations(tables["inference_rows"]))
    write(PAPER / "tables" / "risk.tex", table_risk(data["e4_diagnostics"]["risk_rows"]))
    write(PAPER / "tables" / "concentration.tex", table_concentration(data["e5_concentration"]))
    manifest = {
        "schema_version": 1,
        "scope": "P0-E5 plus V1-preparation only; E6 and Tau3 excluded",
        "generator": {
            "path": "paper/scripts/generate_f1_artifacts.py",
            "sha256": sha256(Path(__file__)),
        },
        "sources": provenance,
    }
    write(PAPER / "generated" / "provenance_manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    print(json.dumps({"status": "ok", "sources": len(provenance), "tables": 5}, sort_keys=True))


if __name__ == "__main__":
    main()
