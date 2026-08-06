"""Conservative, hash-only static API inventory for protected Python sources."""

from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping


class StaticApiInventoryError(ValueError):
    """Raised when the complete protected-source registry cannot be built."""


PURE_CALLS = {
    "abs", "all", "any", "bool", "dict", "enumerate", "float", "int",
    "isinstance", "len", "list", "max", "min", "range", "round", "set",
    "sorted", "str", "sum", "tuple", "zip",
}
PURE_METHODS = {
    "copy", "endswith", "get", "items", "keys", "lower", "replace",
    "split", "startswith", "strip", "upper", "values",
}
CARDINALITY_METHODS = {
    "add", "append", "clear", "discard", "extend", "insert", "pop", "remove",
}
IRREVERSIBLE_METHODS = {"commit", "delete", "emit", "publish", "send"}


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _root_name(node: ast.AST) -> str | None:
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _persistent_target(node: ast.AST) -> bool:
    return isinstance(node, (ast.Attribute, ast.Subscript)) and _root_name(node) in {"self", "cls"}


def _deterministic_rhs(node: ast.AST, arguments: set[str]) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.Name):
        return node.id in arguments
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_deterministic_rhs(item, arguments) for item in node.elts)
    if isinstance(node, ast.Dict):
        return all(key is None or _deterministic_rhs(key, arguments) for key in node.keys) and all(_deterministic_rhs(value, arguments) for value in node.values)
    return False


def _call_name(node: ast.Call) -> tuple[str | None, str | None]:
    if isinstance(node.func, ast.Name):
        return None, node.func.id
    if isinstance(node.func, ast.Attribute):
        return _root_name(node.func.value), node.func.attr
    return None, None


@dataclass(frozen=True)
class FunctionInfo:
    path: str
    qualified_name: str
    node: ast.FunctionDef | ast.AsyncFunctionDef
    content_sha256: str


class _Evidence(ast.NodeVisitor):
    def __init__(self, arguments: set[str], local_names: set[str]) -> None:
        self.arguments = arguments
        self.local_names = local_names
        self.codes: set[str] = set()
        self.internal_calls: set[str] = set()

    def visit_Assign(self, node: ast.Assign) -> None:
        persistent = any(_persistent_target(target) for target in node.targets)
        if persistent:
            self.codes.add("PERSISTENT_REPLACEMENT" if _deterministic_rhs(node.value, self.arguments) else "PERSISTENT_REPLACEMENT_UNPROVEN_RHS")
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if _persistent_target(node.target):
            deterministic = node.value is not None and _deterministic_rhs(node.value, self.arguments)
            self.codes.add("PERSISTENT_REPLACEMENT" if deterministic else "PERSISTENT_REPLACEMENT_UNPROVEN_RHS")
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if _persistent_target(node.target):
            self.codes.add("PERSISTENT_CARDINALITY_CHANGE")
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete) -> None:
        if any(_persistent_target(target) for target in node.targets):
            self.codes.add("PERSISTENT_CARDINALITY_CHANGE")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        root, name = _call_name(node)
        if name is None:
            self.codes.add("UNRESOLVED_DYNAMIC_CALL")
        elif root in {"self", "cls"} and name in self.local_names:
            self.internal_calls.add(name)
        elif root is None and name in self.local_names:
            self.internal_calls.add(name)
        elif name in IRREVERSIBLE_METHODS or (name in CARDINALITY_METHODS and root in {"self", "cls"}):
            self.codes.add("PERSISTENT_CARDINALITY_OR_IRREVERSIBLE_CALL")
        elif name in CARDINALITY_METHODS:
            self.codes.add("UNRESOLVED_MUTATION_RECEIVER")
        elif (root is None and name in PURE_CALLS) or name in PURE_METHODS:
            self.codes.add("PURE_CALL_ALLOWLIST")
        else:
            self.codes.add("UNRESOLVED_EXTERNAL_CALL")
        self.generic_visit(node)


