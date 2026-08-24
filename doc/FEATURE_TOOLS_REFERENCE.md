# Cue Tools 参考

<!-- doc-covers: apps/screenpipe-app-tauri/src-tauri/assets/extensions/web-search.ts, apps/screenpipe-app-tauri/src-tauri/assets/extensions/mcp-bridge.ts, apps/screenpipe-app-tauri/src-tauri/assets/extensions/save-artifact.ts, apps/screenpipe-app-tauri/src-tauri/assets/extensions/live-views.ts, apps/screenpipe-app-tauri/src-tauri/assets/extensions/connection-gate.ts, apps/screenpipe-app-tauri/src-tauri/assets/extensions/intent-card.ts, apps/screenpipe-app-tauri/src-tauri/assets/extensions/intent-card-recent.ts, crates/screenpipe-core/assets/extensions/sub-agent.ts, crates/screenpipe-engine/src/routes/intent_cards.rs, apps/screenpipe-app-tauri/src-tauri/src/intent_agent/session.rs -->
<!-- doc-verified: b4068aa10（分支 feat/intent-cards，已合入 cue-branding） -->

## 1. 这份文档管什么

Cue 里「agent 能调用的每一个工具」的目录级参考：它是什么、什么时候该触发、参数有哪些字段、返回什么结构、出错时模型看到什么。目标是让读者不读源码就能正确使用和集成这些工具。

与另外两份文档的分工：

| 文档 | 管什么 | 不管什么 |
| --- | --- | --- |
| 本文 | 工具目录：参数、响应、触发时机、会话可见性、集成步骤 | 架构论证 |
| `FEATURE_AGENT_CAPABILITY_SURFACE.md` | Skill / Tool / API 四层关系、媒体代理边界、pi-mediated 记账语义 | 逐工具的字段细节 |
| `FEATURE_MODEL_INVOCATION_INVENTORY.md` | 每条模型调用路径的登记 | 工具用法 |

范围界定：只收录 agent 会用到的工具面。引擎全量 HTTP 路由不在本文（有几百条），机器生成的字段级规范在 `GET :3030/openapi.json` 与 `/openapi.yaml`；本文只写字段级展开那些被工具当作后端、或外部 agent 集成必需的路由。

## 2. 工具总表

按第 4 节的四个分组排序，「状态」列标明实现现状：

| 工具 | 注册扩展 | 可见会话 | 性质 | 后端 | 状态 |
| --- | --- | --- | --- | --- | --- |
| `get_recent_intent_cards` | intent-card-recent.ts | intent 白名单；可独立分发 | 只读 | 本地 `/intent-cards/recent` | 已上线 |
| `get_activity_summary` | intent-search.ts | intent 白名单 | 只读 | 本地 `/activity-summary` | **规划中** |
| `search_activity` | intent-search.ts | intent 白名单 | 只读 | 本地 `/search` | **规划中** |
| `search_memories` | intent-search.ts | intent 白名单 | 只读 | 本地 `/memories`（仅 GET） | **规划中** |
| `list_meetings` | intent-search.ts | intent 白名单 | 只读 | 本地 `/meetings` | **规划中** |
| `query_data` | 待定 | intent 白名单 | 只读（wrapper 强制） | 本地 `/raw_sql` | **二期议** |
| `sp_web_search` | web-search.ts | chat 全量 | 读，出网 | Cue Cloud 搜索接口 | 已上线 |
| `sp_mcp_list_tools` | mcp-bridge.ts | chat 全量；intent 白名单 | 读 | 本地 `/mcp-servers` | 已上线 |
| `sp_mcp_call` | mcp-bridge.ts | chat 全量；intent 白名单 | **可能产生外部副作用** | 本地 `/mcp-servers/{id}/call` | 已上线 |
| `screenpipe_list_connections` | connection-gate.ts | chat 全量 | 读 | 本地 `/connections` | 已上线 |
| `screenpipe_connect_app` | connection-gate.ts | chat 全量 | 发起用户授权流程（阻塞等待） | 授权 UI + 连接刷新 | 已上线 |
| `submit_intent_card` | intent-card.ts | 仅意图生成会话 | 受控交卡出口 | 无网络调用，宿主从 transcript 提取 | 已上线 |
| `save_intent_draft` | intent-draft.ts | 仅意图生成会话 | 非终态存档 | 本地 `/intent-cards/drafts`（规划路由） | **规划中** |
| `save_artifact` | save-artifact.ts | chat 全量 | 写入 Artifacts 库 | 本地 `/artifacts/register` | 已上线 |
| `screenpipe_live_view` | live-views.ts | chat 全量 | 读 / 写 Live View 定义 | 本地 live-views 路由族 | 已上线 |
| `screenpipe_live_view_propose` | live-views.ts | chat 全量 | 提议变更，schema 内校验 | 无网络调用，返回提案文本 | 已上线 |
| Pi 内置七件（read/grep/find/ls/bash/edit/write） | Pi 自带 | 见第 3 节矩阵 | 视具体工具 | 本机文件系统 | 已上线 |

