# PROPER 2026 小论文实验计划

- 计划版本：`0.2`
- 建立日期：`2026-08-09`
- 目标：两个月内完成实验、冻结结果并写出可投稿的英文论文
- 冲刺出口：AAMAS 2027 main track
- 降档出口：与主题匹配的 CCF-C 或 SCIE 期刊
- 计划状态：P0 已完成，E1 离线选择进行中

## 1. 论文范围

论文只回答一个核心问题：

> 当工具型 LLM Agent 执行失败后，使用当前可观察失败证据保守地判断候选记忆是否
> 适用，能否比直接采用相似度 Rank-1 更稳定地提高恢复有效性，并控制错误选择风险？

论文的主要方法是 PROPER v1 所代表的“可观察证据 + compatibility + contradiction +
conservative gate”选择原则。PROPER v2.3 execution ledger 不进入本文的主要贡献和
正式实验矩阵。

## 2. 研究问题

- **RQ1 Effectiveness**：PROPER 是否比 TF-IDF Rank-1 提高 Recovery Validity？
- **RQ2 Baselines**：PROPER 是否仍优于 Dense Retrieval 和 LLM Applicability Judge？
- **RQ3 Generalization**：效果能否跨模型家族、跨失败类型复现？
- **RQ4 Mechanism**：conservative gate 和 contradiction checking 分别贡献了什么？
- **RQ5 Risk**：PROPER 是否减少错误替换和可观察到的负迁移，同时保持合理覆盖率？
- **RQ6 Behavior**：记忆选择改变是否真正转化为恢复行为或最终任务结果改变？

RQ1 是主要问题；RQ2--RQ5 是必须完成的支持问题；RQ6 需要通过外部容量门后执行，
若容量不足则作为明确局限报告，不制造 held-out 数据。

## 3. 已完成且冻结的历史证据

以下结果只读引用，不得重新调参后仍称为原确认性结果。

| ID | 模型 | 失败类型 | 有效总体 | 主要总体 | 已有结果 | 状态 |
|---|---|---|---:|---:|---|---|
| H1 | Qwen3-8B | argument omission | 189 | 115 changed pairs | 99/115 -> 109/115，+8.70 pp，10/0 | 已完成/冻结 |
| H2 | Qwen3-8B | transient authz | 175 | 53 changed pairs | 34/53 -> 49/53，+28.30 pp，15/0 | 已完成/冻结 |
| H3 | Qwen3-8B | timeout | 177 | 32 changed pairs | 32/32 -> 32/32，0 pp，0/0 | 已完成/冻结 |

已知边界必须在论文中保留：

- argument-omission 的 10 次改善均来自 `get_doc` 和同一条记忆；
- timeout 中选择改变没有转化为行为指标改善；
- 早期 104 对样本中，“不适用记忆普遍有害”的原假设未得到支持：5 次改善、0 次恶化；
- 当前证据尚未跨模型家族复现。

## 4. 冻结前必须确定的设计

### P0. 协议和复用审计

在新增正式模型输出生成前完成：

1. 冻结论文标题工作版、RQ、主要假设、主要终点和分析总体；
2. 冻结三个失败层、memory bank、候选 Top-k、PROPER 规则和阈值；论文版 PROPER
   必须具有一个共享输入 schema 和统一决策接口，失败类型差异只能通过可观察状态和
   预先声明的 policy taxonomy 表达，不能按 benchmark 名称编写分支；
3. 选择一个不同于 Qwen 的 7B/8B 指令模型；优先选择当前环境已可稳定运行的
   Llama 或 Mistral 家族模型，不为追求型号新颖临时更换运行栈；
   已授权固定版本的 `Mistral-7B-Instruct-v0.3`；远端磁盘空间检查已通过，固定版本正在下载，等待文件清单回传；
4. 冻结 Dense Retrieval 模型、LLM Judge 模型与 judge prompt；
5. 审计历史 Qwen 输出的 prompt、config、model 和输入哈希。只有完全一致的条件才能
   复用；否则标记为历史证据并重新运行新矩阵；
