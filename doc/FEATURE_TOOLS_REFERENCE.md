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

| 工具 | 注册扩展 | 可见会话 | 性质 | 后端 |
| --- | --- | --- | --- | --- |
| `sp_web_search` | web-search.ts | chat 全量 | 读，出网 | Cue Cloud 搜索接口 |
| `sp_mcp_list_tools` | mcp-bridge.ts | chat 全量；intent 白名单 | 读 | 本地 `/mcp-servers` |
| `sp_mcp_call` | mcp-bridge.ts | chat 全量；intent 白名单 | **可能产生外部副作用** | 本地 `/mcp-servers/{id}/call` |
| `save_artifact` | save-artifact.ts | chat 全量 | 写入 Artifacts 库 | 本地 `/artifacts/register` |
| `screenpipe_live_view` | live-views.ts | chat 全量 | 读 / 写 Live View 定义 | 本地 live-views 路由族 |
| `screenpipe_live_view_propose` | live-views.ts | chat 全量 | 提议变更，schema 内校验 | 无网络调用，返回提案文本 |
| `screenpipe_list_connections` | connection-gate.ts | chat 全量 | 读 | 本地 `/connections` |
| `screenpipe_connect_app` | connection-gate.ts | chat 全量 | 发起用户授权流程（阻塞等待） | 授权 UI + 连接刷新 |
| `submit_intent_card` | intent-card.ts | 仅意图生成会话 | 受控交卡出口 | 无网络调用，宿主从 transcript 提取 |
| `get_recent_intent_cards` | intent-card-recent.ts | intent 白名单；可独立分发 | 只读 | 本地 `/intent-cards/recent` |
| Pi 内置七件（read/grep/find/ls/bash/edit/write） | Pi 自带 | 见第 3 节矩阵 | 视具体工具 | 本机文件系统 |

## 3. 会话矩阵

工具不是每个会话都能看到。Pi 不设 `allowedTools` 即默认全开，所以「收窄」必须显式配置：

| 会话 | 内置工具 | 扩展工具 |
| --- | --- | --- |
| Chat | 全量含 bash/edit/write | 上表 chat 全量各工具 |
| 意图卡片生成会话（session id `intent-card`） | 仅 read / grep / find / ls | `sp_mcp_list_tools`、`sp_mcp_call`、`submit_intent_card`、`get_recent_intent_cards`（八项白名单，常量 `INTENT_ALLOWED_TOOLS`） |
| 外部 Pi agent（用户自装） | 该 agent 自己的默认面 | 仅拷入的扩展文件（现例：intent-card-recent.ts） |

白名单机制：会话配置带 `allowedTools` 数组，Pi 只暴露名单内工具。意图会话另有两条隔离纪律：专属项目目录 `~/.screenpipe/pi-intent`，运行前清除带 `.screenpipe-managed` marker 的用户技能镜像（防无人值守定时任务执行任意导入指令）；bash 与一切写侧工具不进白名单。

## 4. 逐工具参考

每工具五段：用途与触发、参数、响应、错误行为、边界。参数表列类型、必填、含义；「必填」指 schema 的 required 或缺省即错。

### 4.1 `sp_web_search`

搜索公网内容。只在需要公开外部信息时用——时事、新闻、公开人物或公司、公开产品文档。禁止用于用户本地数据查询（那是本地 API 和 skills 的事）。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `query` | string | 是 | 搜索词 |

Response：text block，含搜索结果与来源列表。

错误行为：非 2xx 时返回 `Web search failed (<status>): <body>` 文本。边界：请求离开设备，走 Cue Cloud 凭证；工具名带 `sp_` 前缀是为避免与用户全局包撞名导致非交互运行中止（issue #3812）。

### 4.2 `sp_mcp_list_tools`

列出用户注册的 MCP 服务及其暴露的工具。调用 `sp_mcp_call` 前必须先调它拿 `server_id` 和工具名。设计为一对代理工具而非每工具注册一次，是为了省上下文（每服务省约 7-9%）并避开 Anthropic 单轮工具数上限。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `server_id` | string | 否 | 只列该服务；缺省列全部 |

