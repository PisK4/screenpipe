# Wayfinder 地图 · 意图卡片生成质量（教 Agent 出好卡）

Labels: wayfinder:map

## Destination

走到这张图的终点，「让 Intent card Agent 生成用户满意的意图卡片」这件事定稿并生效：质量标准成文、完整生成流程写进 system prompt 与 cue-tools skill、一拍多卡契约落地、save_intent_draft 机制补全，且 ATA 轨迹验证新指引下的出卡行为确有改善。本图携带执行：决策之外，流程文本与相关代码随图落地。

## Notes

- 领域：macOS Tauri 桌面应用（Cue 宿主，screenpipe 个人 fork `PisK4/screenpipe`，分支 `cue-branding`），自建项目纪律。上一张图《意图卡片落点》已全部走完，整体归档在 `archive/意图卡片落点/`，其决议（宿主形态 T3、落库契约 T4、软去重 T10 等）是本图的既有地基，冲突时需显式修订而非默默覆盖。
- **方向基调（用户定调）**：意图卡片是「用户下一步最可能手动执行的任务」。当前生成质量不满意，原始不满材料：**卡片太泛、没有具体依据**——用户只在前端看卡，所以依据缺失与文案不行可能是同一个问题。
- 质量标准的路线已裁决：**直觉草案先行**（先按用户不满定标准草案），改完用 ATA 轨迹验证效果；不先做历史轨迹失败分类。
- 一拍多卡**纳入本轮**，含引擎侧改造；外部 Agent 通过公开接口复用 skill 是**顺带兼容**（主场景仍是内置心跳会话，不为它加约束）。
- **决策先行，落地殿后（用户定调，2026-08-25）**：所有决策票走完之前不写生产代码；全部裁决齐备后由「统一实现」票一次性落地，避免同一批文件被反复改动。代码注释禁止引用票据编号等规划工件（见根 `AGENTS.md`）。
- 写任何用户可见文案或流程文档前调 `de-AI-writing`；改生产代码前调 `ponytail`；改 Tauri command 前调 `screenpipe-tauri`；验证阶段与一切轨迹观察用 `cue-agent-tuning`。
- 本图用本地 markdown 充当 tracker：`tickets/` 下每票一个文件；阻塞关系写在票内 `Blocked by` 行；认领 = 把 `Claimed by` 填上。开票顺序：先建票文件，再回填阻塞边。已完成地图归档于 `archive/`。

## Decisions so far

<!-- the index: one line per closed ticket, enough to judge relevance, then zoom the link for the detail the ticket holds -->

- [07-文案风格定稿](tickets/07-文案风格定稿.md)：正典语气＝贴心助手（第二人称、先接现状再给出路、温度来自复述得准），单档不做设置项；四条文案规则＋「工作建议型」唯一明令禁例；甲/丙弃用，理由入票。原型资产 `assets/t7-copy-style-proto.html`。
- [06-完整生成流程文本定稿](tickets/06-完整生成流程文本.md)：system prompt 全文（Intent card Agent＋强制读 cue-tools＋简版门槛＋宁可不出卡）；cue-tools §2 重写为流程正典（五步流程＋草稿纪律，含 get_intent_draft 时机）；[OPEN_DRAFTS] 改单标记 JSON（active_total/shown 四字段/本地时间），内联收敛指引撤出；FEATURE 合同修订要点六条。
- [04-save_intent_draft机制裁决](tickets/04-save_intent_draft机制裁决.md)：活跃草稿总量上限 10（替换 3）、TTL 48h 不变、renew≥3 收敛线不变；payload 瘦身为最新 3 条 × {draft_id, gist, ripe_when} ＋「n/10」计数头；新增只读 `get_intent_draft(limit)` 工具管其余草稿与取 evidence；不新增 update 工具（save 已是 upsert）；时间戳投影为本地绝对时间。
- [03-多卡契约裁决](tickets/03-多卡契约裁决.md)：多次调用形态（弃数组载荷）；单拍上限 2 张含草稿升级卡；同拍去重＝意图互异纪律＋宿主拦同批同名卡；`insufficient_material` 模型出口不变、落库状态按 draft 操作次数四分类；实现移交统一实现票。
- [01-质量标准草案](tickets/01-质量标准草案.md)：意图卡片＝步进级任务预告（48h 内可执行、证据来自当前窗口）；出卡门槛四要件（具体对象/强度信号/自然下一步/问题陈述）＋提交前自检问句；`insufficient_material` 为默认出口，宁缺毋滥，草稿是攒观察的期票；术语已落 `CONTEXT.md`。
- [05-api_hint注入评估](tickets/05-api_hint注入评估.md)：hint 直接写进 `build_system_prompt()` 文本内一行，对所有模型注入，只点名 cue-tools（screenpipe-api 对意图会话结构性不可达）；skill 索引 REPLACE 后仍可见已对 pi 0.84.1 复核。
- [02-一拍多卡契约调研](tickets/02-一拍多卡契约调研.md)：现状多次 `submit_intent_card` 被静默覆盖只留最后一张；推荐形态 (a) 同会话多次调用＋单拍上限，改 runner/session/instruct/intent-card.ts 四处，DB、引擎路由、前端全不动。

## Not yet specified

- 失败分类回归集：等验证票跑起来、按 ATA 分类积累若干拍后，可能需要把失败模式固化成回归对照集。
- 外部 agent 复用缺口：skill 定稿后若发现外部调用公开接口有缺口（鉴权、参数、文档），再毕业成票。

## Out of scope

- **执行与终态链路**：接受后应答通道交接、Workspace 锁定、信任演示审批等——沿用上一张图的用户明示边界，将来另立 effort。
- **采集与心跳节拍机制本身**：15min 触发频率与信号采集不动，本图只管 Agent 在窗口内怎么做。
- **记忆系统完整建设**：生成输入仍只用 fork 现成数据（上张图 T4 决议）。