状态取值：「已上线」为现状。「规划中」指契约已定稿、代码尚未落地，逐工具小节即实现应遵循的规格；引用它们描述现状前，先确认对应扩展文件是否存在。「二期议」表示方向认可但前置条件未满足（见 §4.1.6）。四个只读取证工具同属一个自包含扩展 `intent-search.ts`（照 intent-card-recent.ts 的 fetch+env 模式），落地时同批加进 `INTENT_ALLOWED_TOOLS` 并把状态改为已上线。

## 3. 会话矩阵

工具不是每个会话都能看到。Pi 不设 `allowedTools` 即默认全开，所以「收窄」必须显式配置：

| 会话 | 内置工具 | 扩展工具 |
| --- | --- | --- |
| Chat | 全量含 bash/edit/write | 上表 chat 全量各工具 |
| 意图卡片生成会话（session id `intent-card`） | 仅 read / grep / find / ls | `sp_mcp_list_tools`、`sp_mcp_call`、`submit_intent_card`、`get_recent_intent_cards`（与内置四件合成八项白名单，常量 `INTENT_ALLOWED_TOOLS`；规划扩入 §2 状态为「规划中」的五件：四件只读取证工具加 `save_intent_draft`，落地时同批加进该常量） |
| 外部 Pi agent（用户自装） | 该 agent 自己的默认面 | 仅拷入的扩展文件（现例：intent-card-recent.ts） |

白名单机制：会话配置带 `allowedTools` 数组，Pi 只暴露名单内工具。意图会话的隔离边界有两处：专属项目目录 `~/.screenpipe/pi-intent`，以及 bash 与一切写侧工具不进白名单。技能可见面与 Chat 对齐——原「运行前剥离用户技能镜像」一条已于 2026-08-24 作废（pi 自动发现全局技能目录，剥离从未真正生效，裁决记录见 FEATURE_INTENT_CARDS §6），技能正文注入的残余风险由工具白名单兜底。

## 4. 逐工具参考

逐工具按四个分组归档，分组轴是受众与副作用等级：数据查证（本地只读）、外部世界（出网或有外部副作用）、产出交付（写用户可见产物）、会话基建。每工具五段：用途与触发、参数、响应、错误行为、边界。参数表列类型、必填、含义；「必填」指 schema 的 required 或缺省即错。标题后标「规划中」「二期议」的小节描述的是已定稿的设计契约，供实现对照，不代表现状。

### 4.1 数据查证类（本地只读）

意图判重与采集数据取证，全部只读。主要服务意图生成会话；chat 会话排障时可经 bash curl 直连同一批后端路由（用法见 screenpipe-api 技能）。

#### 4.1.1 `get_recent_intent_cards`

读取最近生成的意图卡片清单。主用途是判重：同一意图已有卡片或曾被拒就不要再产出同类卡。生成材料里通常已附带近 48 小时清单，本工具用于查更早历史。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `since_hours` | number | 否 | 往回看多少小时，默认 48（对齐过期时钟） |
| `limit` | integer | 否 | 最多几张，默认 20，最大 100 |

Response：每行一张卡的文本列表 `- #<id> [<card_type>/<status>] <proactive_view> (dedup_key=…, created_at=…)`；窗口内无卡时明说。

错误行为：HTTP 非 2xx 返回状态码与 body 前 400 字符。边界：这是双通道分发单源文件——App 内受管安装与外部分发副本（本机 `~/.pi/agent/extensions/`）必须同步更新；只依赖 fetch 和 env（`SCREENPIPE_PORT`、`SCREENPIPE_LOCAL_API_KEY`），对 App 零进程内依赖。

#### 4.1.2 `get_activity_summary`（规划中）

