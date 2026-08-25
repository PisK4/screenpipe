# CONTEXT · 项目词汇术语表

> **添加规则**
>
> - 新概念落地（新配置键、新 payload 标记、新工具、新状态、新出口）当天入表，不等成套；
> - 每条两三句：定义在前，代码锚点另起一行（表名 / 配置键 / 函数 / 标记），不抄代码能自解释的细节；
> - 中文定名须与代码标识对得上，英文原词括注在标题里；UI 文案、文档、注释用词以此表为准，不得另起别名；
> - 术语改名先改本表并在此注明旧词退役，再同步界面与文档；
> - 可调数值只写语义与边界，默认值以代码为准，避免此表变成第二份配置文档。

代码注释里的 beat 与 tick 同义，行文统一用「每轮生成」

## 意图卡片（intent card）

用户下一步最可能手动执行的任务的预告。粒度是**步进级**：项目内的一步 ＋ 可命名的具体对象 ＋ 可启动的动作。任务须在 48h 内可执行，支撑证据必须来自当前材料窗口；title 必填，兼任显示名与软去重材料里的 gist。来源分两族：常规卡 origin 为 `proactive`，系统特殊卡见「新手接入卡」。
代码锚点：`intent_cards` 表；模型经 `submit_intent_card` 工具提交，一至多两张、意图互异。

## 卡片类型（card type）

卡片的三分类，决定渲染形态与交卡校验：`light` 是一句话轻提示，不带方案列表；`read_only` 与 `side_effect` 是提案卡，带方案列表，后者描述改变状态的动作、每个方案必须写 consequence 后果行。
代码锚点：`parse.rs` 枚举校验；载荷 schema 在 `src-tauri/assets/extensions/intent-card.ts`。

## 方案列表（plans）

提案卡自带的候选行动组，一至三条，每条是 title ＋ summary ＋ 可选 consequence；`recommended_index` 标出预选的推荐项，选中才显示后果行。用户可以不选任何一条，在列表末尾自己写一个新方案。
代码锚点：`parse.rs::GeneratedPlan`；前端 `components/intent-workbench/plans-list.tsx`。

## 引子（proactive_view）

用户在卡上读到的证据段。写作契约：本材料窗口内的行为事实散文，不得缩成类别标签或空泛判断。
代码锚点：字段 `proactive_view`，写法约束写在 `src-tauri/assets/extensions/intent-card.ts` 的工具 description 里由模型直读。

## 卡片状态机（card status）

意图卡片的五值生命周期 `proposed → shown → accepted / rejected / expired`。过期时钟从用户看到卡片起算：mark_shown 写入 expires_at，重复 mark_shown 被 SQL 守卫拒绝，前端重渲染改不了时钟；接受与拒绝只写终态，不触发执行。
代码锚点：`intent_cards.status`；时钟长度 `card_ttl_secs` 设置页可调，新手接入卡不挂时钟。

## 卡片生成周期（tick）

心跳循环的一次触发，从信号闸门评估、组装材料、运行 Pi 会话到出口结算的完整过程。节奏由 `heartbeat_interval_secs` 配置，循环串行，一轮未结束不会开始下一轮。
代码锚点：`runner.rs::tick`、`start()` 主循环。

## 材料窗口（material window）

一轮生成可引用证据的时间范围，锚定到最后一张卡的创建时间，硬顶 7 天。
代码锚点：`material_window_secs` 配置、`gate::window_start`；payload 标记 `[MATERIAL_WINDOW]`。

## 信号窗口（signal window）

统计强度信号的第二个时间窗，锚定到最后一次生成尝试，无论成败都推进锚点，失败不会让闸门常开形成重试风暴。窗内数 app 切换与画面变化两类计数，任一越过阈值即放行本轮生成。
代码锚点：`gate.rs::signal_window_start`、`should_attempt_generation`。

## 材料（materials）

首条用户消息里宿主注入的全部上下文，标记族：`[CURRENT_TIME]`、`[ACTIVITY_SUMMARY]`、`[RECENT_CARDS]`（软去重用的瘦身清单）、`[OPEN_DRAFTS]`（草稿瘦身投影）、`[TASK]`。
代码锚点：`instruct.rs::build_user_payload`。

## 本地查证四件（verification tools）

会话白名单里的四个只读查询工具：activity-summary 摘要、活动搜索、记忆搜索、会议列表。模型靠它们自行查证，「材料不足」才是有据结论而不是客套话；search_activity 对返回做上下文保护（中段截断、低质行折叠计数），防止枚举历史吃掉响应预算。
代码锚点：`session.rs::INTENT_ALLOWED_TOOLS`；实现在 `src-tauri/assets/extensions/intent-search.ts`。

## 软去重（soft dedup）

防重复打扰的现行机制：近期瘦身卡片清单随 `[RECENT_CARDS]` 注入材料，模型判为意图相同或高度相近（尤其那张是 rejected）时不出卡；机械唯一索引已删，`dedup_key` 只是记录字段。查更早历史用 `get_recent_intent_cards` 工具。
代码锚点：`gate.rs::RECENT_CARDS_WINDOW_SECS`、`RECENT_CARDS_LIMIT`；工具注册 `src-tauri/assets/extensions/intent-card-recent.ts`。

