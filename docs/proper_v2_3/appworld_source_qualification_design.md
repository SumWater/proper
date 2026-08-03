# AppWorld prospective source-qualification design

## Why this source

AppWorld is the first new source considered after the stopped tau3 acquisition
line. Its ACL 2024 paper reports 9 simulated day-to-day apps, 457 APIs, and 750
multi-step tasks. Unlike PlanBench-XL's qualified read-only executor, AppWorld
uses database-backed applications, records API calls, supports checkpoints,
and evaluates both intended state changes and collateral damage. These are
promising source properties, not accepted PROPER v2.3 target capacity.

Primary sources:

- paper: <https://aclanthology.org/2024.acl-long.850/>;
- official repository: <https://github.com/StonyBrookNLP/appworld>;
- project site: <https://appworld.dev/>.

## Boundaries before acquisition

No AppWorld repository, package, task instruction, API inventory, ground truth,
model output, or evaluator output was read locally in this stage. The source
revision, code version, data version, and manifest are therefore unset, and
the candidate count remains unknown.

The public repository is Apache-2.0, while task/app/API-specific protected
material has an additional encrypted-public-redistribution requirement. A
future offline handoff must retain that encryption boundary; extracted
protected files must not be copied through this repository or a plain folder.

The repository currently contains no prior AppWorld experimental artifacts, so
a future hash-audited source may be called project-unconsumed. Foundation-model
pretraining exposure is unknown, however, so it cannot be called model-unseen,
held-out, or confirmatory at this point.

## Execution-aware qualification requirements

AppWorld normally permits arbitrary code containing several API calls. That
unit is too coarse for the complete ActionExecutionLedger: a state-changing or
non-idempotent call could occur inside code before the controller sees it.
Qualification therefore requires a restricted interface where one named API
call equals one proposed ledger event. Every proposal is classified and
recorded before execution; every result and relevant database checkpoint is
recorded afterward. Unknown effects stop closed.

Ground truth, required apps/APIs, validation solutions, evaluator code,
benchmark labels, difficulty metadata, and semantic-family information are
audit-only and never method inputs. Success evidence used by the method must
come from public API results or observable state queries.

The future transport also separates a user message from an agent action. A
plain public user message does not need a JSON wrapper; agent tool decisions
remain closed-schema objects. This prospective correction applies only to a
new source and does not authorize repair or rerun of the stopped tau3 cohort.
Invalid decisions and all their token usage must still be preserved and
counted.

## Current decision

The CPU-only design validator may pass while the scientific capacity remains
unknown. The only next gate is design of an offline, encrypted source
acquisition and static-inventory protocol. Download, decryption, task play,
model loading, GPU use, target selection, model comparison, and confirmatory
claims remain unauthorized.