宏观活动摘要，与生成材料预载的 summary 同源，差别在时间窗可自选。用途：怀疑摘要失真、要看子时段粒度、或要窗口之前的连续上下文时换窗重查。是否调用由模型自主判断，材料够用就不必调。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `start_time` | string | 否 | ISO 8601、相对时间（`16h ago`）或本地日历字面量（`today`）；缺省取本次材料窗口起点 |
| `end_time` | string | 否 | 同上；缺省 now |

Response：`/activity-summary` 原样 JSON（apps / windows / key_texts / audio 与 data_status 字段）。错误行为照 §9.3 纪律返回状态码与原因。边界：日历字面量按用户本地时区解释，禁止在模型侧换算 UTC 午夜；本工具不做裁剪，窗口大小由调用方控制。

#### 4.1.3 `search_activity`（规划中）

原文级查证入口：verbatim 文本、OCR、音频转录、指定 app 或窗口的精确匹配。摘要说「用户在用 X」，出卡前用本工具确认 X 里具体发生了什么。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `q` | string | 否 | 关键词；音频转录噪声大，搜说话内容慎用 |
| `content_type` | enum | 否 | all（默认）/ accessibility / audio / ocr / input |
| `start_time` | string | 是 | 时间格式同 §4.1.2；必填是为防无界查询超时 |
| `end_time` | string | 否 | 缺省 now |
| `app_name` | string | 否 | 应用名子串 |
| `window_name` | string | 否 | 窗口标题子串 |
| `limit` | integer | 否 | 夹取 1–20，翻页用 offset |
| `offset` | integer | 否 | 缺省 0 |

三条纪律焊死在 wrapper 里，模型不可绕过：fields 列预设白名单（type / app_name / text / timestamp / frame_id）、max_content_length 中段截断、start_time 强制必填。这是把 screenpipe-api skill 的上下文保护规则从「靠模型自觉」升级成「代码保证」，也是包工具相对塞 skill 的核心收益。

Response：`{ data: [...], pagination }`，每行只含白名单列。空结果的返回体要提示回退 get_activity_summary 核对 data_status，不得据此直接断言「没有数据」。

#### 4.1.4 `search_memories`（规划中）

查长期记忆库：偏好、历史决策、项目背景，信号密度高于原始事件流。出卡前先查一遍，避免推荐用户早已决定过的事，同时给卡片补个性化依据。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `q` | string | 否 | FTS 检索词 |
| `tags` | string | 否 | 逗号分隔，条目须携带全部标签 |
| `min_importance` | number | 否 | 重要度下限，0–1 |
| `start_time` / `end_time` | string | 否 | 时间格式同 §4.1.2 |
| `limit` | integer | 否 | 上限夹取 |

边界：只包 GET；POST/PUT/DELETE 一概不进任何白名单——无人值守会话不得写记忆库。

#### 4.1.5 `list_meetings`（规划中）

会议清单查询。摘要里会议信息被压缩，需要参会人与时段细节时用它展开。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `start_time` / `end_time` | string | 否 | 缺省最近 24 小时 |
| `limit` | integer | 否 | 上限夹取 |

Response：`/meetings` 清单 JSON。错误行为照 §9.3 纪律。

#### 4.1.6 `query_data`（二期议）

包装 `POST /raw_sql` 的自由查询出口。方向认可、暂不实现：引擎对 raw_sql 的只读约束目前是纪律约定而非强制，落地前置条件是 wrapper 强制单条 SELECT、自动注入 LIMIT、拒绝 PRAGMA/ATTACH 与多语句。契约待上述护栏定稿后回填本节。

### 4.2 外部世界类（出网或外部副作用）

触达设备之外的信息与能力。凡可能产生外部副作用的调用，权限与审计按外部动作对待。

#### 4.2.1 `sp_web_search`

搜索公网内容。只在需要公开外部信息时用——时事、新闻、公开人物或公司、公开产品文档。禁止用于用户本地数据查询（那是数据查证类和 skills 的事）。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `query` | string | 是 | 搜索词 |

Response：text block，含搜索结果与来源列表。

错误行为：非 2xx 时返回 `Web search failed (<status>): <body>` 文本。边界：请求离开设备，走 Cue Cloud 凭证；工具名带 `sp_` 前缀是为避免与用户全局包撞名导致非交互运行中止（issue #3812）。

