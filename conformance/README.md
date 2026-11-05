# 一致性测试

本目录包含两类互补的测试：

| 测试 | 验证对象 | 不验证 |
|---|---|---|
| FSRS-3 黄金向量 | 参考策略 R1 的数值行为（稳定度、难度、间隔） | 每日计划、队列、生命周期、存储 |
| 业务一致性场景 | 引擎的业务规则（配额、同日重复、`extra`、`known`、`fill` 等） | FSRS-3 的具体数值 |

两者都使用语言无关的 JSON 数据；Python runner 只是参考执行器，不是规范本身。

## 运行

在仓库根目录执行：

```bash
python conformance/run_fsrs3_vectors.py
python conformance/business/run_business_scenarios.py
```

两个命令都无需第三方依赖；失败时返回非零退出码，可直接用于 CI。建议使用 Python 3.11 或更高版本。

## 目录

```text
conformance/
  fsrs3-vectors.json          FSRS-3 黄金向量（V1–V5）
  fsrs3_reference.py          FSRS-3 的最小 Python 参考实现
  run_fsrs3_vectors.py        向量 runner
  business/
    scenarios.json            业务场景（B01–B23）
    reference_engine.py       TP1 测试策略 + 最小业务引擎
    run_business_scenarios.py 场景 runner
```

## FSRS-3 向量约定

- 只传入**当天第一次计划内评分**；同日重复、今日回顾、历史回顾不得调用策略（POLICY-006b）。
- `policyIntervalDays` 是 FSRS-3 公式直接算出的间隔。
- `intervalDays` 是经过业务规则覆盖后的实际间隔：
  - 忘记固定 1 天（SCHED-004）；
  - 模糊默认截断到 3 天（SCHED-005 / `vagueMaxIntervalDays`）；
  - 认识使用公式间隔。
- `stabilityDays` / `difficulty` / `retrievability` 允许 `tolerance`（默认 `0.001`）的浮点误差；间隔和 `lapsesDelta` 必须精确相等。
- `lapsesDelta` 只在“计划内首次评分为忘记”时为 1；同日重复不增加。

## 业务场景约定

业务场景使用**测试策略 TP1**，不是 FSRS-3：

- 初始稳定度：认识 10 天，模糊 3 天，忘记 1 天。
- 复习稳定度：认识 ×2，模糊 ×1.2，忘记 = 1。
- 间隔 = 稳定度 half-up 取整，再 clamp 到 `[minIntervalDays, maxIntervalDays]`。
- 模糊额外受 `vagueMaxIntervalDays` 截断；忘记在 `forgotNextDay=true` 时固定次日。
- TP1 不读取目标保留率，因此业务场景不会因 FSRS 版本变化而改变。

`scenarios.json` 的每个 case 包含：

| 字段 | 含义 |
|---|---|
| `items` / `generate` | 初始条目；`generate` 用前缀 + 数量批量创建 |
| `config` | 覆盖 `defaults` 的配置 |
| `steps` | `rate`、`rate_many`、`plan`、`queue` |
| `expect` | 对条目、事件数、计划或队列的部分断言 |

`reference_engine.py` 只实现这些场景用到的规则，**不是生产实现**，也不覆盖 S01–S40 的全部场景。新增场景时，应同时扩展 runner 的 `op` 和本文件。

### 已覆盖的规范场景

| 业务测试 | 规范场景 | 规则重点 |
|---|---|---|
| B01–B04 | S01、S03、S05 | 新词首次评分、TP1 间隔、`forgotNextDay` |
| B05、B23 | S20、S26 | `extra` 更新状态但不占配额 |
| B06 | S27 | `known` 终止并覆盖当天调度 |
| B07–B10 | S10–S12 | 合并/分开模式的配额分配 |
| B11 | S19、S34 | 重算计划扣除当天已完成 |
| B12、B21 | S13、S14 | `fill` 与 `by_plan` 的区别 |
| B13 | S36 | `commandId` 幂等 |
| B14–B16 | S31、S32 | `sameDayGap` 的 `0`、`k`、`null` |
| B17–B18 | S04、S06 | 同日重复不改长期状态 |
| B19–B20 | S08、S09 | 历史回顾不改长期状态 |
| B22 | S15 | `known` 不进入计划 |

尚未覆盖的场景包括版本冲突（S37）、`forced_complete`（S33）、取消熟知（S28–S29）、删除重加与 `enrollmentEpoch`（S30）以及夏令时边界（S38–S39）。这些规则在规范中有定义，但参考 runner 还没有实现对应的执行器。

## 移植到其他语言

FSRS-3：

1. 读取 `fsrs3-vectors.json`；
2. 按文档 §7.4.1 实现 13 参数 FSRS-3；
3. 实现 §7.4 POLICY-006c 的到期日覆盖；
4. 用同一组 `expect` 做断言。

业务规则：

1. 读取 `business/scenarios.json`；
2. 实现 `rate` / `plan` / `queue` 三个测试入口，或把场景翻译成自己的测试框架；
3. 不使用 TP1 的生产实现也可以运行这些场景——TP1 只用于固定测试结果。

应用实现可以直接把两份 JSON 作为测试框架的 fixture，避免在业务代码里重复维护测试数据。
