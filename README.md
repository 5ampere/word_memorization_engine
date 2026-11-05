# RPE · 复习规划引擎

一个与平台、应用形态和具体编程语言解耦的**背单词复习规划规范**。它描述“什么时候复习、今天学多少、先学什么、同一个词今天出现几次”，不绑定任何 UI、数据库或算法实现。

> 当前版本：**v0.3 Developer Preview**（`rpe-spec-0.3`）。可以作为实现基线，但尚未宣称 1.0 兼容。

## 这个项目解决什么

多数开源 SRS 只回答一个问题：**这个单词下次哪天复习？**

背单词产品还需要回答第二个问题：**今天应该学哪些词、各学多少、按什么顺序学？**

RPE 把两者拆成两层：

| 层 | 职责 | 可替换性 |
|---|---|---|
| 长期调度层 | 评分后的记忆状态、下次到期日 | 策略可替换；参考策略为 FSRS-3 |
| 每日计划层 | 复习/新学配额、排序、同日队列、完成判定 | 业务规则固定；不依赖具体算法 |

规范的核心不是某套公式，而是这些稳定规则：

- 只有**计划内、当天第一次**的评分才更新长期记忆状态。
- 每日学习量是**复习量 + 新学量**的总量；复习优先，新学补位。
- 忘记默认次日到期；模糊的间隔受 `vagueMaxIntervalDays` 截断。
- 熟知是终止生命周期，不等于 FSRS 的 Easy。
- 同一天重复只影响队列，不更新长期状态。
- 日志不可变；更正只能追加事件；相同日志重放必须得到相同状态。

完整规则见 [v0.3 业务描述](docs/01-复习规划引擎-业务描述-v0.3.md)。

## 5 分钟 Quick Start

### 1. 读规范

按这个顺序读最省时间：

1. [§0 一页摘要](docs/01-复习规划引擎-业务描述-v0.3.md#0-一页摘要)
2. [§3 领域模型](docs/01-复习规划引擎-业务描述-v0.3.md#3-领域模型)
3. [§4 长期调度](docs/01-复习规划引擎-业务描述-v0.3.md#4-长期调度一个单词下一次哪天出现)
4. [§5 每日计划](docs/01-复习规划引擎-业务描述-v0.3.md#5-每日计划今天学什么学多少什么顺序)
5. [§7.0 引擎门面](docs/01-复习规划引擎-业务描述-v0.3.md#70-引擎门面命令与查询)

第 3–11 章是规范性内容；第 1 章、附录 A/C 是说明性内容；附录 B 是速查。

### 2. 跑一致性测试

```bash
python conformance/run_fsrs3_vectors.py
python conformance/business/run_business_scenarios.py
```

预期结果：

```text
OK: 5 vectors passed
23/23 scenarios passed
```

两个 runner 都不依赖第三方库。FSRS-3 向量验证参考策略的数值；业务场景验证配额、同日重复、`known`、`extra`、`fill` 等引擎规则。

### 3. 看机器可读契约

```text
schemas/v0.3/
  item-state.schema.json
  study-event.schema.json
  engine-config.schema.json
  daily-plan.schema.json
  export.schema.json
```

Schema 使用 JSON Schema Draft 2020-12，默认 `additionalProperties: false`。说明见 [schemas/README.md](schemas/README.md)。

可选：校验 Schema 与示例（需要 `jsonschema`）：

```bash
python -m pip install "jsonschema==4.23.0"
python schemas/validate_examples.py
```

## 目录结构

```text
docs/
  01-复习规划引擎-业务描述-v0.3.md   当前规范
  01-复习规划引擎-业务描述-v0.2.md   历史基线
schemas/v0.3/                        JSON Schema 数据契约
conformance/
  fsrs3-vectors.json                 FSRS-3 黄金向量（V1–V5）
  fsrs3_reference.py                 FSRS-3 最小 Python 参考实现
  run_fsrs3_vectors.py               向量 runner
  business/
    scenarios.json                   业务场景（B01–B23）
    reference_engine.py              TP1 测试策略 + 最小业务引擎
    run_business_scenarios.py        场景 runner
```

## 规范状态与版本

| 版本轴 | 当前值 | 作用 |
|---|---|---|
| `specVersion` | `rpe-spec-0.3` | 业务规则与接口契约 |
| `schemaVersion` | `3` | 数据实体与导入/导出格式 |
| `policyVersion` | 由实现声明，例如 `fsrs-3@3.0` | 算法行为与参数 |

规范采用语义化版本：破坏兼容的规则变更升 major；新增可选能力升 minor；澄清或修正测试升 patch。

## 一致性等级

| 等级 | 含义 | 测试 |
|---|---|---|
| `core` | 生命周期、当日首次、事件、同日队列、幂等 | B01–B06、B13–B20、B22 |
| `planner` | `core` + 每日计划、配额、`fill`、剩余容量 | B07–B12、B21、B23 |
| `fsrs3` | 参考策略 R1 的数值一致 | V1–V5 |

等级是累加的；`fsrs3` 与 `planner` 是两条独立的轴。声明必须给出 `specVersion`、测试数据哈希、运行日期和实现版本，不能只写“兼容 RPE”。详见规范 §11.1。

## 实现方最小检查清单

- [ ] `lifecycle` 与 `phase` 分离；`known` 不是 `phase`
- [ ] 当日首次评分才更新长期状态；同日重复只写事件
- [ ] `scheduled` / `extra` 更新状态；`history_review` 等不更新
- [ ] 每日计划先复习后新学；重算时扣除当天已完成
- [ ] 忘记默认次日；模糊受 `vagueMaxIntervalDays` 截断
- [ ] `markKnown` 可覆盖当天调度并保存 `knownSnapshot`
- [ ] 删除后重加递增 `enrollmentEpoch`
- [ ] `commandId` 幂等；版本冲突不静默覆盖
- [ ] 日志只追加；更正写 `rating_corrected`
- [ ] 通过 `core` / `planner` 中声明的最低测试集

## 项目范围

本仓库只发布 **P1 复习规划引擎**：规范、数据契约和一致性测试。

P2 网页端案例是这套规范的一个非规范性实现，已从本仓库移出，将作为独立项目维护。P1 不直接提供“可运行代码”。业务规则的生命周期比技术栈长；规范、数据契约和可执行测试比某一份实现更耐迁移。

## 许可证与声明

- 代码与 Schema：[MIT](LICENSE)
- 规范文档：[CC BY 4.0](LICENSE-docs)
- 第三方许可与商标声明：[NOTICE](NOTICE)

本项目是独立开源项目，与“墨墨背单词”及其权利人没有官方关联。参考产品的名称与商标归其权利人所有。

## 参与贡献

欢迎补充业务场景、移植 runner、修正规则歧义。提交前请至少运行：

```bash
python conformance/run_fsrs3_vectors.py
python conformance/business/run_business_scenarios.py
```

新增或修改规范规则时，必须同步更新对应的 Schema 与一致性场景；文字、Schema、测试三者冲突时，以规范规则 ID 为准，并在同一个变更中修正另外两者。