#### 4.2.2 `sp_mcp_list_tools`

列出用户注册的 MCP 服务及其暴露的工具。调用 `sp_mcp_call` 前必须先调它拿 `server_id` 和工具名。设计为一对代理工具而非每工具注册一次，是为了省上下文（每服务省约 7-9%）并避开 Anthropic 单轮工具数上限。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `server_id` | string | 否 | 只列该服务；缺省列全部 |

Response：Markdown 文本，每服务一节，列 `{ name, description }`。无注册服务时提示去连接页添加。

错误行为：单个服务查询失败在对应小节标 `ERROR:`，不影响其他服务。边界：只列 `enabled !== false` 的服务；`SCREENPIPE_MCP_SERVER_ALLOWLIST` 环境变量可进一步收窄可见集。

#### 4.2.3 `sp_mcp_call`

调用用户注册 MCP 服务上的一个工具。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `server_id` | string | 是 | 目标服务 id（来自 list_tools） |
| `tool` | string | 是 | 该服务声明的工具名 |
| `arguments` | object | 否 | 匹配目标工具 schema 的参数对象 |

Response：透传 MCP 的 `content` 数组（通常 text block）。若 MCP 结果 `isError: true`，返回前置警告行说明该工具执行失败——防止把错误当成功继续跑。

错误行为：HTTP 非 2xx 返回状态码与 body 前 800 字符。边界：可能产生外部副作用（发消息、建工单），权限与审计按外部调用对待。

#### 4.2.4 `screenpipe_list_connections`

列出应用连接及各自连接状态。对外部 app 做任何发送、推送、创建、读取之前先调它确认连通性。

参数：无。

Response：JSON 文本 `{ connections: [{ id, name, connected, connected_via, mcp, mcp_server_id, category, description, action_hint }] }`。`connected_via` 区分 mcp 与 connection_proxy，`action_hint` 告诉模型该走哪条路。Gmail 等纯 Composio 托管的连接即使没有原生条目也会合成出现。

错误行为：`isError: true` 加失败原因文本。

#### 4.2.5 `screenpipe_connect_app`

任务依赖的外部 app 未连接时，发起内联授权请求并**阻塞等待用户操作**。用户拒绝前不得继续依赖该 app 的动作。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `connectionId` | string | 是 | 连接 id，如 linear、notion、github、google-docs |
| `reason` | string | 否 | 给用户看的、为什么现在要连的理由 |
| `requiredFor` | string | 否 | 连接后将继续的具体动作描述，拼进确认文案 |

Response：JSON 文本 `{ status: connected | declined | failed, connectionId, name, ... }`。已连接直接返回 connected；无 UI 环境返回 declined 附提示；用户取消视为 declined（干净拒绝，不算失败）；确认后刷新仍不在线则 failed 且 `isError: true`。执行模式为 sequential。

### 4.3 产出交付类（写用户可见产物）

落盘或提交面向用户的最终产出。共同纪律：临时文件和中间产物不走这一组。

#### 4.3.1 `submit_intent_card`

意图卡片生成的唯一交卡出口。参数 schema 是单层平面 object：此前的 oneOf 两分支由 pi 协议层 TypeBox 校验先行拦截，非法调用到不了 execute 也带不出修正指引，故两种载荷的互斥与完整性检查全部下沉到 execute 内自检，非法时抛出可修正的错误文本回灌模型重试。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `v` | integer | 卡载荷必填 | 契约版本，恒为数字 1 |
| `card_type` | enum：light / side_effect / read_only | 卡载荷必填 | 卡片类型，语义见下 |
| `proactive_view` | string | 否 | 给用户看的一句话引子，中文 |
| `recommended_index` | integer ≥0 | 否 | 推荐方案下标 |
| `plans` | array 1–3 项 | 卡载荷必填 | 方案列表，每项 `{title*, summary*, consequence?}` |
| `insufficient_material` | boolean | 材料不足形态必填 | 恒为 true，与卡载荷互斥 |

card_type 语义：read_only=只读操作建议（查询、汇总、打开查看某内容）；side_effect=改变系统状态的建议（改设置、启动自动化），必须给 consequence；light=一句话轻提示，不带 plans。light 与 plans 互斥由 execute 强制，违反会被打回并附二选一的改法。