6. 冻结生成参数、解析器、评价 rubric、排除规则、缓存规则和随机性策略；
7. 若生成温度非零，正式总体至少运行 3 个预先固定的 seeds；若使用确定性解码，运行
   1 次正式生成，并对分层抽取的 10% 样本做重复性检查；
8. 生成 `source.sha256`、`protocol.md`、`prompt_manifest.json` 和配置锁。

**完成判据**：以上文件存在、可解析，且在看到新增正式模型结果前提交到版本控制。

P0 当前进度：

- [x] 建立 paper_2026 协议草案；
- [x] 审计三类历史 Qwen 结果文件、模型身份和已有条件；
- [x] 验证 541 个历史记录的 prompt、输出、outcome 和 prompt hash 完整；
- [x] 建立实验机无推理环境盘点脚本与回传说明；
- [x] 登记实验机 Qwen3-8B 路径，待远端文件清单核验；
- [x] 在实验机运行首轮盘点并回传 `p0_remote_inventory.json`；
- [x] 核验 Qwen3-8B 的 15 个历史模型文件；
- [x] 回传 import、Conda、GPU process 和 BGE manifest 的第二轮诊断；
- [x] 冻结 BGE Dense encoder 的模型文件身份；
- [x] 探测现有 Conda 环境并选定 `failure-memory-pilot` 历史 GPU 运行栈；
- [x] 获得第二模型下载授权并通过远端存储门槛；
- [x] 捕获当前 `failure-memory-pilot` 完整 Conda/pip 环境锁；
- [x] 完成第二模型下载并生成、回传和锁定本地模型清单；
- [x] 完成 Mistral 单卡 BF16、chat template 和严格 JSON smoke；
- [x] 使用同一脚本完成 Qwen3-8B smoke 并冻结双模型运行身份；
- [x] 实现共享 paper-level PROPER 接口和两项单组件消融的开发版本；
- [x] 实现配对风险差、精确 McNemar、确定性 bootstrap CI 和预设 Holm 家族；
- [x] 完成 selector capacity 输入预检：189/175/177 个历史目标上下文和 100 条记忆均通过；
- [x] 同步并核验冻结的 dev/public-test 两个 JSONL 原始输入；
- [x] 在三个失败层运行无模型输出的 selector capacity audit 并冻结最终版本；
- [x] 完成 LLM Judge exact-prompt 远程 smoke 与结果锁；其设计、Dense encoder、双 agent 模型与运行栈已冻结；
- [x] 冻结共享 paper-level PROPER schema、taxonomy 和规则；
- [x] 生成 P0 配置锁与 source manifest；
- [x] 将协议提升为 `1.0-frozen`，授权 E1，仍不授权正式 agent 输出。

## 5. 必须执行的新增实验

### E1. 强基线选择实验

在 189 + 175 + 177 个有效样本上，先离线运行全部选择方法：

1. No Memory；
2. TF-IDF Rank-1；
3. Dense Retrieval Rank-1；
4. LLM Applicability Judge/Reranker；
5. PROPER；
6. Applicable Oracle，仅作为探索性上界。

先冻结所有非 oracle 记忆选择方法相对 TF-IDF 改变最终记忆身份的样本并集，形成
`selection_manifest.json`。并集由 Dense、LLM Judge、PROPER 及两个消融共同定义，
不能只选择 PROPER 发生改变的样本。No Memory 会平凡地改变所有注入条件，Oracle 又
读取 evaluator-only 标签，因此二者都不参与 changed-target union 的定义。

**主要行为总体**：冻结的 changed-target union。

**次要总体**：全部有效样本。对选择结果没有变化且 prompt 完全相同的实例使用
prompt hash 去重，不重复生成。

**完成判据**：三个失败层的每种方法都有选择覆盖率、选择变化数、冲突原因和可复现
manifest；正式行为运行前 union 已冻结。

### E2. 跨模型主效应实验

模型：

