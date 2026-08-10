# PROPER paper 2026

本目录是 2026 年小论文工作的唯一入口。论文主线固定为：

> 基于可观察失败证据的保守式失败记忆选择，及其对工具型 LLM Agent
> 恢复有效性和错误记忆风险的影响。

当前不把 PROPER v2.3 execution ledger 作为论文主贡献。v2.3 可作为背景、局限或
未来工作引用，但不得把开发结果写成正式验证结论。

## 权威文件

- [`experiment_plan.md`](experiment_plan.md)：后续实验、顺序、完成标准、时间表和停止规则。
- [`protocol.md`](protocol.md)：当前协议草案和正式运行冻结条件。
- [`historical_reuse_audit.md`](historical_reuse_audit.md)：三类 Qwen 历史输出的逐条件复用审计。
- [`remote_execution_handoff.md`](remote_execution_handoff.md)：实验机盘点与回传步骤。
- [`remote_inventory_audit.md`](remote_inventory_audit.md)：实验机首轮盘点的审计结论与待决项。

后续每完成一个阶段，都应在实验计划的“状态总表”和“变更记录”中更新；除非记录
理由并提升计划版本，否则不得在看到正式模型结果后修改主要假设、主要总体、主要终点
或方法规则。

## 新工作目录

后续实现和产物应使用以下隔离路径：

- `configs/paper_2026/`
- `docs/paper_2026/`
- `experiments/paper_2026/`
- `outputs/paper_2026/`
- `schemas/paper_2026/`

## Current paper-method artifact

- `selector_design_v0_1.md`: shared selector interface, component-ablation contract, and verification
  status before the offline capacity audit.
- `statistics_design_v0_1.md`: frozen-candidate paired tests, confidence intervals, and multiplicity
  families defined before new formal outputs.
- `selector_capacity_audit_v0_1.md`: full 541-target model-free capacity result and selector-freeze
  decision.

The latest non-model preflight result is written to
`outputs/paper_2026/p0_capacity_audit_input_preflight.json`. It does not contain or generate model
outputs.

既有 `proper_v1`、`proper_v2` 和 `proper_v2_3` 文件属于历史或开发证据。新实验可以
按显式路径和 SHA-256 只读引用，但不得覆盖、移动或重新生成这些结果。