Response：execute 回执 `Intent card submitted.`——真正的载荷由宿主从会话 transcript 的最后一个 submit_intent_card 工具调用里提取（见 FEATURE_INTENT_CARDS.md 第 5 节）。此工具仅在 App 内意图会话安装，不经 HTTP，外部分发版不含。

#### 4.3.2 `save_intent_draft`（规划中）

交卡之外的第三态出口。交卡语义三分后各管一段：submit_intent_card=已熟交付；本工具=信号真实但未熟，把追踪线索存档，下个心跳拉出来接着跑；insufficient_material=没有值得追踪的信号。参数 upsert：给 `draft_id` 即更新既有草稿，缺省新建。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `draft_id` | integer | 否 | 更新指定草稿；缺省新建 |
| `gist` | string | 是 | 一句话：在追踪什么 |
| `evidence_so_far` | string | 是 | 已观察到的材料要点 |
| `ripe_when` | string | 是 | 成熟条件：出现什么就升级为卡 |

Response：`Draft saved (#<id>).` 或更新回执；活跃草稿数达上限时拒绝新建并附「先收敛或废弃」的指引。错误行为照 §9.3 纪律。

边界与宿主侧纪律：草稿持久化在引擎侧 SQLite（intent_cards 表扩展 status=draft 或独立表），不经 transcript 提取——跨心跳续写要求它独立于单次会话存在，App 重启不丢。防拖延循环三条：活跃草稿数超上限（配置项 `intent_draft_max_active`，缺省 3）拒绝新建；存活超时（配置项 `intent_draft_ttl_hours`，缺省 48，对齐卡片过期钟）强制二选一——升级交卡或废弃；同内容原样续写连续超限同样强制收敛。

落地时的联动调整：runner 材料注入「未定稿草稿」一节（gist / evidence_so_far / ripe_when / 已续写次数），有活跃草稿时 spawn 会话的门槛降低（续写比冷启动便宜且价值确定）；get_recent_intent_cards 响应增加 drafts 节，判重语义区分两种抑制——「已有同主题草稿→更新那一份」与「已发过同类卡→不再产出」；生命周期状态机 draft → updated* → submitted | discarded | expired 记入 FEATURE_INTENT_CARDS.md。

#### 4.3.3 `save_artifact`

把面向用户的最终产出（笔记、报告、摘要、清单、导出、代码文件）登记进 Artifacts 库。更新已有 artifact 也用它（同路径 upsert，不产生重复）。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `filename` | string | 是 | 带扩展名的文件名，如 `weekly-summary.md`；路径分隔符与 `..` 会被清洗 |
| `content` | string | 是 | 完整文件内容 |
| `title` | string | 否 | Artifacts 库里的展示标题，缺省取文件名 |

Response：`Saved "<title>" to Artifacts (<output_path>)`。

错误行为：非 2xx 返回状态码与错误体。边界：仅文本类（md/html/json/txt/csv/tsv/ts 等，映射为 kind）；二进制注册是后续能力。写入走会话级临时目录再注册，注册后删临时文件；重复保存同名文件产生同一规范路径，天然 upsert。

#### 4.3.4 `screenpipe_live_view`

对 Live View 仪表盘做五种操作，由 `action` 分派。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `action` | enum：`list` / `get` / `save` / `pipes` / `values` | 是 | list 列仪表盘摘要；get 取完整可编辑定义；save 持久化完整定义；pipes 搜索已安装定时任务；values 看各 Block 当前渲染值 |
| `viewId` | string | get/values 必需 | Live View id，未知先 list |
| `blockId` | string | 否 | values 时看单块；缺省看全部 |
| `query` | string | 否 | pipes 的搜索词，匹配任务名与描述 |
| `view` | object | save 必需 | get 返回的完整定义加改动，须保留 id / revision / periodPolicy / 未改动的 Block |

Response：随 action 不同——list 为紧凑摘要数组；get 为完整定义；values 为 Block 渲染值预览（上限 12 块、每块 600 字符）；pipes 最多 24 条、描述截断 240 字符。

错误行为：业务校验失败抛出明确消息（如 `viewId is required for this action`、revision 非负整数校验），以可重试的工具错误回给模型。

#### 4.3.5 `screenpipe_live_view_propose`

