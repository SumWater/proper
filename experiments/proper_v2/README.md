# PROPER v2 experiments

This directory is reserved for unified PROPER v2 experiment entry points.
Historical PROPER v1 runners are preserved in `../proper_v1/`.

The ToolSandbox v2.1 model-pilot preparation and persistent Qwen JSONL worker
are deliberately separate: ToolSandbox orchestration runs in
`proper-toolsandbox`, while local model inference runs in
`failure-memory-pilot`.

The v2.2.1 continuation stage keeps preparation, scripted ToolSandbox
validation, prospective target inventory, and Qwen inference in separate
modules. `run_toolsandbox_continuation_stage_v2_2_1.py` is the single guarded
remote entry point; it writes result JSON only and does not create a duplicate
console log.
