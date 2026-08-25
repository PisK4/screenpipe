# 意图卡片 v1

<!-- doc-covers: crates/screenpipe-db/src/migrations/20260822120000_create_intent_cards.sql, crates/screenpipe-db/src/migrations/20260823120000_drop_intent_cards_dedup_index.sql, crates/screenpipe-db/src/db/intent_cards.rs, crates/screenpipe-engine/src/routes/intent_cards.rs, crates/screenpipe-engine/src/server.rs, apps/screenpipe-app-tauri/src-tauri/src/intent_agent/mod.rs, apps/screenpipe-app-tauri/src-tauri/src/intent_agent/gate.rs, apps/screenpipe-app-tauri/src-tauri/src/intent_agent/parse.rs, apps/screenpipe-app-tauri/src-tauri/src/intent_agent/instruct.rs, apps/screenpipe-app-tauri/src-tauri/src/intent_agent/session.rs, apps/screenpipe-app-tauri/src-tauri/src/intent_agent/supply.rs, apps/screenpipe-app-tauri/src-tauri/src/intent_agent/commands.rs, apps/screenpipe-app-tauri/src-tauri/src/intent_agent/runner.rs, apps/screenpipe-app-tauri/src-tauri/assets/extensions/intent-card.ts, apps/screenpipe-app-tauri/src-tauri/assets/extensions/intent-card-recent.ts, apps/screenpipe-app-tauri/src-tauri/src/events.rs, apps/screenpipe-app-tauri/src-tauri/src/main.rs, crates/screenpipe-engine/src/cli/agent.rs, apps/screenpipe-app-tauri/components/intent-workbench/index.tsx, apps/screenpipe-app-tauri/components/intent-workbench/plans-list.tsx, apps/screenpipe-app-tauri/lib/intent-events.ts, apps/screenpipe-app-tauri/lib/i18n/en-workbench.ts, apps/screenpipe-app-tauri/lib/i18n/zh-workbench.ts, apps/screenpipe-app-tauri/components/settings/ai-settings.tsx, apps/screenpipe-app-tauri/lib/active-ai-preset.ts, apps/screenpipe-app-tauri/components/chat/standalone/hooks/use-pi-session-lifecycle.ts -->
<!-- doc-verified: 7c3a14c5d（分支 cue-branding） -->
> **Current。** 本文核验于 `cue-branding` 分支的 7c3a14c5d。该分支合入 cue-branding 前，主线的 `doc-verified` 不覆盖意图卡片代码。

## 1. 目的与产品目标

Cue 在本地录制的基础上，主动向用户提出可执行的下一步工作建议。产品目标只有一句话：**制造 aha moment**——挖出用户自己没意识到的模式，或者主动给出省掉脑力劳动的行动方案。衡量一切设计取舍的标尺是它：没人接受的卡片谈不上惊喜。

v1 只做生成与展示闭环。执行链路、重写流程、记忆基底不在范围内，见第 12 节。

## 2. 用户经历的交互

按时间顺序走一遍：

**后台（无感）。** 只要采集引擎在跑（托盘挂着即可，主窗口可不开），Rust 侧随引擎常驻一个心跳循环，每 15 分钟醒来一次。先结算过期卡，再看最近窗口内的活动信号：app 切换与焦点事件 ≥3 次，或画面变化 ≥5 次才过门槛（常量集中在 gate.rs，D3）。

**出卡那一刻。** 过门后取一份 activity-summary 有界摘要和近 48 小时的历史卡片清单，起一个 Pi 子进程会话生成卡片。会话挂着只读工具白名单，模型可以自行查证本地数据，最后通过结构化工具调用交卡（第 5 节）。落库后两件事同时发生：工作台列表收到刷新事件，通知面板弹一条提醒。提醒走 notification-panel 现成的闸门，静音、勿扰、冷却照旧生效；被抑制也算通过闸门验证。