提议 Live View 变更。契约写在 schema 里，违反处作为可重试错误返回，不被 App 静默纠正。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `note` | string | 是 | 一句话向用户说明可见变化；不得声称 operations 未做的改动 |
| `title` | string | 仅新建必填 | 新仪表盘标题 |
| `timeRange` | enum（today/24h/7d/30d） | 否 | 时间范围 |
| `timeRangeBehavior` | enum：selectable / fixed | 否 | 用户可切还是固定 |
| `blocks` | array | 新建必填 | 完整 Block 清单；每块含 component、width（3/6/12 栏）、intent、可选 pipeName |
| `operations` | array | 编辑必填 | 对已有仪表盘的定向修改；每项 `{op: add|update|remove, blockId?, block}` |

硬性互斥：`blocks` 与 `operations` 必须二选一，同时给或都不给都报错。

Response：格式化后的提案文本，供用户确认。

### 4.4 会话基建

#### 4.4.1 Pi 内置工具与会话矩阵

read / grep / find / ls / bash / edit / write 由 Pi 自带，schema 归 Pi 上游文档，此处不复刻。要点在可见性：chat 会话默认全开（含 bash 与写侧）；意图生成会话刻意收窄为只读内置件加白名单扩展工具；bash 在无人值守会话中等于周期性任意执行能力，收窄决策见 FEATURE_AGENT_CAPABILITY_SURFACE.md。

## 5. 特殊机制：sub-agent

`sub-agent.ts` 不是注册工具，而是 bash 命令拦截器：管道 agent 执行 `sub-agent run "prompt"` 时由扩展接管，spawn 子 Pi 进程并以输出作结果。仅 pipes 可用（pipe.md frontmatter 开 `subagent: true`）。安全栏：并发 ≤3、单次运行总数 ≤10、每个子任务 5 分钟超时、禁套娃（env 标记阻断递归）、父进程退出杀全部子进程。子 Pi 的模型请求独立记账为 direct-pi，语义见 CAPABILITY_SURFACE 第 7 节。

## 6. Skills 目录

Skill 教模型怎么用能力，本身不注册工具、不发请求、不能绕过白名单；模型要用 Skill 讲的能力，仍需会话里有 bash 或对应正式 Tool。当前基线三件：`screenpipe-api`（本地数据查询与媒体分析规则）、`screenpipe-cli`、`render-html-report`。用户自装 skills 以目录镜像方式进 chat 会话；意图生成会话的技能可见面与 Chat 对齐（2026-08-24 起，镜像剥离作废）。注意一个能力落差：screenpipe-api / screenpipe-cli 教的 curl 与命令执行在意图会话没有落地工具（无 bash、无发请求通道），这些技能在那里只是索引占位；对应的查证能力正以扩展工具形式补齐（§4.1）。各 Skill 正文见 `crates/screenpipe-core/assets/skills/*/SKILL.md`，本文不复述。

## 7. Agent 侧 HTTP 路由（集成必需子集）

鉴权统一为 `Authorization: Bearer <key>`，key 来自 `SCREENPIPE_LOCAL_API_KEY`（旧名 `SCREENPIPE_API_AUTH_KEY` 将弃用）；引擎全量路由的字段级规范在 `GET :3030/openapi.json` / `/openapi.yaml`，本文不复刻。`/activity-summary`、`/search`、`/memories`、`/meetings` 将成为 §4.1 数据查证类规划中工具的后端，落地时字段级细节以 openapi 为准并回填本节。

### `GET /intent-cards/recent`

| 参数 | 类型 | 缺省 | 说明 |
| --- | --- | --- | --- |
| `since_hours` | number | 48 | 回看小时数，夹取 0–744 |
| `limit` | integer | 20 | 上限数，夹取 1–100 |

响应 `{ cards: [{ id, origin, card_type, status, proactive_view, dedup_key, created_at }], generated_at }`，created_at 为 unixepoch 秒，cards 按 created_at 倒序。错误：500 带 `{"error"}`。

### `GET /mcp-servers` · `GET /mcp-servers/{id}/tools` · `POST /mcp-servers/{id}/call`

list 响应 `{ data: [{ id, name, url, enabled }] }`；tools 响应 `{ data: { tools: [{ name, description? }] } }`；call 请求体 `{ tool, arguments }`，响应 `{ data: { content: [...], isError?: bool } }`。

### `GET /connections`

响应 `{ data: [{ id, name?, connected?, mcp?, mcp_server_id?, icon?, category?, description? }] }`。

### `POST /artifacts/register`