- Qwen3-8B；
- 一个冻结的非 Qwen 模型家族。

失败层：

- argument omission；
- transient authz；
- timeout。

条件：No Memory、TF-IDF、Dense、LLM Judge、PROPER、Oracle。Oracle 不参与主要优越性
检验，只报告可达上界。

主要终点：

- 配对二元 `Recovery Validity`。

次要终点：

- action/tool 是否改变；
- Safety Violation；
- Repeated Invalid Calls；
- 解析失败；
- token、延迟和模型请求数。

主要比较为 PROPER vs TF-IDF。PROPER vs Dense 和 PROPER vs LLM Judge 是校正后的关键
次要比较。No Memory 用于解释记忆本身的作用。

**完成判据**：2 模型 x 3 失败层的冻结总体均完成；失败、排除和重试都有机器可读记录，
不得只汇报正结果层。

### E3. 核心消融实验

仅运行两个预先指定的消融：

- `PROPER-no-gate`：移除保守 gate，在候选分数更高时直接替换；
- `PROPER-no-contradiction`：移除 contradiction checking，其余逻辑保持不变。

先完成全量离线选择；行为生成只需覆盖消融相对完整 PROPER 产生不同注入 prompt 的冻结
并集。若某消融没有改变任何选择，应如实报告“无行为容量”，不得另外寻找有利子集。

**完成判据**：可以分别回答 gate 与 contradiction 模块是否改变覆盖率、错误替换和
Recovery Validity。

### E4. 风险与负迁移实验

在所有有效样本上报告：

- 相对 No Memory 的改善、恶化和不变；
- 相对 TF-IDF 的改善、恶化和不变；
- 选择错误率或不适用记忆注入率；
- PROPER abstention rate；
- gate precision、recall 和 coverage；
- 按失败类型和模型分层的风险差。

论文不得把早期不成立的“错误记忆普遍有害”重新包装为假设。允许的主张是：

> 负迁移不是普遍现象；本实验检验保守选择是否降低可观察错误替换风险。

**完成判据**：正向收益与恶化风险同表报告；不存在只统计 PROPER 改善样本的后验总体。

### E5. 集中性、稳健性与统计分析

必须报告：

- 按模型、failure type、tool、memory 分组的效果；
- leave-one-tool-out；
- leave-one-memory-out；
- 最大单工具和最大单记忆对总改善的贡献比例；
- 配对风险差和 95% bootstrap CI；
- exact two-sided McNemar test；
- 对预先指定的关键次要比较做 Holm correction；
- 选择覆盖率与错误率的关系；
- timeout 的零结果和 selection-to-behavior gap。

**完成判据**：删除 `get_doc` 或最大贡献记忆后的结果已明确，论文结论按该结果收窄，
不以总体均值掩盖集中性。

本阶段已完成。正式矩阵、分层、工具/任务域/记忆集中性和 leave-one-group-out 数字均已
生成并由 `configs/paper_2026/e5_concentration_v1_0.result.lock.json` 冻结。

## 6. 条件执行的外部端到端实验

### E6. 外部容量审计与端到端验证

现有 12 个 ToolSandbox pairs 已被 v2.1--v2.2.1 开发阶段消费，永久属于
development-only；当前 ToolSandbox no-play inventory 也没有未消费合格目标。因此它们
不能被重新声明为 held-out 或 confirmatory 数据。

先做不调用模型的前瞻容量审计，候选优先级为：

1. 已有仓库能够合法获取且尚未暴露的外部 benchmark；
2. 当前已静态审计的 Tau3 来源中，与失败恢复记忆选择问题匹配的任务；
3. 若前两者均无容量，则停止外部确认性实验。

启动端到端模型实验需要同时满足：

- 至少 30 个彼此独立、未被现有开发结果消费的合格任务；
- 至少覆盖 3 类失败或恢复策略；
- 在查看模型输出前冻结任务、记忆、条件、终点和停止规则；
- 一周内能够完成适配和 runner validation，不挤占 E1--E5；
- 不使用 scenario name、gold action、recoverability 或 evaluator outcome 作为方法输入。

