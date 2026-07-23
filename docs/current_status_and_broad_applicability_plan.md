# PROPER 当前研究状态与广泛适用性实验方向

## 1. 本文档的用途

本文档记录截至 2026-07-23、Git 提交 `40217e1` 之后的项目状态，作为开展
第三、第四类 Agent 记忆场景实验之前的版本快照。

本文档只总结已经完成的实验和下一阶段研究边界，不改变任何既有预注册、
结果文件或结果锁，也不把未来目标表述成已经得到验证的结论。

## 2. 当前研究问题

本项目研究工具型 Agent 在执行失败后如何从候选经验中选择适用于当前状态的
恢复记忆。基础检索器使用 TF-IDF 召回 Top-10 经验；PROPER 的目标不是生成
新的记忆，而是在模型读取记忆之前，根据 Agent 当时能够观察到的信息判断
是否应保留 TF-IDF Rank-1，或改选更兼容的候选经验。

目前允许使用的输入包括：

- 任务文本和公开工具 schema；
- 失败的工具调用、参数、工具返回和调用历史；
- 候选经验的自然语言文本、原始 TF-IDF 排名和分数；
- 从上述公开内容中提取的工具、失败证据、恢复策略和修复目标。

`fault_plan`、`fault_type`、`recoverability`、`gold_summary`、环境适用性标签和
Recovery Validity 结果等 benchmark 隐藏信息禁止进入选择器或 Agent prompt。

## 3. 当前方法

PROPER 当前共享的技术框架包含以下步骤：

1. TF-IDF 从固定 memory bank 中检索 Top-10 候选经验；
2. 从当前失败状态提取可观察 failure signature；
3. 从候选文本及其公开来源记录中提取工具、失败证据、恢复 policy 和修复目标；
4. 根据 policy compatibility、repair-target agreement、failure-evidence
   agreement、tool compatibility 和 contradiction rules 评估候选；
5. 只在具有足够可观察依据时替换 Rank-1，否则保留原始 TF-IDF 结果；
6. 将实际选中的完整记忆写入 prompt，再以配对方式评价模型恢复行为。

需要明确的是，已经完成的两轮正式实验共享上述设计原则和特征来源，但还不是
同一个完全统一的场景无关决策器：

- 参数遗漏实验使用冻结的 L1 applicability intervention gate，再调用确定性
  Top-10 compatibility reranker；
- 瞬态授权实验使用单独预注册的保守规则：Rank-1 已是 retry 记忆时保持不变，
  否则优先选择同工具的 retry 记忆，再按原始 TF-IDF 排名选择。

因此，现有结果证明的是“可观察证据驱动的保守记忆选择原则”在两个场景中有效，
尚不能证明当前某一个冻结实现已经直接覆盖多种乃至所有 Agent 记忆场景。

## 4. 已完成的研究结果

### 4.1 原负迁移假设已停止

早期四条件开发实验在 104 个配对实例上比较 Inapplicable Memory 与 No
Memory。结果为 0 次 Recovery Validity 恶化、5 次改善，方向与原先
“不适用记忆导致更多负迁移”的假设相反。因此，该主线已停止；这些数据只作为
开发数据，不能重新定义指标后用于新的确认性结论。

这一结果促使项目从“证明不适用记忆普遍有害”转向“选择更适合当前失败状态的
记忆是否能稳定改善 Agent 恢复”。

### 4.2 参数遗漏场景

冻结的 Qwen3-8B public-test 实验在 115 个 gate-changed 配对实例上得到：

| 指标 | TF-IDF Rank-1 | PROPER |
|---|---:|---:|
| Recovery Validity | 99/115（86.09%） | 109/115（94.78%） |
| 配对改善 | — | 10 |
| 配对恶化 | — | 0 |

配对风险差为 **+8.70 个百分点**，95% CI 为
**[+3.52, +13.87]** 个百分点，exact two-sided McNemar
`p = 0.001953125`。没有观察到 Safety Violation 或新增重复无效调用。

该结果的局限是：10 次改善全部来自 `get_doc`，且全部使用同一条记忆。它证明
了参数遗漏条件下的有效性，但单独不能支持跨工具、跨记忆或通用性主张。

### 4.3 瞬态授权场景

冻结的 Qwen3-8B 实验包含 175 个 released transient-authorization
目标，预注册的 primary population 是选择器在模型运行前改变 Rank-1 的
53 个实例：

| 指标 | TF-IDF Rank-1 | PROPER |
|---|---:|---:|
| Recovery Validity | 34/53（64.15%） | 49/53（92.45%） |
| 配对改善 | — | 15 |
| 配对恶化 | — | 0 |

配对风险差为 **+28.30 个百分点**，95% CI 为
**[+16.06, +40.55]** 个百分点，exact two-sided McNemar
`p = 0.00006103515625`。

在全部 175 个目标上的描述性结果为 144/175 提升到 159/175，即
**+8.57 个百分点**。两种条件均无模型输出解析失败、Safety Violation 或
重复无效调用。15 次改善覆盖 5 个目标工具和 7 条不同记忆，最大单条记忆只
贡献 5/15 次改善。

