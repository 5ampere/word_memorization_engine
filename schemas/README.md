# JSON Schema

本目录是规范的数据契约，使用 **JSON Schema Draft 2020-12**。它定义结构、枚举、必填字段和部分跨字段条件，不替代规范中的业务不变量。

## 文件

| 文件 | 对应规范实体 | 说明 |
|---|---|---|
| `item-state.schema.json` | `ItemState` | 生命周期、阶段、记忆、调度、计数、熟知快照、`enrollmentEpoch` |
| `study-event.schema.json` | `StudyEvent` | 不可变事件；事件类型与关键载荷的条件校验 |
| `engine-config.schema.json` | `EngineConfig` | 扁平配置；分开模式与压力平衡的条件必填 |
| `daily-plan.schema.json` | `DailyPlan` | 计划目标、复习/新学列表、提前复习、已处理/已完成 |
| `export.schema.json` | 导入/导出包 | `state_only` 或 `state_and_logs`，含版本、配置、条目、日志、策略 |

`examples/` 下每个 Schema 有一份可通过校验的示例，可直接用于实现方的单元测试 fixture。

## 校验

快速校验所有 Schema 与示例：

```bash
python -m pip install "jsonschema==4.23.0"
python schemas/validate_examples.py
```

Python 内联示例（需要第三方包）：

```bash
python -m pip install jsonschema
python - <<'PY'
import json
from pathlib import Path
from jsonschema import Draft202012Validator

schema_dir = Path("schemas/v0.3")
schemas = {
    path.name: json.loads(path.read_text(encoding="utf-8"))
    for path in schema_dir.glob("*.schema.json")
}

# 单文件校验示例
data = json.loads(
    Path("schemas/v0.3/examples/item-state.json").read_text(encoding="utf-8")
)
Draft202012Validator(schemas["item-state.schema.json"]).validate(data)
print("OK")
PY
```

Node：

```bash
npx ajv-cli validate \
  --spec=draft2020 \
  -s schemas/v0.3/item-state.schema.json \
  -d schemas/v0.3/examples/item-state.json
```

`export.schema.json` 使用相对 `$ref` 引用同目录的其他 Schema；校验时保留目录结构，或把 `$id` 映射到同一基础 URI。

## 设计约定

- 所有对象默认 `additionalProperties: false`；未知字段必须显式拒绝，避免静默丢数据。
- `unselected` / `queued` / `deleted` 条目不得带 `memory` / `schedule`；`unselected` / `queued` 的计数必须为 0；`deleted` 还要清空 `knownAt` / `knownSnapshot` / `firstLearnedDay`。
- `known` 条目必须有 `knownAt` 与 `knownSnapshot`。
- `phase` 可为 `null`，且永远不是权威状态；判断计划归属必须用 `lifecycle` 与 `schedule.dueDay`。
- `study_rated` 必须有 `itemId`、非空 `context`、`rating` 和 `wasNew`；`marked_known` 必须有 `itemId` 和 `knownSnapshot`，且 `rating` 必须为 `null`。
- `item_deferred` 必须带 `deferredFrom` / `deferredTo`；`rating_corrected` 必须带 `targetEventId`。
- `volumeMode=split` 时必须提供 `dailyReviewQuota` 与 `dailyNewQuota`。
- `pressureBalance=spread_backlog` 时必须提供 `dailyMaxReview`。

## 不变量不在 Schema 里

以下规则由规范与一致性测试保证，Schema 无法表达或不应重复表达：

- 同一 Item 同一学习日最多一次长期状态更新。
- `dueDay` 与 `policyIntervalDays` 的业务覆盖关系。
- 计划容量、复习优先、`remainingCapacity` 的扣减。
- 事件重放后的状态哈希一致。
- 版本冲突、`commandId` 幂等与单写者约束。

文字、Schema、测试三者冲突时，以规范的规则 ID 为准，并在同一个变更中修正另外两者。

## 版本

Schema 目录按规范主版本分目录：`v0.3/` 对应 `specVersion = rpe-spec-0.3`、`schemaVersion = 3`。破坏兼容的字段变更升 `schemaVersion` 并新建目录；不得在原地改变字段语义。