通过容量门后比较 No Memory、TF-IDF、LLM Judge 和 PROPER，报告：

- 最终任务成功率；
- 首个恢复动作正确率；
- 无效和重复工具调用；
- 非幂等副作用重复；
- 总工具调用、token、延迟；
- 选择改变是否转化为行为或最终结果改变。

若容量门失败：E6 状态记为 `stopped: insufficient unexposed capacity`，论文如实报告外部
端到端证据不足；不得生成新的有利样本、复用已消费 12 pairs 或把 scripted traces
写成 held-out 结果。

## 7. 评价可靠性

- 优先使用预先冻结、可执行的确定性 evaluator；
- evaluator 不得读取条件名称或方法身份；
- 对全部 discordant pairs 和分层抽取的至少 20% 非 discordant pairs 做盲审；
- 若有第二标注者，报告一致率和 Cohen's kappa；若只能单人复核，明确标记为限制；
- 评价规则一旦在正式输出前冻结，不得因观察到不利结果而修改；必要修复必须版本化，
  并对所有条件统一重算。

## 8. 运行与产物要求

每个正式阶段至少保存：

- `protocol.md`
- `config.yaml`
- `selection_manifest.json`
- `prompt_manifest.json`
- `results.json`
- `analysis.json`
- `exclusions.json`
- `source.sha256`
- `reproduction.md`

所有结果写入 `outputs/paper_2026/<stage_id>/`。不得写入或覆盖
`outputs/proper_v1/`、`outputs/proper_v2/` 或 `outputs/proper_v2_3/`。

缓存键至少包含：输入、完整 prompt、模型标识、模型权重哈希、解码配置和 runner 版本。

## 9. 状态总表

状态只允许：`pending`、`in_progress`、`completed`、`stopped`。

| 阶段 | 内容 | 优先级 | 当前状态 | 计划完成日期 |
|---|---|---|---|---|
| P0 | 协议冻结、模型选择、复用和哈希审计 | 必须 | completed | 2026-08-15 |
| E1 | Dense/LLM Judge/Oracle 选择与 union 冻结 | 必须 | completed | 2026-08-23 |
| E2 | 双模型、三失败层主效应 | 必须 | completed | 2026-09-06 |
| E3 | no-gate 与 no-contradiction 消融 | 必须 | completed | 2026-09-06 |
| E4 | 风险、负迁移和 gate diagnostics | 必须 | completed | 2026-09-10 |
| E5 | 分层、集中性和正式统计 | 必须 | completed | 2026-09-13 |
| V1 | 匿名评价盲审与一致性分析 | 必须 | in_progress | 2026-08-24 |
| E6 | 外部容量审计与条件式端到端验证 | 条件 | stopped | 2026-08-16 |
| F1 | 冻结结果、表格和图 | 必须 | in_progress | 2026-09-13 |
| W1 | 完整英文初稿 | 必须 | pending | 2026-09-20 |
| W2 | 内部修改和投稿包 | 必须 | pending | 2026-10-01 |
| S1 | AAMAS 投稿或记录降档决定 | 必须 | pending | 2026-10-08 |

## 10. 执行顺序

严格按以下顺序推进：

1. P0：协议与所有方法定义冻结；
2. E1：只做选择和容量计算，不先批量生成模型结果；
3. 第二模型与每个条件各做少量 smoke test；smoke 样本永久标为 development；
4. 冻结 changed-target union；
5. E2 和 E3 批量生成；
6. E4、E5 统一分析并冻结数字；
7. E6 与 E2/E3 并行的前提是容量门已通过且不会拖延必须阶段；
8. 2026-09-13 后不再按结果调方法，只修复影响所有条件的实现错误；
9. 用冻结结果写论文。

## 11. 停止和降级规则

- 到 2026-08-23 第二模型仍不能稳定运行：改用当前环境中已经可运行的另一模型，不继续
  调试新运行栈；