Response：Markdown 文本，每服务一节，列 `{ name, description }`。无注册服务时提示去连接页添加。

错误行为：单个服务查询失败在对应小节标 `ERROR:`，不影响其他服务。边界：只列 `enabled !== false` 的服务；`SCREENPIPE_MCP_SERVER_ALLOWLIST` 环境变量可进一步收窄可见集。

### 4.3 `sp_mcp_call`

调用用户注册 MCP 服务上的一个工具。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `server_id` | string | 是 | 目标服务 id（来自 list_tools） |
| `tool` | string | 是 | 该服务声明的工具名 |
| `arguments` | object | 否 | 匹配目标工具 schema 的参数对象 |

Response：透传 MCP 的 `content` 数组（通常 text block）。若 MCP 结果 `isError: true`，返回前置警告行说明该工具执行失败——防止把错误当成功继续跑。

错误行为：HTTP 非 2xx 返回状态码与 body 前 800 字符。边界：可能产生外部副作用（发消息、建工单），权限与审计按外部调用对待。

### 4.4 `save_artifact`

把面向用户的最终产出（笔记、报告、摘要、清单、导出、代码文件）登记进 Artifacts 库。更新已有 artifact 也用它（同路径 upsert，不产生重复）。临时文件和中间产物不要用。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `filename` | string | 是 | 带扩展名的文件名，如 `weekly-summary.md`；路径分隔符与 `..` 会被清洗 |
| `content` | string | 是 | 完整文件内容 |
| `title` | string | 否 | Artifacts 库里的展示标题，缺省取文件名 |

Response：`Saved "<title>" to Artifacts (<output_path>)`。

错误行为：非 2xx 返回状态码与错误体。边界：仅文本类（md/html/json/txt/csv/tsv/ts 等，映射为 kind）；二进制注册是后续能力。写入走会话级临时目录再注册，注册后删临时文件；重复保存同名文件产生同一规范路径，天然 upsert。

### 4.5 `screenpipe_live_view`

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

### 4.6 `screenpipe_live_view_propose`

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

### 4.7 `screenpipe_list_connections`

列出应用连接及各自连接状态。对外部 app 做任何发送、推送、创建、读取之前先调它确认连通性。

参数：无。

Response：JSON 文本 `{ connections: [{ id, name, connected, connected_via, mcp, mcp_server_id, category, description, action_hint }] }`。`connected_via` 区分 mcp 与 connection_proxy，`action_hint` 告诉模型该走哪条路。Gmail 等纯 Composio 托管的连接即使没有原生条目也会合成出现。

错误行为：`isError: true` 加失败原因文本。

### 4.8 `screenpipe_connect_app`

任务依赖的外部 app 未连接时，发起内联授权请求并**阻塞等待用户操作**。用户拒绝前不得继续依赖该 app 的动作。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `connectionId` | string | 是 | 连接 id，如 linear、notion、github、google-docs |
| `reason` | string | 否 | 给用户看的、为什么现在要连的理由 |
| `requiredFor` | string | 否 | 连接后将继续的具体动作描述，拼进确认文案 |

Response：JSON 文本 `{ status: connected | declined | failed, connectionId, name, ... }`。已连接直接返回 connected；无 UI 环境返回 declined 附提示；用户取消视为 declined（干净拒绝，不算失败）；确认后刷新仍不在线则 failed 且 `isError: true`。执行模式为 sequential。

### 4.9 `submit_intent_card`

意图卡片生成的唯一交卡出口。参数 schema 内嵌完整卡片契约（oneOf 两分支），pi 在协议层做编译期校验，非法调用在 execute 之前被拒并把错误回灌给模型自纠。

参数（oneOf 二选一）：

分支一，普通卡：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `v` | integer，恒为 1 | 是 | 契约版本 |
| `card_type` | enum：light / side_effect / read_only | 是 | 卡片类型 |
| `proactive_view` | string | 否 | 给用户看的一句话引子 |
| `recommended_index` | integer ≥0 | 否 | 推荐方案下标 |
| `plans` | array 1–3 项 | 是 | 方案列表，每项 `{title*, summary*, consequence?}` |