请求体 `{ source, source_type, title, kind, file_path }`；file_path 指向服务器可达的文件（chat 场景是扩展写的会话临时文件）。响应含 `title` 与 `output_path`。

## 8. 环境变量速查

| 变量 | 谁读 | 用途 |
| --- | --- | --- |
| `SCREENPIPE_PORT` | 各扩展 | 本地 API 端口，缺省 3030 |
| `SCREENPIPE_LOCAL_API_URL` / `SCREENPIPE_LOCAL_API_PORT` | save-artifact、live-views、connection-gate | 显式覆盖 API 地址 |
| `SCREENPIPE_LOCAL_API_KEY`（旧名 `SCREENPIPE_API_AUTH_KEY`） | 各扩展 | Bearer 鉴权 |
| `SCREENPIPE_SESSION_ID` | mcp-bridge | 请求标记头 `x-screenpipe-session` |
| `SCREENPIPE_CHAT_SESSION_ID` | save-artifact | 会话级 upsert 键 |
| `SCREENPIPE_MCP_SERVER_ALLOWLIST` | mcp-bridge | 逗号分隔的服务 id 收窄可见集 |
| `SCREENPIPE_API_KEY` | web-search | Cue Cloud 搜索凭证 |
| `SCREENPIPE_SUBAGENT` | sub-agent | 值为 1 阻止递归 spawn |

## 9. 集成指南

### 9.1 给 Cue 新增一个工具

1. 在 `apps/screenpipe-app-tauri/src-tauri/assets/extensions/<name>.ts` 写扩展：`export default function (pi: ExtensionAPI)`，内部 `pi.registerTool({ name, label, description, parameters, execute })`。工具名带 `sp_` 前缀防与用户全局包撞名；description 决定模型何时触发，写清用途与禁区。
2. 注册安装：chat 全量工具进 `pi.rs` 的 `MANAGED_PI_EXTENSION_FILES`；会话专属工具走该会话的 ensure 安装函数（先例 `ensure_intent_card_extension`）。
3. 若目标会话设了白名单，把工具名加进对应常量（先例 `INTENT_ALLOWED_TOOLS`）。
4. 文件头加 provenance 注释；参数 schema 尽量内嵌完整契约，让协议层替你挡非法调用。
5. 回本文档补总表一行与逐工具小节（归入 §4 对应分组）；若属跨工具的使用学说，同步 cue-tools skill；架构级变化另同步 CAPABILITY_SURFACE。

### 9.2 把现有工具用进外部 Pi agent

1. 确认该扩展是自包含的：只依赖 fetch 与 env，不 import 应用代码。当前符合此标准的是 intent-card-recent.ts；web-search 依赖远程凭证，其余多数绑定本地路由但同样可用。
2. 整文件拷进目标 agent 的 `.pi/extensions/`（项目级）或全局扩展目录。
3. 设 env：`SCREENPIPE_PORT`（缺省 3030）、`SCREENPIPE_LOCAL_API_KEY`（引擎开了鉴权时必设）。
4. Cue 必须在运行，路由才存在；写侧工具（如 submit_intent_card）不在分发范围，模型侧没有 HTTP 写路径是刻意设计。

### 9.3 错误行为纪律

所有工具失败必须返回可修正的错误（状态码、原因、重试建议），不得伪装成成功结果；MCP 层的 `isError` 要前置警告。新增工具照此办理，验收判据见 CAPABILITY_SURFACE 第 10 节。

## 10. 变更检查表

| 改动 | 必须同步 |
| --- | --- |
| 改某工具的参数 schema | 本文档该工具的参数表；若契约被宿主解析（如 submit_intent_card ↔ parse.rs），两侧一起改 |
| 新增工具 | 总表、逐工具小节（归入对应分组）、所属会话白名单、受管安装清单、doc-covers |
| 改双通道分发文件（intent-card-recent.ts） | 受管源与全部外部分发副本（至少 `~/.pi/agent/extensions/`） |
| 动白名单机制 | 第 3 节矩阵与 CAPABILITY_SURFACE 的隔离论述 |
| 引擎路由参数变更 | openapi 自动跟随；仅当该路由是工具后端时同步本文对应行 |
| 改跨工具使用学说 | cue-tools skill（本文不复述学说内容，只管契约） |
| 规划中工具落地实现 | 总表与小节去掉「规划中」标记；新扩展文件名加进 doc-covers 并刷新 doc-verified |
