# PROPER v2.2.1 continuation/replan development protocol

## Status

This is a new versioned development contract created after inspecting the
frozen v2.2 Qwen development outputs. It extends, but does not modify, the
v2.2 lifecycle contract.

The 12 v2.1 pairs may be used for development and regression. They cannot
become confirmatory data for this extension. No held-out or general Agent
memory claim is authorized.

## Problem isolated by v2.2

The frozen v2.2 lifecycle consumed the recovery memory and removed it from the
prompt in all nine post-failure trajectories. Qwen nevertheless proposed the
completed prerequisite again in six trajectories. The v2.2 controller blocked
those proposals by terminating the trajectory.

Consequently, execution-level repetition was removed, but return to the
original task was not established.

## Unified continuation contract

The continuation layer accepts the same selected memory and lifecycle state
for both `pre_action` and `post_failure`. It contains no scenario or tool-family
branch.

After runtime success evidence consumes an action memory:

1. actionable memory content remains removed;
2. the exact successful action and its runtime evidence enter a non-actionable
   execution ledger;
3. ordinary task planning resumes;
4. an exact completed-action repeat is not executed;
5. the controller returns structured replan feedback instead of immediately
   stopping;
6. an allowed replanned decision continues the original trajectory;
7. the controller stops only when a safety rule or a replan budget is
   exhausted.

The ledger is execution state, not retrieved memory. It must not contain the
memory's natural-language lesson, ranking score, or other actionable recovery
instructions.

## Budgets and stopping

- completed-action repeat replans: 2;
- invalid-decision replans: 1;
- a third completed-action repeat stops with
  `repeat_replan_budget_exhausted`;
- a second invalid decision stops with
  `invalid_replan_budget_exhausted`;
- terminal lifecycle tool calls and active stop-policy tool calls stop
  immediately;
- a consumed repeat without verifiable completed-action evidence fails closed.

A model `stop` decision remains observable and is not silently rewritten into
a successful completion.

## Development comparison

The existing two-condition comparison confounds selector and lifecycle effects.
The versioned development runner must create identical branch starts for four
conditions:

1. `tfidf_persistent_memory`;
2. `proper_persistent_memory`;
3. `proper_lifecycle_prompt_only`;
4. `proper_lifecycle_replan_controller`.

For compatibility with the frozen v2.1 ToolSandbox executor, the first two
conditions retain the serialized keys `tfidf_rank1_memory` and
`proper_v2_1_memory`; their report labels are the explicit names above.

The persistent conditions inject their selected memory on every decision. The
prompt-only condition consumes and removes the PROPER memory but does not block
a later repeat. The controller condition uses the same lifecycle prompt and
adds bounded non-executing replans.

The four conditions isolate:

- selector: TF-IDF persistent versus PROPER persistent;
- lifecycle prompt: PROPER persistent versus PROPER lifecycle prompt-only;
- controller/replan: prompt-only versus lifecycle replan controller.

## Required endpoints

Results must report separately:

- selector first-decision alignment;
- lifecycle consumption and ordinary-planning handoff;
- proposed, executed, and blocked completed-action repeats;
- replan acceptance and budget exhaustion;
- final native task completion and partial similarity;
- minefields, tool exceptions, and controller interventions;
- model requests, accepted decisions, tool calls, prompt tokens, and
  completion tokens.

Reduced cost caused by early stopping must not be described as an efficiency
improvement without the associated final-completion result.

## Held-out boundary

Before a future confirmatory run, a new target inventory must be frozen without
model outputs. Eligible post-failure targets require a recoverable prerequisite
followed by at least two observable task steps. Targets must not be any of the
12 model-exposed pairs or direct variants of their exact source scenarios.

The two currently unconsumed remove-contact targets remain
preservation-only: the selectors choose the same stop policy and its specific
trigger does not match. They are not continuation-effect targets.

Any protocol change after seeing a new target's model output creates another
development version and disqualifies that target from confirmatory reuse.