**裁决。** 提醒的「查看」动作跳进主窗口「工作台」section（左栏新增一行，不动 chat 首屏）。两个 Filter：待决定、已结束。一张提案卡自上而下是 title、proactive_view、方案列表——推荐项预选、选中显示后果行、末行「自己写一个新方案」输入框，选中自选项即聚焦输入框开始编辑；单选圆点由前端自绘，不依赖 webview 原生控件的填充渲染。按钮：「接受选中方案 / 不要」；轻提示卡没有方案列表，「知道了 / 不要」。

**接受之后，第一版什么也不发生。** 接受只写终态，不开 Thread 不触发执行。唯一例外是新手接入卡（第 9 节）。

**设置页。** 模型区有一块 intent 槽卡片：preset 选择器（含「跟随 Chat（默认）」）、当前实际生效来源与端点 host+model、最近一次生成的成败与原因。BYOK 引导块尚未实现，属已知缺口。

## 3. 管线全景

全链路三段管线，本 feature 新建一段半：

| # | Pipeline | 宿主 | 状态 |
| --- | --- | --- | --- |
| P0 | 采集管线：frames / elements / ui_events 持续落库 | screenpipe-engine | 已有，只消费 |
| P1 | **生成管线**：心跳 tick 内的固定顺序流程，含一次 Pi 会话 | src-tauri `intent_agent::runner` | 本 feature 新建 |
| P2 | **裁决管线**：事件监听 → 列表渲染 → shown 回写 → decide 写终态 | 前端 workbench + Tauri commands | 本 feature 新建 |

P1 每次 tick 的固定顺序：

1. `expire_due` 结算过期；
2. 材料窗口锚定最近一张卡的创建时刻（无卡默认 24h，硬上限 7 天防正反馈膨胀）；
3. 信号窗口锚定最后一次尝试（任何结局都推进锚点，失败不会让闸门常开形成重试风暴）；
4. 数增量信号过门槛；
5. GET activity-summary（ISO 8601 参数）＋ 预载近 48h 卡片清单（软去重材料，见第 4 节）；
6. 解析供给三级链（slot → mirror → builtin，见第 7 节）;
7. 起 Pi 会话（240 秒超时，用完即停），模型经 `submit_intent_card` 工具逐张交卡，一拍至多两张；
8. 按提交顺序归约全部载荷（同名折叠、超上限丢弃）、入库、emit 事件、发面板提醒；tick 状态四分类见下；
9. 成败写入 `intent_last_generation` 供设置页展示。任何一步失败记 tracing，循环不退出，下一拍同级重试。

tick 状态四分类（优先级从高到低）：

1. **cards**：落库 ≥1 张卡。detail 仅在张数 ≠1 时写 `"<n> cards"`；
2. **draft-progress**：零卡但会话里有 `save_intent_draft` 操作。detail 形如 `"<n> draft op(s), no card"`；
3. **insufficient**：零卡零草稿操作且模型显式声明材料不足。detail 为 `"material insufficient"`；
4. **failed**：解析错误或空报告。detail 带首个解析错误或 `"empty session report"`。

P2 是唯一能改卡片状态的通道：前端按钮只调 command，SQL 层带 WHERE status 守卫，模型侧没有任何路径能写 status。Pi 会话产出的只是工具调用参数，写库永远在 Rust 侧确定性代码手里。

两条旁路：过期结算挂 P1 节拍不建独立定时器；新手接入卡走专门 command 直接进 P1 后半段，跳过门槛和会话。

## 4. 数据、状态机与软去重

### 表结构与状态机

`intent_cards` 十三列（迁移 `20260822120000_create_intent_cards.sql` + `20260824220000_add_intent_card_title.sql`）：身份（id、origin、card_type、dedup_key、local_date）、内容（title、proactive_view、plans_json；title 自 2026-08-24 起是交卡契约必填项，历史行按首方案标题回填）、供给追溯（model_id）、时间戳（created_at、shown_at、expires_at）、状态（status）。

状态机五值 `proposed → shown → accepted / rejected / expired`，v1 只生效四条转移，全部由 SQL WHERE 守卫保证：