分支二，材料不足：`{"insufficient_material": true}`。

Response：execute 只回执 `Intent card submitted.`——真正的载荷由宿主从会话 transcript 的最后一个 submit_intent_card 工具调用里提取（见 FEATURE_INTENT_CARDS.md 第 5 节）。此工具仅在 App 内意图会话安装，不经 HTTP，外部分发版不含。

### 4.10 `get_recent_intent_cards`

读取最近生成的意图卡片清单。主用途是判重：同一意图已有卡片或曾被拒就不要再产出同类卡。生成材料里通常已附带近 48 小时清单，本工具用于查更早历史。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `since_hours` | number | 否 | 往回看多少小时，默认 48（对齐过期时钟） |
| `limit` | integer | 否 | 最多几张，默认 20，最大 100 |

Response：每行一张卡的文本列表 `- #<id> [<card_type>/<status>] <proactive_view> (dedup_key=…, created_at=…)`；窗口内无卡时明说。

错误行为：HTTP 非 2xx 返回状态码与 body 前 400 字符。边界：这是双通道分发单源文件——App 内受管安装与外部分发副本（本机 `~/.pi/agent/extensions/`）必须同步更新；只依赖 fetch 和 env（`SCREENPIPE_PORT`、`SCREENPIPE_LOCAL_API_KEY`），对 App 零进程内依赖。

### 4.11 Pi 内置工具与会话矩阵

read / grep / find / ls / bash / edit / write 由 Pi 自带，schema 归 Pi 上游文档，此处不复刻。要点在可见性：chat 会话默认全开（含 bash 与写侧）；意图生成会话刻意只留四件只读件；bash 在无人值守会话中等于周期性任意执行能力，收窄决策见 FEATURE_AGENT_CAPABILITY_SURFACE.md。

## 5. 特殊机制：sub-agent

`sub-agent.ts` 不是注册工具，而是 bash 命令拦截器：管道 agent 执行 `sub-agent run "prompt"` 时由扩展接管，spawn 子 Pi 进程并以输出作结果。仅 pipes 可用（pipe.md frontmatter 开 `subagent: true`）。安全栏：并发 ≤3、单次运行总数 ≤10、每个子任务 5 分钟超时、禁套娃（env 标记阻断递归）、父进程退出杀全部子进程。子 Pi 的模型请求独立记账为 direct-pi，语义见 CAPABILITY_SURFACE 第 7 节。

## 6. Skills 目录

Skill 教模型怎么用能力，本身不注册工具、不发请求、不能绕过白名单；模型要用 Skill 讲的能力，仍需会话里有 bash 或对应正式 Tool。当前基线三件：`screenpipe-api`（本地数据查询与媒体分析规则）、`screenpipe-cli`、`render-html-report`。用户自装 skills 以目录镜像方式进 chat 会话；意图生成会话每次运行前剥离镜像只留基线。各 Skill 正文见 `crates/screenpipe-core/assets/skills/*/SKILL.md`，本文不复述。

## 7. Agent 侧 HTTP 路由（集成必需子集）

鉴权统一为 `Authorization: Bearer <key>`，key 来自 `SCREENPIPE_LOCAL_API_KEY`（旧名 `SCREENPIPE_API_AUTH_KEY` 将弃用）；引擎全量路由的字段级规范在 `GET :3030/openapi.json` / `/openapi.yaml`，本文不复刻。

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
5. 回本文档补总表一行与逐工具小节；架构级变化另同步 CAPABILITY_SURFACE。

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
| 新增工具 | 总表、逐工具小节、所属会话白名单、受管安装清单、doc-covers |
| 改双通道分发文件（intent-card-recent.ts） | 受管源与全部外部分发副本（至少 `~/.pi/agent/extensions/`） |
| 动白名单机制 | 第 3 节矩阵与 CAPABILITY_SURFACE 的隔离论述 |
| 引擎路由参数变更 | openapi 自动跟随；仅当该路由是工具后端时同步本文对应行 |