- 到 2026-09-06 计算尚未完成：优先删除 E6，其次删除 Oracle 行为生成；不得删除第二
  模型、timeout、Dense、LLM Judge 或两个核心消融；
- 外部容量不足：停止 E6，不制造数据；
- 某失败层结果为零或负：保留并报告，不删除该层；
- 第二模型不复现：收窄为模型相关结论，转投较保守出口；
- 效果在 leave-one-tool/memory-out 后消失：收窄为特定工具/记忆场景结论；
- 只有选择指标改善而行为和 Recovery Validity 不变：不得宣称提升了 Agent 恢复能力；
- 2026-09-13 冻结所有数字，不做结果驱动的阈值、规则或样本调整。

## 12. 投稿档位判据

### 可冲 AAMAS

- 两个模型家族均在至少两个失败层上呈方向一致的改善；
- PROPER 相对 TF-IDF 的主要比较成立，并在 Dense/LLM Judge 下仍有竞争力；
- 没有未解释的明显恶化或安全回归；
- 集中性分析后仍有可辩护的结论；
- 复现实验和限制完整。

### 更适合 CCF-C / SCIE

- 第二模型总体方向一致但效应弱，或 timeout 仍为零结果；
- 收益只在部分失败层稳定，但风险控制和消融证据完整；
- 结论已按工具、记忆和 benchmark 边界收窄。

### 尚不应投稿

- 只有原 Qwen 冻结结果，没有新模型或强基线；
- Dense/LLM Judge 已解释全部收益且 PROPER 没有风险、成本或可解释性优势；
- 结果主要依赖单工具/单记忆且没有诚实的受限结论；
- 数据划分、prompt、评价或排除规则无法复现。

## 13. 明确不做的工作

- 不把 v2.3 execution ledger 扩展为本文第二主贡献；
- 不加入第三个模型；
- 不新增第四、第五类失败；
- 不做大量 embedding sweep；
- 不从零建设大型 benchmark；
- 不覆盖历史冻结产物；
- 不在看到正式结果后重新定义主要总体或成功指标。

## 14. 下一步

P0--E5 已完成并由结果锁冻结。当前论文线并行推进 V1 和 F1；E6 已停止并移交独立分支：

1. 两位审查者分别填写冻结的 1,099-pair 匿名审查表；若只有一位，必须记录为限制；
2. 从 E2--E5 结果锁生成预览表图和 claim--evidence matrix；V1 完成后冻结终稿；
3. 当前论文仅把 Tau3 结果作为复现边界/限制记录，不作为效果证据；
4. 独立 E6 分支按 `docs/paper_2026/e6_separate_branch_handoff.md` 先修复基础设施，再审计
   54 个 prospective held-out 任务；
5. 只有至少 30 个任务、至少 3 类恢复策略的资格门通过后，E6 分支才允许冻结模型协议。

## 15. 变更记录

| 日期 | 版本 | 变更 | 原因 |
|---|---|---|---|
| 2026-08-09 | 0.1 | 建立后续实验、完成判据、时间表和停止规则 | 将两个月论文目标转为可执行计划 |
| 2026-08-09 | 0.2 | 增加统一 selector 要求、修正 changed-target union 定义并启动 P0 | 适配本机无模型、实验机统一运行的实际条件 |
| 2026-08-10 | 0.3 | 将 P0--E5 标记完成，下一步切换为 F1 表图与主张冻结 | 双模型正式结果、风险诊断和集中性复跑均已锁定 |
| 2026-08-10 | 0.4 | 增加 V1 盲审包并冻结 E6 当前容量门，启动 Tau3 CPU 资格审计 | 当前外部合格 held-out 容量为 0，禁止提前运行 GPU |
| 2026-08-16 | 0.5 | 冻结 Tau3 远端负 envelope 与 development-screen 结果；当前论文停止 E6，后续移交独立分支 | 12 个 development pairs 通过，但 held-out 为 0，且 envelope 有 9 项基础设施测试问题 |
