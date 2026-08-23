# Wayfinder 地图 · 意图卡片落点（screenpipe fork）

Labels: wayfinder:map

## Destination

走到这张图的终点，「生成 + 展示」链路在这个 fork 上怎么落就定了：宿主形态、数据契约映射、展示挂点、模型供给、审批交互，每个决策都查得到它的票据，没定下来的 gap 也列成清单。图只产决策，不产实现代码；执行与终态链路不在本图。

## Notes

- 领域：macOS Tauri 桌面应用。仓库是本机个人 fork（`PisK4/screenpipe`，分支 `cue-branding`），身份为**自建项目**（登记进物证台账见票 T1），其结论按自建项目纪律引用，不当外部物证。
- **方向基调（用户定调）**：screenpipe fork 的工程架构已经成熟落地，是承载方和主要约束；意图卡片是从 Cue 档案里取出的想法，挑值得要的部分嵌进去。Cue 设计档案（`Agent开发/cue/`）是想法来源，不是必须逐条满足的合同——各票裁决取舍时引用出处（《04》主卡、《05》Intent Agent、《09》§3.1 表结构参照、《03》界面命名、《21》模型槽位、《11》《12》通道与记账），冲突时 fork 的现成机制优先。
- Cue 设计档案位于知识库 `Agent开发/cue/`：本 feature 对应《04-意图卡片》，Intent Agent 见《05-Agent-crew》，表结构参照《09-采集数据结构》§3.1，界面命名与呈现投影归《03-产品功能地图》，模型槽位归《21-模型与上下文供给》，通道边界与记账见《11》《12》。
- fork 侧开工前必读：根 `AGENTS.md` 与 `doc/` 下五份 Feature 合同（branding / i18n / local-first / agent capability surface / model invocation inventory）；改 Tauri command 前先调 `screenpipe-tauri` skill；JS/TS 一律 bun。
- 常规约束：用户可见文案全部走 i18n 字典并遵守 Cue 品牌边界；local-first 基线（默认本机 Ollama、无账户可用、不得引去登录页）。
- 在知识库写任何文档前调 `de-AI-writing` skill。
- 本图用本地 markdown 充当 tracker：`tickets/` 下每票一个文件；阻塞关系写在票内 `Blocked by` 行（无原生依赖关系可用的降级约定）；认领 = 把 `Claimed by` 填上。开票顺序：先建票文件，再回填阻塞边。

## Decisions so far

- [T1 · 登记物证台账](tickets/01-登记物证台账.md): screenpipe fork 以「自建项目的宿主检出」新节登记进台账（第八节），性质自建项目、锚定随分支演进、`wayfinder/` 是本仓研究产物。