该实验缓解了第一轮结果集中于单一工具和单一记忆的问题，但仍只涉及一个模型、
一个 benchmark、一个 released transient condition 和一步恢复。

## 5. 当前可以与不可以声称的结论

当前可以声称：

> 在 ToolMisuseBench 的参数遗漏和 released transient-authorization
> 两类可观察失败条件中，基于公开执行证据的保守记忆选择相对 TF-IDF Rank-1
> 提高了 Qwen3-8B 的 Recovery Validity，且两轮实验均未观察到配对恶化。

当前不可以声称：

- PROPER 已经适用于所有 Agent 记忆场景；
- 当前单一冻结选择器已经跨场景泛化；
- 结果已经跨模型、跨 benchmark 或跨 Agent 架构复现；
- PROPER 能从第一次拒绝中区分瞬态授权与持久授权；
- 现有 public-test 结果可以继续用于调参后再次充当确认性证据。

有限实验无法严格证明“所有可能的 Agent 记忆场景”。下一阶段合理目标是验证：

> 一个统一、仅依赖可观察证据的 PROPER 选择器，能否在多个具有代表性的
> Agent 记忆场景、模型和环境中稳定优于基础检索，并控制负迁移和安全风险。

## 6. 第三、第四类场景的下一阶段方向

第三、第四类场景必须在查看新模型输出之前完成容量审计、协议冻结和实现冻结。
不应为了得到正结果而复用已经消费的数据、降低筛选标准或按结果调整规则。

优先方向如下：

1. **第三类：瞬态 timeout 或其他可安全重试的执行失败。**
   当前开发审计中 timeout 有 92 个目标，但只有 7 个“Rank-1 不适用且
   Top-10 存在替代记忆”的冲突，容量不足。因此需要在未使用数据、扩展但预先
   冻结的 memory bank，或第二个 benchmark 中寻找足够的自然干预实例。
2. **第四类：与参数修复和 retry 不同的 Agent 恢复决策。**
   优先考虑工具选择/替代、fallback、验证后继续或多步计划修复等场景，用于
   检验同一套 failure evidence、policy compatibility、repair target、
   tool compatibility 和 contradiction 特征是否仍然有效。当前
   ToolMisuseBench schema-drift 开发数据的 Rank-1 已全部适用，没有有效
   重排序空间，因此不能强行用该子集制造确认实验。

持久授权拒绝不作为第三或第四类正向扩展。第一次 `authz_denied` 的公开状态
不能识别拒绝是否持久，而试探性重试持久拒绝违反当前安全契约。它应保留为方法
边界和负控制。

## 7. 统一 PROPER 的验证要求

下一阶段应先形成一个统一的场景无关接口，而不是继续增加互相独立的场景专用
选择器。统一版本至少应满足：

- 同一输入 schema 和同一组公开特征；
- 同一套 policy taxonomy、兼容性表示和冲突处理框架；
- 场景差异通过结构化可观察状态表达，而不是读取 benchmark 标签；
- 不确定时保留 Rank-1，并记录覆盖率；
- 在新模型结果生成前冻结规则、阈值、memory bank、Top-k、prompt、解码参数、
  评价器和排除清单；
- 保留 TF-IDF Rank-1、No Memory 以及可行时的 Applicable Oracle 控制；
- 主要终点保持为配对 Recovery Validity；
- 同时报告 PPT、PNT、配对风险差及置信区间、exact McNemar、
  Safety Violation、Repeated Invalid Calls、Recovery Cost 和选择覆盖率。

如果统一规则无法覆盖新场景，应如实报告覆盖边界；不能把多个事后编写的场景
规则简单组合后称为通用方法。

## 8. 数据隔离与结果保护

- 已完成的 104 个四条件实例属于 development 数据；
- 参数遗漏和瞬态授权正式实验的目标及模型输出均已消费，不得用于重新调参后
  再次形成确认性结论；
- 新场景必须创建新的 protocol、config、source lock、result schema、
  output directory 和 exclusion manifest；
- 既有 `outputs/confirmatory_gate_v1/`、
  `outputs/confirmatory_transient_authz_v1/` 以及对应 result lock 不得覆盖；
- public-test 输入曾参与 CPU 容量筛选的实验，只能表述为 model-output
  holdout，不能表述为完全 unseen-input holdout；
- 最终广泛适用性主张至少需要第二个 benchmark 和多个模型系列上的独立证据。

## 9. 当前版本结论

PROPER 已经从一个参数遗漏特例，发展为在两个不同可观察失败条件上均取得正向
Recovery Validity 结果的方法方向。瞬态授权实验还提供了跨工具、跨记忆的
效果分布证据，因此继续研究广泛 Agent 记忆适用性是合理的。

但当前最重要的未完成工作，是把两轮实验中的相关选择逻辑收敛为同一个统一、
可解释、仅使用可观察信息的 PROPER 接口，并在真正未消费的第三、第四类场景
上进行冻结后的独立验证。在这些验证完成前，论文主张应保持为“两类场景中的
有效性证据”，而不是“所有 Agent 记忆场景的通用方法”。