def _signature_shape(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
    args = node.args
    return {
        "positional_only": len(args.posonlyargs),
        "positional_or_keyword": len(args.args),
        "keyword_only": len(args.kwonlyargs),
        "has_vararg": args.vararg is not None,
        "has_kwarg": args.kwarg is not None,
        "default_count": len(args.defaults) + sum(item is not None for item in args.kw_defaults),
        "return_annotation": node.returns is not None,
        "async": isinstance(node, ast.AsyncFunctionDef),
    }


def _classify(codes: set[str]) -> tuple[str, str]:
    if {"UNRESOLVED_DYNAMIC_CALL", "UNRESOLVED_EXTERNAL_CALL", "UNRESOLVED_MUTATION_RECEIVER", "PERSISTENT_REPLACEMENT_UNPROVEN_RHS"} & codes:
        return "unknown_effect", "unknown_stop"
    if {"PERSISTENT_CARDINALITY_CHANGE", "PERSISTENT_CARDINALITY_OR_IRREVERSIBLE_CALL"} & codes:
        return "non_idempotent_side_effect", "unsafe"
    if "PERSISTENT_REPLACEMENT" in codes:
        return "idempotent_state_setting", "safe_same_arguments_after_verified_prior_outcome"
    return "read_only", "safe"


def inventory_static_api_sources(sources: Mapping[str, bytes]) -> dict[str, Any]:
    """Parse every Python/stub source and return no plaintext protected identifiers."""

    selected = sorted((path, content) for path, content in sources.items() if path.endswith((".py", ".pyi")))
    if not selected:
        raise StaticApiInventoryError("no Python or stub members")
    functions: list[FunctionInfo] = []
    for path, content in selected:
        try:
            text = content.decode("utf-8")
            tree = ast.parse(text, filename="<protected>", type_comments=True)
        except (UnicodeDecodeError, SyntaxError) as exc:
            raise StaticApiInventoryError("protected source parse failure") from exc
        digest = hashlib.sha256(content).hexdigest()
        for item in tree.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(FunctionInfo(path, item.name, item, digest))
            elif isinstance(item, ast.ClassDef):
                for child in item.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        functions.append(FunctionInfo(path, f"{item.name}.{child.name}", child, digest))
    by_short_name: dict[str, list[FunctionInfo]] = {}
    for info in functions:
        by_short_name.setdefault(info.qualified_name.rsplit(".", 1)[-1], []).append(info)
    direct: dict[str, _Evidence] = {}
    for info in functions:
        arguments = {arg.arg for arg in (*info.node.args.posonlyargs, *info.node.args.args, *info.node.args.kwonlyargs)}
        if info.node.args.vararg:
            arguments.add(info.node.args.vararg.arg)
        if info.node.args.kwarg:
            arguments.add(info.node.args.kwarg.arg)
        evidence = _Evidence(arguments, set(by_short_name))
        for statement in info.node.body:
            evidence.visit(statement)
        direct[info.qualified_name] = evidence

    def transitive_codes(info: FunctionInfo, active: set[str]) -> set[str]:
        if info.qualified_name in active:
            return {"UNRESOLVED_DYNAMIC_CALL"}
        active = {*active, info.qualified_name}
        result = set(direct[info.qualified_name].codes)
        for short_name in direct[info.qualified_name].internal_calls:
            targets = by_short_name.get(short_name, [])
            if len(targets) != 1:
                result.add("UNRESOLVED_EXTERNAL_CALL")
            else:
                result.add("TRANSITIVE_INTERNAL_CALL")
                result.update(transitive_codes(targets[0], active))
        return result

    records = []
    for info in functions:
        short_name = info.qualified_name.rsplit(".", 1)[-1]
        if short_name.startswith("_"):
            continue
        codes = transitive_codes(info, set())
        effect, retry = _classify(codes)
        identity = f"{info.path}\0{info.qualified_name}".encode("utf-8")
        records.append({
            "symbol_sha256": hashlib.sha256(identity).hexdigest(),
            "file_content_sha256": info.content_sha256,
            "signature_shape_sha256": canonical_sha256(_signature_shape(info.node)),
            "decorator_count": len(info.node.decorator_list),
            "effect_class": effect,
            "retry_safety": retry,
            "evidence_codes": sorted(codes or {"NO_PERSISTENT_MUTATION_OR_EXTERNAL_CALL"}),
        })
    records.sort(key=lambda item: item["symbol_sha256"])
    counts = Counter(item["effect_class"] for item in records)
    effect_counts = {key: counts.get(key, 0) for key in ("read_only", "idempotent_state_setting", "non_idempotent_side_effect", "unknown_effect")}
    return {
        "python_member_count": len(selected),
        "candidate_count": len(records),
        "effect_counts": effect_counts,
        "unknown_effect_count": effect_counts["unknown_effect"],
        "complete_registry": True,
        "full_effect_coverage": all(effect_counts[key] > 0 for key in ("read_only", "idempotent_state_setting", "non_idempotent_side_effect")) and effect_counts["unknown_effect"] == 0,
        "candidate_records": records,
        "candidate_manifest_sha256": canonical_sha256(records),
        "protected_plaintext_persisted": False,
        "module_imported": False,
    }