- [T2 · fork 数据现状与合同生成输入的逐字段映射](tickets/02-数据映射调研.md): 近期活动/原始观察/聚合摘要路由可直接投影；三类记忆预算、执行账、持久摘要、触发变化量有基底缺口径；记账三件套、dedup 落库、记忆确认流、卡片两表完全缺件，全落 T4 建表范围。票面「accessibility 表」已过时，现行为 frames+elements+semantic_items+ui_events。
- [T4 · 数据契约落库方案](tickets/04-数据契约落库.md): intent_cards 十二列最小表定稿（origin 支持新手接入卡，兼任开发期测通链路的载具）；状态五值、本地自然日日界、dedup 简单拼接、expires_at 单列；重写流程与记账/确认流全套不进第一版；生成输入只用 fork 现成数据，不建记忆基底。
- [T3 · Intent Agent 宿主形态](tickets/03-宿主形态.md): 选定 Rust 侧心跳 + 单次直调（B 方案），节拍与出卡判据分离，心跳只拉增量信号过门槛；上下文累积即查询窗口增长，不建新存储；随采集引擎常驻（不要求主窗口打开）；新手卡走 Tauri command 旁路；质量不够时生成段可升级为 Pi 会话，其余层不动。（2026-08-23 修订：生成段改为 Pi 子进程会话随 v1 落地——只读工具白名单、仅基线三件 skills、终报沿用 `"v":1` 契约；心跳/门槛/落库/展示/状态机不动，详见票内修订记录。）
- [T5 · 展示挂点与卡片形态](tickets/05-展示挂点.md): 工作台落主窗口新增 section（照 activity/pipes 模式，不改 chat 首屏）；轻提示裁决面在工作台列表，到卡提醒复用 notification-panel 现成闸门；第一版只做待决定、已结束两个 Filter，执行中随执行链路补位；新手接入卡随第一版走。按钮组随执行链路后置收窄（接受只写终态不开 Thread）。
- [T8 · 审批交互与状态机实现](tickets/08-审批交互.md): 五值状态机照搬、转移收窄为四条；过期维持 T4 统一 48h（对《04》§3 轻提示免过期的有意偏离，理由在票面）；结算挂 T3 心跳节拍不建独立定时器；状态写入唯一入口是 src-tauri Tauri command；「有人动才重置」随重写砍掉而消解；快捷键不在本轮定义。
- [T7 · 模型供给与回退](tickets/07-模型供给.md): 两级回退——设置页新增 intent 槽（preset 选择器），空则回退发起时刻 chat 正用的 preset（充当 primary）；intent 槽默认内置 Ollama qwen3.5:9b，BYOK 引导不进第一版；失败记 tracing 加设置页可见状态，工作台不打扰，心跳下轮自然重试。（2026-08-23 修订：BYOK 引导提前进 v1——Pi 会话的多轮循环对本地小模型要求高；两级回退结构保留，实现载体换为 preset→PiProviderConfig 映射。）
- [T6 · 意图卡片 UI 原型](tickets/06-UI原型.md): 原型资产 `assets/t6-workbench-proto.html` 定稿。中性视觉对齐现有 tab（`#121212` 底、白底主按钮）；方案列表含推荐预选、选中显后果、末行「自己写一个新方案」；新手接入卡文案落到 `skills.rs` 的 MCP 注册真实机制上。
- [T9 · 现成功能可升级性盘点](tickets/09-现成功能盘点.md): 盘点结论——fork 无可直接升级为意图卡片的现成功能；Suggestions 最接近但产物形态/供给层/宿主语义/输出结构四处结构性不同，只作参考件（直调写法、UTF-8 截断纪律、模板回退），维持 T3/T4 新建决议。
- [T10 · 去重重设计：机械配额换软去重](tickets/10-软去重重设计.md): 作废 D2——删 `(dedup_key, local_date)` 唯一索引，判重改为模型对照预载的近 48h 卡片清单自行判断（rejected 卡不再被遗忘，同日不同意图不再误伤）；读侧单一事实源是引擎只读路由 `GET /intent-cards/recent`，`sp_intent_cards_recent` 扩展单文件可独立分发给外部 Pi agent；新手卡幂等改显式预检。顺带修复 supply 懒初始化击穿「跟随 Chat」与 mirror 上报漏面；D6–D9 补录归档。

## Not yet specified

- i18n 键清单：文案已在 T6 原型中定形，键名与字典接线归实现期，遵守 `doc/FEATURE_I18N_UI_LANGUAGE.md`。
- 测试与验收策略（browser-mock loop、src-tauri 显式测试路径）：等实现形态清晰。
- （T2 建议存档）Daily Summary 持久化有独立价值，若做另立小票；memories 类型扩展 ADR 与 semantic_items 对应裁决在「不建记忆基底」定调后对本 feature 不再必要。

本图九张票已全部 Resolved（2026-08-22）；2026-08-23 增补 T10（去重重设计，作废 D2），同样 Resolved。Destination 达成：每个决策可回溯到票据，剩余 gap 都在上面的清单或 Out of scope。

## Out of scope

- **执行与终态链路**：接受后应答通道交接、Workspace/cwd 锁定、信任演示审批、abort 语义、重跑与回看、保留期删数据的账处理、反馈账的规划消费。用户明示后置，将来另立 effort，本图不毕业。
- **重写流程**：T4 决议第一版不做（无 rewrite 列、铅笔编辑不入库），将来随执行链路 effort 一并重估。
- **记忆系统完整建设**：超出「最小基底」的部分不进本图；T4 已定生成输入不依赖任何记忆基底。
