# PROPER v2.3 tau3 source-qualification stage

## Decision

The pinned tau3-bench `v1.0.1` source qualifies for the next CPU-only,
scripted recoverable-branch screen. It does **not** yet provide a qualified
development, held-out, preservation, or confirmatory pair.

Current disposition: `continue_cpu_branch_screening`.

The stage does not authorize a model runner, GPU use, or a confirmatory claim.

## Why this source

The current ToolSandbox pool remains exhausted at 1,032 scenario names and
zero eligible new candidates. ToolMisuseBench has already supplied PROPER v1
memory sources and targets, so it is not a genuinely new source.

The official tau3-bench source exposes three relevant stateful domains:

- airline: public policy, task, split, and tool definitions;
- retail: public policy, task, split, and tool definitions;
- telecom: public policy, task, split, and dual-control tool definitions.

The upstream repository describes each domain using policies, tools, and task
sets, and publishes an MIT license. The source was acquired from
`https://github.com/sierra-research/tau2-bench.git` and pinned to tag `v1.0.1`,
commit `fc0055dc4e0a316c3f83133267fbd6faaa770992`.

## Read boundary

The audit reads only 13 explicitly listed and hashed inputs:

- task definitions;
- upstream split definitions;
- public policies;
- public agent-tool implementations.

It does not import tau3-bench, execute an environment, execute a target task,
load a model, or open bundled historical results or trajectories. The selected
input manifest excludes `data/tau2/results`, `data/simulations`, and
`historical_trajectories`.

Public evaluator action specifications are used only on the audit side as a
continuation-depth proxy. They, task descriptions, initial state, scenario or
family metadata, gold labels, evaluator outcomes, and model outputs are
forbidden from the PROPER method handoff.

## Static result

The eligible upstream base pools contain:

| Domain | Base tasks | Train | Test |
| --- | ---: | ---: | ---: |
| airline | 50 | 30 | 20 |
| retail | 114 | 74 | 40 |
| telecom | 114 | 74 | 40 |
| total | 278 | 178 | 100 |

The audit found 455 static positions where an assistant action has at least
two required actions after it:

| Public action-effect contract | Opportunities |
| --- | ---: |
| read-only | 374 |
| idempotent state-setting | 19 |
| non-idempotent side effect | 62 |

These are action-sequence opportunities, not recoverable pairs. No native
recoverable branch has been claimed.

The upstream train portion is prospectively labelled development. The 100
upstream test tasks are deterministically divided into 54 prospective held-out
and 46 preservation inputs. The partition manifest SHA-256 is
`2f5e2177b6d0ed12d4965e51f35ffdc42bf3408f833ae3229c5b1e5a8ab5e244`.
Those labels reserve inputs; they do not make the inputs qualified targets.

## Next gate

The next stage must implement a CPU-only scripted branch screen that proves,
for each proposed pair:

1. a failure is observable from public tool output or public state;
2. the recovery action is supported by public policy and tool contracts;
3. success evidence is observable without evaluator outcome or hidden gold;
4. at least two necessary task steps remain after recovery;
5. the same generic failure-injection and verification interface works across
   domains;
6. non-idempotent outcome-unknown actions fail closed or verify before retry;
7. development, held-out, and preservation inputs remain immutable.

Before any pair can enter those partitions, the audit must also exclude
overlap with PROPER v1 memory-source families, the 12 model-exposed PROPER v2
families, and every task used to tune a v2.3 rule. These three exclusion audits
remain pending in this source-only stage.

Until that gate passes, `new_target_capacity_available=false` and all model-run
authorization flags remain false.

## Local entry point

```powershell
python experiments/proper_v2_3/validate_tau3_source_qualification_v2_3.py
```

The generated artifacts belong only under
`outputs/proper_v2_3/tau3_source_qualification/`.