1. `mark_shown`：仅 proposed→shown，同时写 `shown_at` 与 `expires_at = shown_at + 48h`；
2. `finish`：仅 shown→accepted|rejected；
3. `expire_due`：仅结算 shown 且到期的行；
4. **时钟不可续命**：重复 mark_shown 被 WHERE 拒绝，组件重挂载、Strict Mode 双渲染、多窗口都改不了 shown_at。前端 useRef 防重只是省往返，兜底在 SQL。

proposed 与 shown 分开，是为了让过期时钟从「用户有机会看到」起算；三个终态分开存为将来的反馈账留信号。新手卡 expires_at = NULL 不过期。

### 软去重（2026-08-23 重设计，作废 D2）

机械去重已被推翻。原规则 `unique(dedup_key, local_date)`（每 app 每类型每天最多一张）在真实使用中暴露三个结构性问题：重度单应用用户的 dominant_app 全天锁死，名额上午耗尽后整天静默吞卡；昂贵会话跑完才判重，白跑；零点配额重置对 rejected 无记忆，防不住跨日重复打扰，又误伤同日不同意图。它是伪装成去重的每日配额，而键的两个分量（模型自选的 card_type、使用习惯决定的 dominant_app）都不受产品控制。

现行机制：

- 迁移 `20260823120000_drop_intent_cards_dedup_index.sql` 删除唯一索引（DROP INDEX，不重建表）。`dedup_key` 列保留继续写，降级为记录字段（格式仍是 `{card_type}:{dominant_app}`），排查有用、不构成约束。
- 心跳预载近 48 小时卡片清单进生成材料（`RECENT_CARDS_WINDOW_SECS` / `RECENT_CARDS_LIMIT`，gate.rs）。system prompt 写明判重规则：与清单中某卡意图相同或高度相近——尤其那张是 rejected——必须提交 `{"insufficient_material": true}`，不要出卡。rejected 从此有跨日记忆。
- 模型要查更早历史时调 `get_recent_intent_cards` 工具（第 8 节）。
- 新手卡幂等从唯一索引改为 command 内显式当日预检（`intent_find_id_by_dedup_key`）；`InsertOutcome::DedupHit` 已移除，insert 直接返回新行 id。
- 成本边界：心跳节拍（900s）是硬顶，判重失效的最坏结果是一天几十次会话里多几张重复卡，通知面板兜底。不设机械保险丝；实测命中率不可接受时，最粗兜底是同 app 单日 COUNT 检查，届时另议。

### 草稿状态机（2026-08-24 新增，`intent_drafts` 表）

交卡出口从二元扩为三分：已熟交卡（submit_intent_card）、未熟存档（save_intent_draft，工具见 FEATURE_TOOLS_REFERENCE §4.3.2）、无信号（insufficient_material）。草稿是「带成熟条件的期票」：`gist` + `evidence_so_far` + 必填的 `ripe_when`，跨心跳存活于独立的 `intent_drafts` 表（迁移 `20260824120000_create_intent_drafts.sql`），不经 transcript 提取。

状态四值 `active → submitted | discarded | expired`：

1. `upsert`：新建或按 id 续写（renew_count +1）；活跃数达上限（`INTENT_DRAFT_MAX_ACTIVE=10`）由 POST 路由以 409 拒绝并引导先收敛或丢弃；
2. `expire_due`：心跳每拍结算超过 TTL（`INTENT_DRAFT_TTL_SECS=48h`，锚定 created_at）的 active 行；
3. submitted / discarded 为终态，不可续写复活。

防拖延是宿主职责而非模型自觉：收敛线为 renew_count 达到 3 或 ripe_when 已满足——必须升级交卡或判定不再值得追踪，不允许无限续写；该规则的权威文本在 cue-tools skill 的草稿纪律节，由 system prompt 的强制读指令兜底。gate 的 spawn 门槛暂不因活跃草稿降低，先观察真实续写率。

### 草稿读侧与材料投影

