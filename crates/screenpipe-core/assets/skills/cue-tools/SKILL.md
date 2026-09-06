---
name: cue-tools
description: Read before generating an intent card, querying or verifying the user's local data, calling an external service, or producing a deliverable — the tool division of labor, dedup discipline, draft convergence rules, and timezone conventions all live here. Draft lifecycle (create/renew/fetch) rules live here too.
---

# Cue Tools 使用学说

> 本文件不承载契约。参数、响应字段以各工具 schema 为准；硬护栏（时间窗必填、结果截断、只读限制）焊在 wrapper 代码里，模型不可绕过。这里只讲单条工具 description 装不下的横向判断。

## 0. 分工地图

| 你要做的事 | 用哪件 |
| --- | --- |
| 查活动概貌 / 换时间窗复核 | get_activity_summary（材料已含则不必重调） |
| 查用户看过/说过什么的原文 | search_activity |
| 查偏好、历史决策、项目背景 | search_memories |
| 查会议细节（参会人、时段） | list_meetings |
| 判断同类卡是否发过 / 被拒过 | get_recent_intent_cards |
| 信号未熟但值得追踪，或续写已有草稿 | save_intent_draft（upsert：带 draft_id 即更新；ripe_when 必填） |
| 取回草稿详情（evidence、renew_count、时间） | get_intent_draft（payload 只展示最新 3 条，其余用它取） |
| 交意图卡（已熟） | submit_intent_card |
| 查公网信息（时事、公开产品） | sp_web_search（禁查本地数据） |
| 用外部 app 能力 | sp_mcp_list_tools → sp_mcp_call |
| 外部动作前确认连通性 | screenpipe_list_connections（未连则 screenpipe_connect_app） |
| 存面向用户的最终产出 | save_artifact |
| 看板查询 / 提案变更 | screenpipe_live_view / screenpipe_live_view_propose |

## 1. 通用纪律

- 本地优先于出网：能查本地数据就不要 web_search。
- 失败结果带状态码与原因：先修正参数重试一次，仍失败就放弃该路径并在产出里说明，不得把失败当成功。
- 空结果 ≠ 没有数据：先核对 data_status 或放宽时间窗，再下结论。
- 时间窗必带；`today` / `yesterday` 按用户本地时区解释，禁止自行换算 UTC 午夜。
- MCP 结果带 `isError: true` 是明确的失败信号，不得当成功继续。

## 2. 角色边界与生成流程

角色定位由各会话的 system prompt 给出，这里划能力组的边界，并给出意图卡会话的完整工作流。

### 意图卡生成流程

意图卡是「用户下一步最可能手动执行的任务」：步进级——项目内的一步、可命名的具体对象、可启动的动作；48h 内可执行，证据必须来自当前材料窗口。

流程五步：

1. 读材料。[ACTIVITY_SUMMARY]、[RECENT_CARDS]、[OPEN_DRAFTS] 先过一遍；结果为空先核对 data_status 或放宽时间窗，再下结论。
2. 找候选。从行为里找「用户卡在哪、接下来顺手该做什么」；[OPEN_DRAFTS] 里有活跃草稿时优先续写对应 draft_id，不开平行线。
3. 过门槛。四条全满足才允许考虑交卡：
   - 具体对象：能指名到 app/文档/人/项目；
   - 强度信号：时长或切换次数达标；
   - 自然下一步：说得出接下来的一步；
   - 问题陈述：填得出「用户当前的摩擦是 __，这张卡帮他解决 __」。
4. 自检。用户此刻看到这张卡，第一反应是「正要弄这个」还是「别烦我」？后者按材料不足处理。
5. 走出口。三分支：
   - 熟了 → 判重后 submit_intent_card，一拍至多两张、意图互异；
   - 未熟但值得追踪 → save_intent_draft 存期票；
   - 都不是 → {"insufficient_material": true}。这是默认出口，出卡是例外。

### 草稿纪律

- save_intent_draft 是 upsert：带 draft_id 即更新（renew_count 加一），不带则新建；ripe_when 必填，写可判定的成熟条件。
- [OPEN_DRAFTS] 是对象：active_total 是活跃草稿总量，shown 至多列最新 3 条；不在 shown 里的草稿，以及续写所需的 evidence_so_far，用 get_intent_draft(limit) 取回。
- 时间戳是本地绝对时间，对照 [CURRENT_TIME] 判断陈旧度；两天没动静的草稿优先收敛。
- 收敛线：renew_count 达到 3 或 ripe_when 已满足的草稿必须收敛——升级交卡或判定不再值得追踪，不允许无限续写。

### Chat

全表可用；本地 API 直连细则见 screenpipe-api 技能。

共同禁区：写记忆库、写卡片状态、任何未经 connect 确认的外部副作用。
