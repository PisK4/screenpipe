# T4 · save_intent_draft 机制裁决

Labels: wayfinder:task (HITL)
Blocked by: [01-质量标准草案](01-质量标准草案.md)
Claimed by: pis（走图会话，2026-08-25）

> 收敛语义已由质量标准票定调：草稿是未熟观察的期票，`insufficient_material` 是默认出口——本票裁的是数值与规则，不写代码（实现统一移交「统一实现落地」票）。

## Question

补全草稿机制的规则并裁决：

1. 硬顶：单项目活跃草稿上限几张？超顶时新草稿挤掉谁？
2. 废弃：超过多久没续写的草稿自动废弃？废弃是被删、标记还是静默退出注入？
3. 收敛线：renew_count 阈值与 ripe_when 判定是否维持现状；
4. 规则同时落在 wrapper 代码（硬护栏）与 cue-tools skill 文本（模型可读的理由）两处。

用户已给的输入：倾向宽松、以 10 为量级。

## Resolution

Status: Resolved（2026-08-25，用户逐项确认）

### 配额与生命周期数值

- **活跃草稿总量上限 10**（替换现状的 3）：超限依旧 409，回执引导先收敛或废弃再创建；每拍不设单独的创建次数限制，受总量约束。
- **TTL 维持 48h** 不变：到期由心跳结算为 expired，不删除行。过期语义维持「标记退出注入」，不是物理删除。
- renew_count 收敛线维持 ≥3 必须收敛的现状；ripe_when 判定要求维持必填。

### 可见性：瘦身 payload ＋ 新增只读详情工具

采用方案 A：

- **payload `[OPEN_DRAFTS]` 瘦身**：只注入最新 3 条活跃草稿（按 updated_at 倒序），每条三个字段 `{draft_id, gist, ripe_when}`；节首加计数头「3/10」式（已展示数/活跃总数）。active 总数大于展示数时，明示其余草稿可用 `get_intent_draft` 获取。
- **新增 `get_intent_draft(limit)` 只读工具**：返回活跃草稿完整详情（id、gist、evidence_so_far、ripe_when、renew_count、格式化时间），按 updated_at 倒序，limit 入参封顶。它是 agent 管理「未展示的那部分」草稿和续写前取回 evidence 上下文的唯一入口。
- **不新增 update 工具**：`save_intent_draft` 本就是 upsert（传 draft_id 即更新，renew_count+1，响应区分 saved/updated），一个语义不允许两个名字；description 措辞在流程文本票里再钉清。

### 时间戳投影

表结构不动（created_at/updated_at 已存在，unixepoch 秒）。改的是模型可见层：

- payload 与 `get_intent_draft` 返回里的时间一律格式化为本地绝对时间（与 `[CURRENT_TIME]` 同风格，如 `2026-08-25 14:30`），agent 对照窗口头部时间即可判断草稿陈旧度，支撑收敛决策；
- `save_intent_draft` 成功回执顺带带回该草稿的更新时间。

### 规则落点

- wrapper 代码硬护栏（总量 409、TTL 结算、renew 阈值）与 cue-tools skill 文本（三分支出口、upsert 语义、时间戳读法、get_intent_draft 使用时机）两处同步——文本部分归完整生成流程文本票起草，写入动作随统一实现票落地。

### 明确不做

- 不做 update_intent_draft（upsert 已覆盖）；
- 不做草稿的物理删除与手动废弃入口（discarded 状态保留给模型经 save 流程显式声明，本轮无证据需要更多）。
