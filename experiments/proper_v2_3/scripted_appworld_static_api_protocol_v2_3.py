"""Synthetic decision traces for the protected static-API protocol."""
TRACES=[
 {"id":"pure_transitive_query","evidence":["PURE_EXTERNAL_ALLOWLIST","NO_PERSISTENT_MUTATION"],"effect":"read_only","decision":"record"},
 {"id":"deterministic_replacement","evidence":["PERSISTENT_REPLACEMENT","RHS_ARGUMENT_OR_CONSTANT"],"effect":"idempotent_state_setting","decision":"record_preliminary"},
 {"id":"cardinality_append","evidence":["PERSISTENT_CARDINALITY_CHANGE"],"effect":"non_idempotent_side_effect","decision":"record_preliminary"},
 {"id":"unresolved_external","evidence":["UNRESOLVED_EXTERNAL_CALL"],"effect":"unknown_effect","decision":"block_full_capacity"},
 {"id":"transitive_helper_mutation","evidence":["TRANSITIVE_PERSISTENT_INCREMENT"],"effect":"non_idempotent_side_effect","decision":"record_preliminary"},
 {"id":"syntax_error","evidence":["AST_PARSE_ERROR"],"effect":None,"decision":"stop_and_preserve"},
 {"id":"plaintext_output_attempt","evidence":["PLAINTEXT_SYMBOL_OUTPUT"],"effect":None,"decision":"stop_privacy_boundary"},
 {"id":"forbidden_task_access","evidence":["TASK_OR_EVALUATOR_ACCESS"],"effect":None,"decision":"stop_protocol_boundary"}
]
def run_traces(): return TRACES