活跃草稿清单按最近活动排序（`updated_at DESC, id DESC`）。生成材料的 `[OPEN_DRAFTS]` 节是行级 JSON 计数头投影：`{"active_total":N,"shown":[...]}`，`shown` 至多 3 条（最新活动优先），每条固定四字段 `draft_id/gist/ripe_when/updated`（`updated` 为本地绝对时间 YYYY-MM-DD HH:MM）；evidence_so_far 不进材料，模型经 `get_intent_draft` 工具（intent-draft.ts，读 `GET /intent-cards/drafts` 全量活跃清单）取回完整详情后再续写。save 成功回执携带本地化的 updated 时间戳，来自 upsert 响应新增的 `updated_at` 字段。

### 运行时配置与设定页（2026-08-24）

心跳间隔、卡片 TTL、草稿上限、草稿 TTL、材料窗口默认值五项为运行时配置：存共享 KV 表 `intent_settings`（迁移 `20260824130000_create_intent_settings.sql`），引擎进程（drafts 路由的上限校验）与 App 进程（心跳循环、mark_shown 时钟、窗口锚定）读同一份定义；设定页「意图卡片」（`components/settings/intent-settings.tsx` 对应的 `intent-cards` section）写入后即时生效，无需重启。加载侧统一夹取区间，手改数据库不会卡死心跳。gate 阈值、会话超时等判据仍留编译期常量——暴露给用户只会制造误调。

## 5. 输出契约：submit_intent_card 结构化交卡

结论必须通过调用 `submit_intent_card` 工具提交，不写普通文字。工具参数 schema 内嵌完整卡片契约（oneOf 两分支），pi 在协议层做 TypeBox 编译校验：非法调用在 execute 之前被拒并回灌错误让模型自纠。第三方结构化输出包评估后未采纳——Ajv 校验与 steering 重试都有更便宜的等价物（协议层校验、心跳下拍自然重试）。

两种合法载荷：

```jsonc
// 普通提案卡
{ "v": 1, "card_type": "light|side_effect|read_only",
  "proactive_view": "", "recommended_index": 0,
  "plans": [{ "title": "", "summary": "", "consequence": "" }] }

// 材料不足（含判重命中后的主动放弃）
{ "insufficient_material": true }
```

Rust 侧从 agent_end 的 messages 数组按调用顺序提取全部 `submit_intent_card` 调用的 arguments 作为交卡载荷，逐个流经原 parse 层（D4 版本门：未知版本拒解析、未知字段宽容）。一拍多卡契约：模型可多次调用该工具，单拍上限 2 张、意图互异；同批同名卡由宿主折叠（只保留首个，见 runner 的归约策略）；已交卡后不得再补发 insufficient_material。无工具调用的会话降级为把最终文本当单一载荷，parse 层仍拒非 JSON 文本。

## 6. Intent Agent 运行时

生成段是一个真实的 Pi 子进程会话，与 chat 同一套 runtime 和启动模式（piStart/piPrompt/piStop），区别只在宿主方式：chat 由用户消息驱动，意图会话由 Rust 心跳在门槛过后拉起，拿到终报即停。

为什么用会话不用单次直调：aha moment 藏在 activity-summary 压缩掉的部分里，会话形态下模型拿只读工具自己查证，「材料不足」也从客套话变成查证后的有据结论；且加工具从一轮架构改动变成一行白名单配置。

会话专属项目目录 `~/.screenpipe/pi-intent`，与其他会话互不共享。技能可见面与 Chat 对齐（全局发现 + 基线三件照常安装；2026-08-24 修订 D7——原镜像剥离对 pi 全局技能发现本就无效，轨迹取证见 01a02f23/01a02f15）。隔离边界收敛到工具白名单：bash 与一切写侧工具不进白名单；残余的技能正文注入风险由工具白名单兜底（sp_mcp_call 的外部副作用为已知并接受的残留面）。

工具白名单十三项：read / grep / find / ls（本机文件读取）、sp_mcp_list_tools / sp_mcp_call（查询用户注册的 MCP 服务）、submit_intent_card（交卡）、get_recent_intent_cards（近期卡片查询）、get_activity_summary / search_activity / search_memories / list_meetings（本地查证四件）、save_intent_draft / get_intent_draft（草稿写读）。会话 transcript 天然留存于 pi-intent 目录，排查某张烂卡能看到完整推理与工具调用过程。

