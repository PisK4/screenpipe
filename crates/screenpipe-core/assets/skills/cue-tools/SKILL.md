---
name: cue-tools
description: Read before generating an intent card, querying or verifying the user's local data, calling an external service, or producing a deliverable — the tool division of labor, dedup discipline, draft convergence rules, and timezone conventions all live here.
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
| 信号未熟但值得追踪 | save_intent_draft（ripe_when 必填，草稿是期票不是拖延） |
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

## 2. 角色边界

角色定位由各会话的 system prompt 给出，这里只划能力组的边界：

- **意图卡生成**：主力用数据查证类 + 卡片交付类。材料够用不重复查询；出卡前必判重；存草稿必须给可判定的成熟条件，renew_count 已高的草稿要收敛而不是继续续写。
- **Chat**：全表可用；本地 API 直连细则见 screenpipe-api 技能。
- 共同禁区：写记忆库、写卡片状态、任何未经 connect 确认的外部副作用。