## 出卡门槛

允许交卡的下限，四要件缺一不可：具体对象、强度信号、自然下一步、问题陈述（用户当前的摩擦 ＋ 卡片帮他解决的收益）。
代码锚点：文本落在 `instruct.rs::build_system_prompt` 与 cue-tools 技能 §2。

## 自检问句

提交前的行为闸门：用户看到这张卡的第一反应应是「正要弄这个」，而不是「别烦我」；后者视为材料不足。

## insufficient_material

材料不足的正式结论，同时是生成会话的**默认出口**——出卡是例外，不是常态。软去重命中后的主动放弃也走这同一个出口，所以材料不足率连续偏高时，先查判重规则与出卡门槛，再查信号质量。
代码锚点：`parse.rs::parse_model_output` 识别该载荷。

## 意图草稿（draft）

未熟观察的期票：证据还不够格出卡但值得追踪时，用 `save_intent_draft` 把观察与成熟条件（`ripe_when`）存下来，跨生成周期续写收敛。状态四值 `active → submitted | discarded | expired`——submitted 升级为卡，discarded 是模型主动废弃，expired 由心跳按 TTL 结算，三个终态都不可复活。草稿是出卡的准备态，不是出卡失败的替补。
代码锚点：`intent_drafts` 表、upsert 语义（带 `draft_id` 即更新）；活跃总量上限 `draft_max_active`；材料中只展示最新 3 条，全量经 `get_intent_draft` 取回。

## 收敛

草稿走向终点的动作：要么升级交卡，要么判定不再值得追踪而废弃。收敛线是续写次数到顶或 `ripe_when` 已满足，先到者触发；不允许无限续写。
代码锚点：规则正典在 cue-tools 技能草稿纪律节；判定依据 `renew_count` 与 `ripe_when`。

## 生成时限（session timeout）

一次生成会话的墙钟预算，超时会话被终止、本轮作废（未出卡、未存草稿，等同没运行过）。设置页可调（60–3600 秒）；心跳循环串行，时限拉长只会推迟下一轮，不会让两轮重叠。
代码锚点：`session_timeout_secs` 配置，消费点 `session.rs::run_intent_session`。

## 会话隔离（session isolation）

意图会话跑在专属项目目录 pi-intent，与其他 Pi 会话互不共享 transcript 与技能面；安全边界收敛在工具白名单上——白名单同时是运行时硬门控，扩展注册了但不在名单里的工具对模型不可见，bash 与一切写侧工具不进名单。
代码锚点：`session.rs::intent_project_dir`、`INTENT_ALLOWED_TOOLS`。

## 供给链（supply chain）

生成模型的来源解析链：slot（设置页意图专用槽）→ mirror（镜像 Chat 当前激活 preset，只记 id）→ builtin（内置本地 Ollama）。slot 为空就是「跟随 Chat」，任何路径不得把默认供给写进 slot；链只解析配置，运行期失败不跨级降级，下一拍同级重试。preset 切换的上报收在唯一写入汇点，新增切换界面必须走它。
代码锚点：`supply.rs::resolve_chain`；生效来源 tag `slot | mirror | builtin`；镜像汇点 `lib/active-ai-preset.ts` 的 `writeActiveAiPresetId`。

## 工作台（intent workbench）

主窗口里看卡、裁决卡的 section，pending = proposed + shown。新卡落库后发事件刷新列表，通知面板的查看动作跳到这里；裁决只经 Tauri command 改状态，模型侧没有写 status 的路径。
代码锚点：`apps/screenpipe-app-tauri/components/intent-workbench/`；事件 `intent_card_created`，通知动作 `open_intent_workbench`。

## 新手接入卡（onboarding card）

origin 为 `system_onboarding` 的系统特殊卡，由设置页或工作台空态显式触发，当日幂等、不挂过期时钟。全计划唯一的接受例外：写终态之外还真实注册检测到的 MCP 连接，失败只记日志不回滚。
代码锚点：`commands.rs::intent_spawn_onboarding_card`、`spawn_onboarding_connect_if_needed`。

## 出口结算（tick outcome）

每轮结束对会话产出的规约与归类：交卡载荷先经同名折叠、超上限丢弃，再按优先级分四类：cards（出了卡）、draft-progress（只有草稿操作）、insufficient（模型声明材料不足或判重后主动放弃）、failed（解析错误或空报告）。成败与原因写入最近生成记录，供设置页展示。
代码锚点：`runner.rs::reduce_submissions`、`session.rs::SessionReport`；记录键 `intent_last_generation`。

## 运行时设置（intent_settings）

心跳间隔、双时效、草稿上限、材料窗口等可调项共用的 KV 配置表，App 进程与引擎进程读同一份定义，设定页写入即时生效。加载侧统一夹取区间；gate 阈值仍是编译期常量，不暴露给用户。
代码锚点：`crates/screenpipe-db/src/db/intent_settings.rs`。