角色名为 **Intent card Agent**（system prompt REPLACE 文本首句）；完整的生成流程正典——四要件门槛、五步流程、自检问句、默认出口倾斜、草稿纪律——的唯一权威版本在 cue-tools skill 的「角色边界与生成流程」节，由 system prompt 第三段的强制读指令兜底执行；prompt 本体只携带角色、边界与不可让渡的契约指针。

## 7. 模型供给：三级链与镜像汇点

| 级别 | 来源 | 说明 |
|---|---|---|
| slot | 设置页意图专用槽 | PresetQuadruple 整体存 store extra；**永不被默认值写入**，空就是「跟随 Chat」 |
| mirror | Chat 当前激活 preset | 只镜像 preset id；心跳每次按 id 去 aiPresets 现查端点，改 Key/URL 天然新鲜 |
| builtin | 内置 Ollama | qwen3.5:9b @ http://localhost:11434/v1 |

链只解析配置，运行期失败不跨级降级，下一拍同级重试（D8）。

两条已修死的纪律：

- **懒初始化禁令**。曾经 slot 键缺失时 `intent_get_supply` 会把 builtin 写进 slot；slot 优先级高于 mirror，设置页开一次就永久击穿「跟随 Chat」。现在 slot 为 None 就返回 None，builtin 兜底由 `resolve_chain(None, None)` 承担，任何路径不得把默认供给写进 slot 键。
- **镜像上报唯一汇点**。切换 preset 的所有界面路径都经过 `writeActiveAiPresetId`，镜像上报就收在该函数内（`reportActiveAiPresetId`，带去重守卫与失败重试位）；chat 生命周期 hook 只保留启动时机的上报腿。新增切换面时只要走这个写入函数，镜像天然同步。

设置页意图模型卡常显当前生效来源 tag 和实际端点 host+model，「跟随 Chat」也显示解析出的具体地址。

## 8. 读侧：recent 路由与扩展单文件分发

近期卡片的读取只有一个事实源：引擎路由 `GET :3030/intent-cards/recent`（screenpipe-engine routes/intent_cards.rs），参数 `since_hours`（默认 48，对齐过期时钟）与 `limit`(默认 20，上限 100)，鉴权走本地 API 的 Bearer。App 内预载进程内直调同一个查询函数，不走 HTTP。

`assets/extensions/intent-card-recent.ts` 注册 `get_recent_intent_cards` 工具包装这条路由，刻意只依赖 fetch 和 env（`SCREENPIPE_PORT`、`SCREENPIPE_LOCAL_API_KEY`），对 App 零进程内依赖——因此它可以整文件拷进任何外部 Pi agent 的 `.pi/extensions/` 目录直接用（本机已装：`~/.pi/agent/extensions/`）。未来其他场景要读卡片，复用同一路由。

写侧刻意不存在：模型侧没有任何 HTTP 路径能创建或改写卡片。交卡走的是 App 内嵌的 `intent-card.ts`（submit_intent_card），其载荷由宿主从会话 transcript 提取，不经 HTTP；外部分发版不含此文件。若将来要给外部 agent 开交卡能力，须新增带 token 门控的 POST 路由并在 wayfinder 记信任边界裁决，不要悄悄扩例。

## 9. 新手接入卡

`system_onboarding` 卡由设置页或工作台空态显式触发（intent_spawn_onboarding_card），幂等靠显式当日预检而非唯一索引。检测到的桌面 Agent 名来自引擎探测。接受语义是全计划唯一的例外：写 accepted 终态之外还调 skills.rs 现成的 connect_detected_ai_tools_in_background 真实注册 MCP，失败只记 tracing 不回滚状态。其余所有卡的「接受」都只写终态。执行链路 effort 启动时应回来统一这条语义。

## 10. 工作台与前端接线

