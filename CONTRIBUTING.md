# 参与贡献

## 可以贡献什么

- 指出规范中的歧义、冲突或不可判定的行为。
- 补充业务一致性场景（`conformance/business/scenarios.json`）或移植 runner。
- 修正 Schema 与规范不一致的地方。
- 改进文档结构、术语和示例。
- 报告参考策略的数值错误。

## 修改规范的流程

1. **先定位规则 ID**。每条规范规则都有形如 `SCH-001`、`PLAN-015` 的编号；讨论时引用编号，而不是只引用段落。
2. **说明行为变化**。写清楚旧行为、新行为、受影响的实现和迁移方式。
3. **同步三件套**：
   - 规范文字；
   - `schemas/v0.3/` 中对应的 JSON Schema；
   - `conformance/` 中对应的场景或向量。
4. **运行测试**：

   ```bash
   python conformance/run_fsrs3_vectors.py
   python conformance/business/run_business_scenarios.py
   ```

5. **更新版本记录**。规则变化写入规范 §13；破坏兼容的变更必须升级 `specVersion` 的 major。

## 新增业务场景

`conformance/business/scenarios.json` 的 case 由 `items` / `generate`、`config`、`steps`、`expect` 组成。可用的 `op` 是：

- `rate`：单个评分；
- `rate_many`：按前缀批量评分；
- `plan`：生成计划；
- `queue`：计算同日重新入队后的队列。

如果新场景需要 runner 尚未实现的规则：

1. 先在 `reference_engine.py` 中实现最小逻辑；
2. 在 `scenarios.json` 中加 case；
3. 在 `conformance/README.md` 的覆盖表中登记；
4. 确认旧场景不回归。

参考 runner 是测试工具，不是生产实现；不要为了让它“通过”而把规范规则改弱。

## 提交信息

建议格式：

```text
spec: clarify sameDayGap=0 / null distinction
test: add B24 for forced_complete
schema: require wasNew on study_rated
```

## 许可

提交即表示你同意以 MIT（代码、Schema、runner）和 CC BY 4.0（规范文档）许可贡献内容。详见 `LICENSE` 与 `LICENSE-docs`。