工作台是 Home 的 sidebar section（?section=workbench），pending = proposed+shown。文案全部走 i18n 字典 workbench.*，en 先行 zh 同构。卡片正文自上而下渲染 title（`intent_cards.title` 列，经 `IntentCardDto.title` 透传）、proactive_view、方案列表；无 title 的历史行回退用 proactive_view 当标题，且不再重复显示正文段。方案列表单选、推荐项预选、选中显 consequence、末行自定义输入框（选中即聚焦）；点击后乐观移出，command 报错才 toast。pending 渲染后逐张 mark_shown 回写。通知动作 open_intent_workbench 由前端监听 notification:action 跳转；该事件 cfg 门控 macOS/Windows，Linux 降级为仅面板展示。

## 11. Evaluation 怎么追【分层提案】

L0（上线当天可算，零迁移）：采纳率（accepted 占终态比例，按 card_type/model_id/供给来源分桶）、响应时延（created_at→shown_at→终态分布）、过期率、材料不足率（会话形态下含义更重——判重命中的主动放弃也走 insufficient_material，连续过高说明判重规则或门槛该调了）、生成健康度（会话失败率、超时、格式错误、三级回退命中比例）、会话轨迹排查。建议 SQL 口径并入验收清单。

L1（跑一段后的补票候选）：rejected 无理由字段是有意砍掉的；候选形态二选一——rejected_reason 加列（rebuild 迁移）或独立 feedback 小表，等真实数据积累出问题再回来定。

L2（执行链路落地后才可能）：真实价值是「接受的方案被执行并解决问题」，v1 天然测不到价值闭环。执行链路 effort 启动时 evaluation 应作为一等公民一起设计。

## 12. 明确不做

执行与终态后续链路、卡片重写流程、记忆基底、记账三件套、独立过期定时器、BYOK 引导 UI、卡片快捷键、「执行中」Filter、chat active preset 整体迁入 SettingsStore（只镜像 id）、机械去重的任何回归（unique 索引、每日配额）、对外 HTTP 写卡路由（除非另立信任边界裁决）。出现这些诉求时另行开票。

## 13. 后续改动检查

| 改动类型 | 应同时确认的结果 |
|---|---|
| 改状态机或加新值 | CHECK 约束要重建表迁移；转移守卫必须留在 SQL 层 |
| 改心跳节拍、门槛或窗口常量 | 常量在 gate.rs 顶部；材料/信号双窗口锚点语义（D9）不得破坏 |
| 改软去重行为 | RECENT_CARDS_* 常量与 prompt 判重规则要同步；恢复任何机械约束前先看 T10 票的成本论证 |
| 给卡片加新形态 | submit schema 与 parse.rs 的 D4 规则两侧同步；未知版本拒解析 |
| 改供给链 | 三级顺序不变；禁止把默认供给写进 slot 键；mirror 只传 id；设置页必须能看到最终生效端点 |
| 动 intent-card-recent.ts | 它是双通道分发的单源：改完同时更新受管安装与 `~/.pi` 等外部分发副本 |
| 新增接受副作用 | 先回到第 9 节例外声明，不要悄悄扩例 |
| 新增文案 | 进 workbench.* 字典，en 先行 zh 补齐；品牌词写 Cue |

## 14. 证据索引

- screenpipe-db：迁移 ×2（建表、删索引）；db/intent_cards.rs 数据层与状态机守卫，含 9 个单元测试。
- screenpipe-engine：routes/intent_cards.rs 只读路由；server.rs 注册行。
- src-tauri intent_agent：runner.rs 心跳流水线；gate.rs 双窗口与软去重常量；instruct.rs 判重规则与载荷组装；session.rs 会话编排、白名单与扩展安装；supply.rs 三级链；commands.rs 七个 command；parse.rs D4 解析。
- assets/extensions/：intent-card.ts（交卡契约）、intent-card-recent.ts（读侧，双通道分发单源）。
- 前端：components/intent-workbench/、lib/active-ai-preset.ts（镜像汇点）、use-pi-session-lifecycle.ts（启动上报腿）。
- 决策记录：wayfinder/tickets/10-软去重重设计.md（T10，作废 D2，补录 D6–D9）。
- doc/FEATURE_MODEL_INVOCATION_INVENTORY.md 的 PATH-INTENT-CARD 条目。
