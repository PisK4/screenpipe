# 意图卡片 v1（生成 + 展示链路）实现计划 · v3

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 screenpipe fork（品牌 Cue，分支 cue-branding）上落成意图卡片的完整「生成 → 落库 → 展示 → 裁决」链路：Rust 心跳驱动 Pi 子进程会话生成卡片，主窗口工作台 section 展示与裁决，notification-panel 提醒。

**Architecture:** 数据层新建 `intent_cards` 十二列表（screenpipe-db 迁移）；生成侧是 src-tauri 常驻 tokio 循环——每次醒来先结算过期，再拉增量信号过门槛，过门后经 localhost HTTP 取 activity-summary、按三级回退解析供给、起一个 Pi 子进程会话（只读工具白名单 + 仅基线 skills）生成方案 JSON，解析入库并推送事件与通知；展示侧是主窗口新增 workbench section，按钮只调 Tauri command 写状态。

**Tech Stack:** Rust（tokio / sqlx / reqwest / serde）、Tauri 2 + specta 绑定生成、Pi coding-agent 子进程（bun，`@earendil-works/pi-coding-agent@0.84.1`）、Next.js App Router + TypeScript（bun）、SQLite（sqlx migrate）、i18n 双字典。

**Spec:** `wayfinder/MAP.md`（决策地图）、`wayfinder/tickets/01` 至 `09`（T3/T7 含 2026-08-23 修订记录）、`wayfinder/draft/2026-08-23-意图卡片-feature-草案.md`（整体图景）。本计划从这些票出发；冲突时以票据为准。

**版本记录：** v1（2026-08-22）为单次直调方案，已被 T3 修订取代；v2 仅加修订横幅；**v3（2026-08-23）为当前唯一有效版本**——按 T3/T7 修订重写生成段（Task 3/4/5），并采纳外部审查（DeepSeek）全部高/中优先级发现（H1–H3、M1–M5 及低优先级勘误，处置见文末修订记录）。v3 全文自洽，无需对照 v1 阅读。

## Global Constraints

以下约束对每个任务隐式生效，值均抄自仓库约定、票据或补裁决：

- 每个新建或编辑的源码文件，头部加 provenance 注释（Rust/TS 用 `//`），内容照根 `AGENTS.md` 原文。
- JS/TS 一律 bun，禁 npm/pnpm；Rust 用 cargo。
- 用户可见文案全部走 i18n 字典：先加 en 键、补 zh 同构键，组件内不写内联文案；测试默认英文环境断言逐字原文（`doc/FEATURE_I18N_UI_LANGUAGE.md`）。
- 品牌边界：用户可见处写 Cue；代码标识符、数据路径、env 保留 `screenpipe` 命名（`doc/FEATURE_CUE_BRANDING.md`）。
- local-first 基线：无账户可用，不得引去登录页；**出厂默认供给是内置 `native-ollama` preset（qwen3.5:9b @ `http://localhost:11434/v1`），非空、随安装生效**（D8，对应 T7 决议 2 原文）；设置页另有 BYOK 引导（T7 修订）。
- 状态写入唯一入口是 src-tauri 的 Tauri command；前端不直接写库，模型/会话侧没有任何路径能写 `status`（T8 决议 4）。
- 状态机五值 `proposed/shown/accepted/rejected/expired`，v1 只生效四条转移：`proposed→shown`、`shown→accepted`、`shown→rejected`、`shown→expired`；过期时钟唯一写入点是 `mark_shown`，**仅对 `origin='proactive'` 写 `shown_at+48h`，新手卡永不过期**（D10，T5 决议 4）；重复 mark_shown 拒绝且绝不续命（R1）。
- 会话纪律（T3 修订 + D6/D7）：意图会话工具面只读白名单 `sp_mcp_list_tools,sp_mcp_call`，禁 bash 禁写侧；skills 仅基线集（screenpipe-api / screenpipe-cli / render-html-report），用户自装 skills 不进意图会话；会话失败不跨级降级供给，记 tracing 加设置页状态，心跳下轮重试。
- OCR/活动文本截断一律走 `screenpipe_core::strings::{safe_byte_prefix, truncate_string}`，生成相关模块文件头加 `#![deny(clippy::string_slice)]`（T9 参考件纪律）。
- 不建：重写流程、`rewrite_prev_card_id`/`adjust_opened_at` 列、记账三件套、记忆基底、执行链路、独立过期定时器、直调双路径回退、用户 skills 镜像、bash 工具（MAP Out of scope + T3 修订 + D6/D8）。
- UI 验证走 browser-mock 循环（`bun run dev:web`），不为 React/布局改动编 Tauri；跨原生边界才用 `bun run dev:tauri`。
- src-tauri 测试：先 `bun scripts/pre_build.js`，再 `cargo test --manifest-path apps/screenpipe-app-tauri/src-tauri/Cargo.toml <filter>`；构建会改写 tracked 的 `gen/schemas/`，事后 `git checkout -- apps/screenpipe-app-tauri/src-tauri/gen/schemas/`。
- 改 Tauri command 前调 skill `screenpipe-tauri`；改用户可见文案前读两份 branding/i18n 合同。
- git：never `git reset`，不删非自己写的代码；每任务一提交。

## 计划期补裁决（D1–D10）

票据留白或外部审查要求、本计划锁定的实现口径。D1–D5 承自 v1（D1 按 v3 语境微调表述），D6–D10 为 v3 新增：

| # | 裁决 | 内容 | 依据 |
| --- | --- | --- | --- |
| D1 | 回退镜像机制 | chat active preset 存在前端 localStorage（`lib/active-ai-preset.ts` 键 `chat-active-preset-id`），心跳在主窗口关闭时读不到。前端在**应用启动**与**`writeActiveAiPresetId` 调用时**两处把 preset id 经 command 写进 SettingsStore.extra 的 `intent_fallback_preset_id` 键（注意：aiPresets 本体在 store 顶层字段 `ai_presets`，不在 extra；extra 键读写走 store.rs 的 insert+save 模式）。心跳取用顺序：intent 槽 → 按 id 去 `ai_presets` 现查 → 内置 Ollama 默认。现查保证 preset 内容修改后天然新鲜。**语义偏离声明**：实际语义从 T7 票面「发起那一刻 chat 正用的 preset」变为「最近一次前端上报的 active preset」，有意为之，执行链路 effort 回收。 | T7 + T3 常驻语义 + 评审 R3 + 审查 M3-2 |
| D2 | dedup_key 口径 | `{card_type}:{dominant_app}`；dominant_app 取 activity-summary 响应 `apps` 数组（按 minutes 降序）首位的 `name`，缺省 `general`。unique(dedup_key, local_date) 编码「每 app 每类型每天最多一张」的产品策略。 | T4 决议 7 + 评审 R8 + 审查 M5 |
| D3 | 心跳节拍常量 | 间隔 900s，首轮延迟 120s；信号门槛：窗口内 app_switch+window_focus ≥ 3 或 frames hash 变化 ≥ 5；材料查询窗口上限 MAX_WINDOW_SECS = 7 天。常量集中在 gate.rs 顶部。 | T3 决议 3 + 评审 R2 |
| D4 | plans_json 结构 | 所有形态带版本字段 `"v": 1`。普通卡：`{"v":1,"recommended_index":0,"plans":[{"title","summary","consequence"}]}`；新手接入卡：`{"v":1,"kind":"onboarding_mcp","detected_agents":[...]}`。解析器先看 `v`，未知版本直接报错；GeneratedPlan serde 默认宽容未知字段。 | T6 + 评审 R4 |
| D5 | 新手卡接受语义 | 「接入」= 写 accepted 终态 + 调 skills.rs 现成的 `connect_detected_ai_tools_in_background(api_auth_enabled: bool, api_port: u16)`，失败记 tracing 不回滚状态。全计划唯一 accept 触发副作用的路径，执行链路 effort 时统一。 | T6 + T5 收窄 + 评审 R6 |
| D6 | 会话编排契约 | session_id 固定 `"intent-card"`；project_dir 固定 `~/.cue/pi-intent`（独占，不与 chat/daily-summary 共享）；工具白名单 `["sp_mcp_list_tools","sp_mcp_call"]`（经 PiProviderConfig.allowedTools → `--tools` 逗号 join，`apply_pi_tool_allowlist` pi.rs L1904-1919）；会话总超时 240s；终报 settle 条件 = `agent_end` 且非 willRetry；每次跑完 `pi_stop`（资源可预期，spawn 频率受门槛约束）；终报文本收集走进程内 `app.listen("agent_event")` 过滤 sessionId（仓内先例 `commands/native_actions.rs` L100 的 `app_handle.listen`），**不改 pi.rs 的 stdout reader 热路径**。 | T3 修订 + 审查 H2 频率关切 |
| D7 | skills 隔离口径 | 复用 `ensure_screenpipe_skill(project_dir)`（core 会动态渲染 api skill），随后遍历 `<project_dir>/.pi/skills/` 删除含 marker 文件 `.screenpipe-managed`（core 私有 const，字面量稳定，core agents/pi.rs L806）的目录——用户镜像不进意图会话。安全性建立在 D6 的独占 project_dir 上：marker 清理只影响意图会话自己的目录。 | T3 修订第 4 条 + 侦察第 6 节 |
| D8 | 供给默认与降级语义（审查 H3 采纳） | **intent 槽出厂默认非空**：内置 `native-ollama` preset（provider `native-ollama`、url `http://localhost:11434/v1`、model `qwen3.5:9b`、无 key），随首次 `intent_get_supply` 惰性写入 extra 的 `intent_slot` 键；「跟随 Chat」是用户显式选项（写 slot=None → 走 mirror）。三级解析 slot→mirror→builtin 只做**配置解析**，不做运行时跨级降级：某级会话失败即本轮失败，记设置页，不自动换下一级重跑（避免一次 tick 双会话成本）。此为对「无账户也能出卡」的兑现口径：出厂默认就在本机 Ollama 上，不依赖回退链。 | T7 决议 2 原文 + T7 修订 + 审查 H3 |
| D9 | 尝试锚定与 dedup 静默（审查 H2 采纳） | 信号计数窗口锚到**最后一次生成尝试**（extra `intent_last_generation.at` 时间戳，任何结局都更新），不再锚到最后插入——杜绝 insufficient_material / 解析失败 / dedup 命中导致的门槛常开与每 15 分钟无退避重试。`insert_intent_card` 返回 `InsertOutcome::{Inserted,DedupHit}`；DedupHit 时**跳过 emit 与通知**，GenerationRecord 记 `detail:"dedup hit"`。材料查询窗口仍锚最后插入（材料跨失败尝试累积，R2 封顶不变）。 | 审查 H2 + R2 |
| D10 | 过期时钟归属（审查 H1 采纳） | `expires_at` 唯一写入点是 `mark_shown`，且仅当 `origin='proactive'` 时写 `now+CARD_TTL_SECS`，`system_onboarding` 保持 NULL；`NewIntentCard` 不再携带 expires_at 字段（insert 一律 NULL），消除与 mark_shown 的职责重叠。`expire_due` 天然跳过 NULL（SQL `expires_at IS NOT NULL` 守卫）。 | 审查 H1 + T5 决议 4 |

**Schema 备忘**：`card_type`/`status` 的 CHECK 约束保留（T4 决议 4：多留一个值比日后 rebuild 迁移便宜）；将来加值走 rebuild 迁移，fork 先例在 activity_ledger。

---

### Task 1: intent_cards 表与数据访问层

**Files:**
- Create: `crates/screenpipe-db/src/migrations/20260822120000_create_intent_cards.sql`
- Create: `crates/screenpipe-db/src/db/intent_cards.rs`
- Modify: `crates/screenpipe-db/src/db/mod.rs`（注册模块）

**Interfaces:**
- Consumes: sqlx migrate 宏（`crates/screenpipe-db/src/db/setup.rs` L429-430 已有 `migrate!("./src/migrations")`）；`DatabaseManager` 有 `pub pool: SqlitePool`（`db/mod.rs` L297），自由函数吃 `&SqlitePool` 可行。
- Produces（后续任务依赖的确切签名，`db/mod.rs` re-export）:

```rust
pub struct IntentCardRow {
    pub id: i64, pub origin: String, pub card_type: String, pub status: String,
    pub proactive_view: Option<String>, pub dedup_key: String, pub local_date: String,
    pub plans_json: String, pub model_id: Option<String>,
    pub shown_at: Option<i64>, pub expires_at: Option<i64>, pub created_at: i64,
}
pub struct NewIntentCard { // D10：无 expires_at 字段，insert 一律 NULL
    pub origin: String, pub card_type: String, pub proactive_view: Option<String>,
    pub dedup_key: String, pub local_date: String, pub plans_json: String,
    pub model_id: Option<String>,
}
#[derive(Debug, PartialEq)] // D9：区分新插入与 dedup 命中
pub enum InsertOutcome { Inserted(i64), DedupHit(i64) }
impl InsertOutcome { pub fn id(&self) -> i64; pub fn is_new(&self) -> bool; }

pub async fn insert_intent_card(pool: &SqlitePool, card: &NewIntentCard) -> Result<InsertOutcome, sqlx::Error>;
pub async fn list_pending(pool: &SqlitePool) -> Result<Vec<IntentCardRow>, sqlx::Error>;   // status IN ('proposed','shown')
pub async fn list_accepted(pool: &SqlitePool) -> Result<Vec<IntentCardRow>, sqlx::Error>;
// D10：expires_at 唯一写入点；仅 proactive 写 now+48h，onboarding 保持 NULL。
// 仅允许 proposed→shown 单向；重复调用返回 false 且绝不改写 shown_at/expires_at（R1）。
pub async fn mark_shown(pool: &SqlitePool, id: i64, now: i64) -> Result<bool, sqlx::Error>;
pub async fn finish(pool: &SqlitePool, id: i64, terminal: &str) -> Result<bool, sqlx::Error>; // 仅 accepted/rejected，WHERE status='shown'
pub async fn expire_due(pool: &SqlitePool, now: i64) -> Result<u64, sqlx::Error>;
pub async fn latest_created_at(pool: &SqlitePool) -> Result<Option<i64>, sqlx::Error>;
// 时间参数用 chrono 类型，与参考件 get_frames_in_range_for_export（search.rs L1563，DateTime<Utc> + sqlx chrono 编码）同款，不传字符串（审查低-3）：
pub async fn count_ui_events_since(pool: &SqlitePool, since: chrono::DateTime<chrono::Utc>) -> Result<i64, sqlx::Error>;  // event_type IN ('app_switch','window_focus')
pub async fn count_frame_changes_since(pool: &SqlitePool, since: chrono::DateTime<chrono::Utc>) -> Result<i64, sqlx::Error>;
```

- [ ] **Step 1: 写迁移文件**

`20260822120000_create_intent_cards.sql`，DDL 抄 T4 决议原文（该时间戳排在现有最新迁移 `20260818133000` 之后，已核）：

```sql
CREATE TABLE intent_cards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  origin TEXT NOT NULL CHECK (origin IN ('proactive','system_onboarding')),
  card_type TEXT NOT NULL CHECK (card_type IN ('light','side_effect','read_only')),
  status TEXT NOT NULL DEFAULT 'proposed'
    CHECK (status IN ('proposed','shown','accepted','rejected','expired')),
  proactive_view TEXT,
  dedup_key TEXT NOT NULL,
  local_date TEXT NOT NULL,
  plans_json TEXT NOT NULL,
  model_id TEXT,
  shown_at INTEGER,
  expires_at INTEGER,
  created_at INTEGER NOT NULL DEFAULT (unixepoch())
);
CREATE UNIQUE INDEX idx_intent_cards_dedup ON intent_cards(dedup_key, local_date);
```

- [ ] **Step 2: 写数据访问层失败测试**

新建 `db/intent_cards.rs`。测试建池：内存池 + 跑迁移（注意：`write_queue.rs` 测试只建池**没有** migrate!，迁移步骤是本计划自加的正确步骤，勿照抄它的表述——审查低-4）：

```rust
#[cfg(test)]
async fn test_pool() -> sqlx::SqlitePool {
    let pool = sqlx::SqlitePool::connect("sqlite::memory:").await.unwrap();
    sqlx::migrate!("./src/migrations").run(&pool).await.unwrap();
    pool
}

fn sample_card() -> NewIntentCard { // origin proactive
    NewIntentCard {
        origin: "proactive".into(), card_type: "light".into(),
        proactive_view: Some("你似乎在反复切换".into()),
        dedup_key: "light:VSCode".into(), local_date: "2026-08-23".into(),
        plans_json: r#"{"v":1,"recommended_index":0,"plans":[]}"#.into(),
        model_id: None,
    }
}

#[tokio::test]
async fn mark_shown_sets_expiry_and_finish_only_from_shown() {
    let pool = test_pool().await;
    let id = insert_intent_card(&pool, &sample_card()).await.unwrap().id();
    assert!(mark_shown(&pool, id, 1_000_000).await.unwrap());
    let row = list_pending(&pool).await.unwrap().into_iter().next().unwrap();
    assert_eq!(row.status, "shown");
    assert_eq!(row.expires_at, Some(1_000_000 + 48 * 3600));
    assert!(finish(&pool, id, "accepted").await.unwrap());
    assert!(!finish(&pool, id, "rejected").await.unwrap()); // 终态不可再转
}

#[tokio::test]
async fn repeated_mark_shown_never_extends_expiry() { // R1
    let pool = test_pool().await;
    let id = insert_intent_card(&pool, &sample_card()).await.unwrap().id();
    assert!(mark_shown(&pool, id, 1_000_000).await.unwrap());
    assert!(!mark_shown(&pool, id, 99_000_000).await.unwrap());
    let row = list_pending(&pool).await.unwrap().into_iter().next().unwrap();
    assert_eq!(row.shown_at, Some(1_000_000));
    assert_eq!(row.expires_at, Some(1_000_000 + 48 * 3600)); // 时钟未被续命
}

#[tokio::test]
async fn onboarding_card_never_gets_expiry() { // H1 / D10
    let pool = test_pool().await;
    let mut card = sample_card();
    card.origin = "system_onboarding".into();
    card.dedup_key = "system_onboarding:onboarding".into();
    let id = insert_intent_card(&pool, &card).await.unwrap().id();
    assert!(mark_shown(&pool, id, 1_000_000).await.unwrap());
    let row = list_pending(&pool).await.unwrap().into_iter().next().unwrap();
    assert_eq!(row.status, "shown");
    assert_eq!(row.expires_at, None); // 48h 后不得被 expire_due 结算
    assert_eq!(expire_due(&pool, 99_999_999_999).await.unwrap(), 0);
}

#[tokio::test]
async fn dedup_hit_returns_existing_id_and_is_flagged() { // D9
    let pool = test_pool().await;
    let first = insert_intent_card(&pool, &sample_card()).await.unwrap();
    let second = insert_intent_card(&pool, &sample_card()).await.unwrap();
    assert!(matches!(first, InsertOutcome::Inserted(_)));
    assert!(matches!(second, InsertOutcome::DedupHit(id) if id == first.id()));
}
```

同文件再加两个测试：`expire_due` 只结算 `expires_at <= now` 且仍 `shown` 的卡（插入两张，一张过期一张未到，断言只结算一张）；`finish` 对 `status='proposed'` 的卡返回 false。先跑确认编译失败。

- [ ] **Step 3: 实现**

逐函数实现到测试全绿。要点：

- `mark_shown` 单条 UPDATE，用 CASE 区分 origin（D10）：

```sql
UPDATE intent_cards SET status='shown', shown_at=?2,
  expires_at = CASE WHEN origin='proactive' THEN ?2 + 172800 ELSE expires_at END
WHERE id=?1 AND status='proposed'
```

- `finish`：UPDATE 带 `WHERE status='shown'`，受影响 0 行返回 false。
- `insert_intent_card`：INSERT 后按受影响行数/查询冲突区分 `Inserted` / `DedupHit`（可用 `INSERT OR IGNORE` + last_insert_rowid==0 判命中，或先 SELECT 再插，二选一，测试说了算）。
- 时间格式：`intent_cards` 自身列是 INTEGER unixepoch（`Utc::now().timestamp()`）；`count_*_since` 的 `ui_events.timestamp` / `frames.timestamp` 是 DATETIME 文本列，bind `DateTime<Utc>` 让 sqlx chrono 编码 RFC3339——先读 `crates/screenpipe-db/src/db/search.rs` 的 `get_frames_in_range_for_export`（约 L1563）确认 bind 写法再落码，不要传 unix 秒。

- [ ] **Step 4: 注册模块**

`db/mod.rs` 在 `mod memories;` 一组里插 `mod intent_cards;`，文件尾 `pub use self::intent_cards::{...};` 列出 Interfaces 全部公开项，风格与相邻 `pub use self::semantic::{...};` 一致。

- [ ] **Step 5: 跑测试**

```bash
cargo test -p screenpipe-db intent_cards
```

Expected: 全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add crates/screenpipe-db/src/migrations/20260822120000_create_intent_cards.sql \
        crates/screenpipe-db/src/db/intent_cards.rs crates/screenpipe-db/src/db/mod.rs
git commit -m "feat(db): add intent_cards table and data access layer"
```

---

### Task 2: intent_agent 纯逻辑（gate / parse / instruct）

**Files:**
- Create: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/mod.rs`
- Create: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/gate.rs`
- Create: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/parse.rs`
- Create: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/instruct.rs`（v1 的 prompt.rs 演化：直调 messages 构造改为会话指令构造）
- Modify: `apps/screenpipe-app-tauri/src-tauri/src/main.rs`（声明模块）

**Interfaces:**
- Consumes: 无外部依赖，全部纯函数。
- Produces（Task 4/6 依赖）:

```rust
// mod.rs（文件头 #![deny(clippy::string_slice)] 加在各子文件）
pub mod gate; pub mod parse; pub mod instruct;
pub struct WindowSignals { pub app_switches: i64, pub frame_changes: i64 }
pub struct GenerationInput {
    pub window_start_text: String, pub window_end_text: String,
    pub activity_summary: serde_json::Value, pub signals: WindowSignals,
}

// gate.rs
pub const HEARTBEAT_INTERVAL_SECS: u64 = 900;
pub const FIRST_RUN_DELAY_SECS: u64 = 120;
pub const MIN_APP_SWITCH_EVENTS: i64 = 3;
pub const MIN_FRAME_CHANGES: i64 = 5;
pub const CARD_TTL_SECS: i64 = 48 * 3600;
pub const DEFAULT_WINDOW_SECS: i64 = 24 * 3600;
pub const MAX_WINDOW_SECS: i64 = 7 * 24 * 3600;
pub fn should_attempt_generation(s: &WindowSignals) -> bool;          // 两信号 OR
pub fn dedup_key(card_type: &str, dominant_app: &str) -> String;      // "{type}:{app|general}"
pub fn window_start(now: i64, latest_card_at: Option<i64>) -> i64;    // 材料窗：锚最后插入，封顶 7d（R2）
pub fn signal_window_start(now: i64, last_attempt_at: Option<i64>) -> i64; // D9：信号窗：锚最后尝试，同样封顶
pub fn dominant_app(summary: &serde_json::Value) -> String;           // D2/M5：summary["apps"][0]["name"]，缺省 "general"

// parse.rs（与 v1 逐字相同，解析对象从直调响应变为会话终报，契约不变）
pub struct GeneratedPlan { pub title: String, pub summary: String, #[serde(default)] pub consequence: String }
pub struct GeneratedCard { pub card_type: String, pub proactive_view: String, pub recommended_index: usize, pub plans: Vec<GeneratedPlan> }
pub enum ModelOutcome { Card(GeneratedCard), InsufficientMaterial }
pub fn parse_model_output(raw: &str) -> Result<ModelOutcome, String>;

// instruct.rs
pub fn build_system_prompt() -> String;                    // 会话 system 指令（进 PiProviderConfig.systemPrompt）
pub fn build_user_payload(input: &GenerationInput) -> String; // 单条 user 消息：窗口文本 + 信号 + 截断后的 summary JSON
```

- [ ] **Step 1: 写 gate.rs 失败测试**

```rust
#[test]
fn threshold_passes_on_either_signal() {
    assert!(!should_attempt_generation(&WindowSignals { app_switches: 0, frame_changes: 0 }));
    assert!(should_attempt_generation(&WindowSignals { app_switches: 3, frame_changes: 0 }));
    assert!(should_attempt_generation(&WindowSignals { app_switches: 0, frame_changes: 5 }));
}
#[test]
fn dedup_key_combines_type_and_app() {
    assert_eq!(dedup_key("light", "VSCode"), "light:VSCode");
    assert_eq!(dedup_key("light", ""), "light:general");
}
#[test]
fn window_start_is_capped() { // R2
    let now = 10_000_000_000_i64;
    assert_eq!(window_start(now, None), now - DEFAULT_WINDOW_SECS);
    assert_eq!(window_start(now, Some(now - 90 * 24 * 3600)), now - MAX_WINDOW_SECS);
    assert_eq!(window_start(now, Some(now - 3600)), now - 3600);
}
#[test]
fn signal_window_anchors_to_last_attempt_and_caps() { // D9
    let now = 10_000_000_000_i64;
    assert_eq!(signal_window_start(now, None), now - DEFAULT_WINDOW_SECS);
    assert_eq!(signal_window_start(now, Some(now - 600)), now - 600); // 上次尝试 10 分钟前：只数增量
    assert_eq!(signal_window_start(now, Some(now - 90 * 24 * 3600)), now - MAX_WINDOW_SECS);
}
#[test]
fn dominant_app_reads_first_app_or_falls_back() { // M5
    let summary = serde_json::json!({ "apps": [ {"name": "VSCode", "minutes": 42}, {"name": "Slack", "minutes": 3} ] });
    assert_eq!(dominant_app(&summary), "VSCode");
    assert_eq!(dominant_app(&serde_json::json!({ "apps": [] })), "general");
    assert_eq!(dominant_app(&serde_json::json!({})), "general");
}
```

Run: `bun scripts/pre_build.js && cargo test --manifest-path apps/screenpipe-app-tauri/src-tauri/Cargo.toml intent_agent::gate`
Expected: 编译失败（函数未定义）。后续纯逻辑任务的测试先行步骤相同，不再重复写 Expected。

- [ ] **Step 2: 实现 gate.rs**

常量按 Interfaces 原文；`should_attempt_generation` 为两个 OR；`dedup_key` 空 app 归 `general`；`window_start = max(latest_card_at.unwrap_or(now - DEFAULT_WINDOW_SECS), now - MAX_WINDOW_SECS)`；`signal_window_start = max(last_attempt_at.unwrap_or(now - DEFAULT_WINDOW_SECS), now - MAX_WINDOW_SECS)`。

`dominant_app` 实现（M5：activity-summary 响应无 dominant_app 字段，首位 app 在 `apps[0].name`，响应按 minutes 降序——落码前用 `rg -n "pub struct AppUsage|apps" crates/screenpipe-engine/src/routes/activity_summary.rs` 核对字段名与排序注释，若实际字段名不同以路由结构体为准并同步本测试）：

```rust
pub fn dominant_app(summary: &serde_json::Value) -> String {
    summary["apps"][0]["name"].as_str().unwrap_or("general").to_string()
}
```

- [ ] **Step 3: 写并实现 parse.rs**

```rust
pub fn parse_model_output(raw: &str) -> Result<ModelOutcome, String> {
    let stripped = raw.trim().trim_start_matches("```json").trim_start_matches("```")
        .trim_end_matches("```").trim();
    let v: serde_json::Value = serde_json::from_str(stripped).map_err(|e| e.to_string())?;
    if v.get("insufficient_material") == Some(&serde_json::Value::Bool(true)) {
        return Ok(ModelOutcome::InsufficientMaterial);
    }
    match v.get("v").and_then(|x| x.as_i64()) {
        Some(1) => {}
        _ => return Err("missing or unsupported plans_json version".into()), // D4
    }
    let card: GeneratedCard = serde_json::from_value(v).map_err(|e| e.to_string)?;
    if card.plans.is_empty() { return Err("empty plans".into()); }
    if !matches!(card.card_type.as_str(), "light" | "side_effect" | "read_only") {
        return Err(format!("bad card_type {}", card.card_type));
    }
    Ok(ModelOutcome::Card(card))
}
```

测试覆盖：围栏剥离、`insufficient_material:true` 分支、缺 `v` 或 `v!=1` 报错、空 plans 报错、非法 card_type 报错、正常解析 recommended_index、未知额外字段不报错。

- [ ] **Step 4: 写并实现 instruct.rs**

`build_system_prompt()`：角色说明（你在为一位 macOS 用户的本地活动生成主动式意图卡片）；可用工具说明（只读白名单，鼓励用 sp_mcp_call 查证材料后再下结论）；输出契约——最终回复必须是单个 JSON 对象、顶层带 `"v": 1`、结构 `{"v":1,"recommended_index":0,"plans":[{"title","summary","consequence"}]}`、plans 1–3 项首项为推荐；三种 card_type 定义（light/side_effect/read_only）；材料不足时最终回复 `{"insufficient_material": true}`；禁止输出 JSON 以外的任何文字。

`build_user_payload(input)`：JSON 文本含 `window_start`/`window_end`（ISO 文本）、`signals`（两个计数）、`activity_summary`（超长先 `truncate_string(&raw, 12_000)`，文件头 `#![deny(clippy::string_slice)]`）。

测试：system prompt 含 `"v": 1`、`insufficient_material`、三种 card_type 字样；user payload 含窗口起止文本与信号计数。

- [ ] **Step 5: main.rs 声明模块**

crate 根作用域加 `mod intent_agent;`（与 `mod suggestions;` 相邻）。

- [ ] **Step 6: 跑测试**

```bash
cargo test --manifest-path apps/screenpipe-app-tauri/src-tauri/Cargo.toml intent_agent
git checkout -- apps/screenpipe-app-tauri/src-tauri/gen/schemas/
```

- [ ] **Step 7: Commit**

```bash
git add apps/screenpipe-app-tauri/src-tauri/src/intent_agent apps/screenpipe-app-tauri/src-tauri/src/main.rs
git commit -m "feat(intent-agent): add capped gates, versioned parser, and session instruction builder"
```

---

### Task 3: 供给解析（slot / mirror / builtin 三级）

**Files:**
- Create: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/supply.rs`
- Modify: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/mod.rs`（`pub mod supply;`）

**Interfaces:**
- Consumes: `crate::pi::PiProviderConfig`（pi.rs L1811-1845，serde camelCase：`provider/url/model/apiKey/maxTokens/systemPrompt/allowedTools` 等全字段）；SettingsStore 顶层 `ai_presets` 字段（store.rs L938-939，serde rename `aiPresets`）与 extra 键读写模式（store.rs L2112-2121 insert+save；读入口先例 `notifications/gate.rs` 的 `load_guard`）。
- Produces:

```rust
#[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize, specta::Type)]
#[serde(rename_all = "camelCase")]
pub struct PresetQuadruple { pub provider: String, pub url: String, pub model: String, pub api_key: Option<String> }
// provider 取值域照 AIPreset：openai | anthropic | native-ollama | custom（Pi 侧原样透传，先例 lib/daily-summary-pi.ts buildDailySummaryProviderConfig）

pub fn builtin_default() -> PresetQuadruple; // D8：native-ollama / http://localhost:11434/v1 / qwen3.5:9b / None
pub fn to_provider_config(q: &PresetQuadruple) -> crate::pi::PiProviderConfig; // 直通映射，max_tokens 4096 默认，其余 Option 字段留空
pub async fn read_supply(app: &tauri::AppHandle) -> (Option<PresetQuadruple>, Option<String>); // (extra intent_slot, extra intent_fallback_preset_id)
pub async fn resolve_mirror_preset(app: &tauri::AppHandle, preset_id: &str) -> Option<PresetQuadruple>; // 顶层 ai_presets 按 id 现查（D1，已核实 Rust 可读）
pub fn resolve_chain(slot: Option<PresetQuadruple>, mirror: Option<PresetQuadruple>) -> (crate::pi::PiProviderConfig, &'static str); // "slot"|"mirror"|"builtin"，只解析不降级（D8）
```

- [ ] **Step 1: 写 resolve_chain 与映射的失败测试**

```rust
#[test]
fn chain_prefers_slot_then_mirror_then_builtin() {
    let slot = PresetQuadruple { provider: "openai".into(), url: "https://api.openai.com/v1".into(), model: "gpt-4o".into(), api_key: Some("k".into()) };
    let mirror = builtin_default();
    let (cfg, tag) = resolve_chain(Some(slot.clone()), Some(mirror.clone()));
    assert_eq!(tag, "slot"); assert_eq!(cfg.model, "gpt-4o");
    let (cfg, tag) = resolve_chain(None, Some(mirror.clone()));
    assert_eq!(tag, "mirror"); assert_eq!(cfg.provider, "native-ollama");
    let (cfg, tag) = resolve_chain(None, None);
    assert_eq!(tag, "builtin"); assert_eq!(cfg.model, "qwen3.5:9b");
}
#[test]
fn to_provider_config_passes_fields_through() {
    let q = PresetQuadruple { provider: "anthropic".into(), url: "https://api.anthropic.com".into(), model: "claude-sonnet-4".into(), api_key: Some("k".into()) };
    let cfg = to_provider_config(&q);
    assert_eq!(cfg.provider, "anthropic");
    assert_eq!(cfg.url, "https://api.anthropic.com");
    assert_eq!(cfg.model, "claude-sonnet-4");
    assert_eq!(cfg.api_key.as_deref(), Some("k"));
    assert!(cfg.allowed_tools.is_none()); // 白名单由 session 层挂，supply 不带（D6）
    assert!(cfg.system_prompt.is_none());
}
```

Run: `cargo test --manifest-path apps/screenpipe-app-tauri/src-tauri/Cargo.toml intent_agent::supply`（先 pre_build），Expected: 编译失败。

- [ ] **Step 2: 实现 extra 读写与三级解析**

- extra 读写照 store.rs L2112-2121 的 insert+save 模式封装两个私有 helper（`extra_get(app,key)->Option<Value>` / `extra_set(app,key,value)`）；`read_supply` 反序列化 `intent_slot` / `intent_fallback_preset_id` 两键。
- `resolve_mirror_preset`：`SettingsStore::get(app)?.ai_presets`（顶层字段，已核实可读）线性找 id 匹配项，映射成 `PresetQuadruple{provider,url,model,api_key}`（字段名以 store.rs 的 AIPreset serde 名为准，落码前 `rg -n "struct AiPreset|ai_presets" crates/screenpipe-app-tauri/src-tauri/src/store.rs | head` 核对）。
- `builtin_default()` 按 D8 常量；`to_provider_config` 直通 + `max_tokens: 4096`（PiProviderConfig 的 serde 默认同值）。
- `resolve_chain` 纯函数，顺序 slot → mirror → builtin，不降级（D8）。

- [ ] **Step 3: 跑测试并提交**

```bash
bun scripts/pre_build.js
cargo test --manifest-path apps/screenpipe-app-tauri/src-tauri/Cargo.toml intent_agent::supply
git checkout -- apps/screenpipe-app-tauri/src-tauri/gen/schemas/
git add apps/screenpipe-app-tauri/src-tauri/src/intent_agent
git commit -m "feat(intent-agent): add three-level supply chain resolving to PiProviderConfig"
```

---

### Task 4: Pi 会话编排（终报收集 + 白名单 + skills 隔离）

**Files:**
- Create: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/session.rs`
- Modify: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/mod.rs`（`pub mod session;`）

**Interfaces:**
- Consumes: `crate::pi::pi_start_inner`（pi.rs L2474，pub，跨模块调用先例 `e2e/commands.rs` L671-687）、`crate::pi::pi_prompt`（pi.rs L3909，pub command 函数可直接调，`State<PiState>` 经 `app.state::<PiState>()` 获取）、`crate::pi::pi_stop`（L2247）、`crate::pi::ensure_screenpipe_skill` 包装（pi.rs L1588-1592）；`app.listen` 进程内事件监听（先例 `commands/native_actions.rs` L100）；事件 payload 形状 `{"source":"pi","sessionId":sid,"event":...}`（pi.rs `emit_agent_event` L141-152）。
- Produces:

```rust
pub const INTENT_SESSION_ID: &str = "intent-card";
pub const SESSION_TIMEOUT_SECS: u64 = 240; // D6
pub const INTENT_ALLOWED_TOOLS: [&str; 2] = ["sp_mcp_list_tools", "sp_mcp_call"]; // D6 只读白名单
pub fn intent_project_dir() -> std::path::PathBuf; // default_screenpipe_data_dir().join("pi-intent")，先例 pi.rs L5218 的 pi-chat
// 跑一轮会话，返回会话终报文本（parse_model_output 的输入）。
pub async fn run_intent_session(
    app: &tauri::AppHandle,
    base_config: crate::pi::PiProviderConfig, // supply 层产出；本函数挂 systemPrompt 与 allowedTools
    system_prompt: String,
    user_message: String,
) -> Result<String, String>;
// 纯 helper，供测试：
fn extract_text_delta(event: &serde_json::Value) -> Option<String>; // text_delta / message_update 两条路径
fn strip_user_skill_copies(skills_dir: &std::path::Path) -> std::io::Result<usize>; // D7 marker 清理
```

- [ ] **Step 1: 核对两处现成代码再动笔（只读）**

- ~~终报事件 JSON 路径~~ **已钉死，无需再核**：`lib/events/bus.ts` 的 `isAssistantTextDelta` 判定是唯一权威——`event.type === "message_update"` 且 `event.assistantMessageEvent.type === "text_delta"`，文本在 `.delta` 字符串里。Step 2/3 按此实现。
- 读 pi.rs L2474-2530（pi_start_inner 签名与指纹复用逻辑）与 e2e/commands.rs L671-687（跨模块调用 + state 获取写法）。
- 读 pi.rs L141-152（emit_agent_event payload 形状）确认 sessionId 过滤字段名。

- [ ] **Step 2: 写纯 helper 失败测试**

```rust
#[test]
fn extract_text_delta_reads_the_message_update_path() { // 已对照 lib/events/bus.ts isAssistantTextDelta 钉死
    let delta = serde_json::json!({ "type": "message_update",
        "assistantMessageEvent": { "type": "text_delta", "delta": "世界" } });
    assert_eq!(extract_text_delta(&delta).as_deref(), Some("世界"));
    assert!(extract_text_delta(&serde_json::json!({ "type": "agent_end" })).is_none());
    assert!(extract_text_delta(&serde_json::json!({ "type": "message_update",
        "assistantMessageEvent": { "type": "tool_use" } })).is_none());
}

#[test]
fn strip_user_skill_copies_removes_only_marked_dirs() {
    let dir = tempfile::TempDir::new().unwrap().path().join("skills"); // dev-dependency tempfile，crate 已有则复用，没有则加
    std::fs::create_dir_all(dir.join("screenpipe-api")).unwrap();
    std::fs::create_dir_all(dir.join("my-own-skill")).unwrap();
    std::fs::create_dir_all(dir.join("imported-one")).unwrap();
    std::fs::write(dir.join("imported-one/.screenpipe-managed"), "").unwrap();
    assert_eq!(strip_user_skill_copies(&dir).unwrap(), 1);
    assert!(dir.join("screenpipe-api").exists());      // 基线保留
    assert!(dir.join("my-own-skill").exists());        // 无 marker 的不动
    assert!(!dir.join("imported-one").exists());       // marker 目录删除（D7）
}
```

- [ ] **Step 3: 实现 session.rs**

```rust
use tauri::Listener; // app.listen 需要的 trait

pub async fn run_intent_session(
    app: &tauri::AppHandle,
    base_config: crate::pi::PiProviderConfig,
    system_prompt: String,
    user_message: String,
) -> Result<String, String> {
    let dir = intent_project_dir();
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;

    // D7：基线 skills 写入 + 用户镜像剔除（独占 project_dir 前提）
    crate::pi::ensure_screenpipe_skill(&dir.to_string_lossy())?;
    let _ = strip_user_skill_copies(&dir.join(".pi/skills"));

    // D6：白名单与 system prompt 挂在会话配置上
    let mut cfg = base_config;
    cfg.system_prompt = Some(system_prompt);
    cfg.allowed_tools = Some(INTENT_ALLOWED_TOOLS.iter().map(|s| s.to_string()).collect());

    // 终报收集：先挂监听再发 prompt（D6，不改 stdout reader 热路径）
    let (done_tx, done_rx) = tokio::sync::oneshot::channel::<Result<String, String>>();
    let sid = INTENT_SESSION_ID.to_string();
    let collector: std::sync::Arc<std::sync::Mutex<(String, Option<String>)>> = Default::default();
    let listener = {
        let collector = collector.clone();
        app.listen("agent_event", move |evt| {
            let Ok(payload) = serde_json::from_str::<serde_json::Value>(evt.payload) else { return };
            if payload["sessionId"].as_str() != Some(&sid) || payload["source"].as_str() != Some("pi") { return; }
            let event = &payload["event"];
            if event["type"] == "agent_end" && event["willRetry"] != serde_json::json!(true) {
                let mut buf = collector.lock().unwrap();
                // 兜底：缓冲为空时从 messages 数组提取（summarize-with-ai.ts 同款）
                if buf.1.is_none() && buf.0.trim().is_empty() {
                    let mut final_text = String::new();
                    if let Some(messages) = event["messages"].as_array() {
                        for m in messages {
                            if m["role"] == "assistant" {
                                if let Some(blocks) = m["content"].as_array() {
                                    for b in blocks {
                                        if b["type"] == "text" {
                                            final_text.push_str(b["text"].as_str().unwrap_or(""));
                                        }
                                    }
                                }
                            }
                        }
                    }
                    buf.1 = Some(final_text);
                } else if buf.1.is_none() {
                    buf.1 = Some(std::mem::take(&mut buf.0));
                }
                let _ = done_tx.send(Ok(buf.1.clone().unwrap_or_default()));
                return;
            }
            if let Some(delta) = extract_text_delta(event) {
                collector.lock().unwrap().0.push_str(&delta);
            }
        })
    };

    let result = async {
        let pi_state = app.state::<crate::pi::PiState>();
        crate::pi::pi_start_inner(app, pi_state.inner(), INTENT_SESSION_ID,
            dir.to_string_lossy().into_owned(), None, Some(cfg)).await?;
        crate::pi::pi_prompt(app.clone(), app.state::<crate::pi::PiState>(),
            Some(INTENT_SESSION_ID.to_string()), user_message, None, None).await?;
        match tokio::time::timeout(std::time::Duration::from_secs(SESSION_TIMEOUT_SECS), done_rx).await {
            Ok(Ok(Ok(text))) if !text.trim().is_empty() => Ok(text),
            _ => Err("intent session produced no final text".into()),
        }
    }.await;

    let _ = crate::pi::pi_stop(app.state::<crate::pi::PiState>(), Some(INTENT_SESSION_ID.to_string())).await; // D6：跑完即停
    app.unlisten(listener);
    result
}

fn extract_text_delta(event: &serde_json::Value) -> Option<String> {
    // 形状逐字对照 lib/events/bus.ts 的 isAssistantTextDelta
    if event["type"] == "message_update" && event["assistantMessageEvent"]["type"] == "text_delta" {
        return event["assistantMessageEvent"]["delta"].as_str().map(str::to_string);
    }
    None
}
```

实现注意（侦察钉死的事实，落码时逐条核对）：

- `pi_prompt` 的 `State<'_, PiState>` 参数不能提前存变量复用（生命周期），在调用表达式内现取 `app.state::<...>()`；若编译器仍报借用冲突，改调 `pi_start_and_prompt`（pi.rs L2285，组合版，live-views 注释提醒它可能在会话就绪前 ack——所以保留先 start 后 prompt 的两步式为首选，组合版只作借用冲突时的备案并加注释）。
- `agent_end` 时若文本缓冲为空，兜底从 `event["messages"]` 数组提取（过滤 `role=="assistant"`、拼 `content[].type=="text"`）——summarize-with-ai.ts 的 fallback 逻辑，Step 1 核对后补进 collector 分支。
- `pi_start_inner` 的指纹复用（同 project_dir+config 复用现有进程，pi.rs L2497-2511）意味着第二次 tick 不重 spawn，属预期行为；池满驱逐（L2691-2724）在 MAX_PI_SESSIONS=20 下可接受，PR 说明里提一句。
- `tempfile` dev-dependency：`rg -n "tempfile" apps/screenpipe-app-tauri/src-tauri/Cargo.toml`，没有就加到 `[dev-dependencies]`。

- [ ] **Step 4: 跑测试并提交**

```bash
bun scripts/pre_build.js
cargo test --manifest-path apps/screenpipe-app-tauri/src-tauri/Cargo.toml intent_agent::session
git checkout -- apps/screenpipe-app-tauri/src-tauri/gen/schemas/
git add apps/screenpipe-app-tauri/src-tauri/src/intent_agent apps/screenpipe-app-tauri/src-tauri/Cargo.toml
git commit -m "feat(intent-agent): add Pi session runner with read-only allowlist and baseline-only skills"
```

---

### Task 5: Tauri commands（唯一写入口）与绑定生成

**Files:**
- Create: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/commands.rs`
- Modify: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/mod.rs`（`pub mod commands;`）
- Generated: `apps/screenpipe-app-tauri/lib/utils/tauri.ts`（bindings:generate 产出，不手编）

前置动作：调 skill `screenpipe-tauri`。

**Interfaces:**
- Consumes: Task 1 db 函数（经 `live_db()`，先例 `meeting_export.rs`）、Task 3 `PresetQuadruple` 与 supply 读写、`skills.rs::connect_detected_ai_tools_in_background(api_auth_enabled: bool, api_port: u16)`（skills.rs L82）。
- Produces（**七个** command，TS 经 `commands.*` 调用，Result 包装 `{status:"ok",data}|{status:"error",error}`；数量勘误见审查低-1）:

```rust
#[derive(Serialize, Deserialize, specta::Type)] pub struct IntentCardDto { /* IntentCardRow 全字段 */ }
#[derive(Serialize, Deserialize, specta::Type)]
pub struct LastGenerationStatus { pub at: i64, pub ok: bool, pub detail: Option<String>, pub source: String }
#[derive(Serialize, Deserialize, specta::Type)]
pub struct IntentSupplyState { pub slot: Option<supply::PresetQuadruple>,
    pub fallback_preset_id: Option<String>, pub last_generation: Option<LastGenerationStatus> }

#[tauri::command] #[specta::specta] pub async fn intent_list(filter: String) -> Result<Vec<IntentCardDto>, String>; // "pending"|"accepted"
#[tauri::command] #[specta::specta] pub async fn intent_card_mark_shown(app: tauri::AppHandle, card_id: i64) -> Result<(), String>;
#[tauri::command] #[specta::specta] pub async fn intent_card_decide(app: tauri::AppHandle, card_id: i64, decision: String) -> Result<(), String>; // "accepted"|"rejected"
#[tauri::command] #[specta::specta] pub async fn intent_spawn_onboarding_card(app: tauri::AppHandle) -> Result<i64, String>;
#[tauri::command] #[specta::specta] pub async fn intent_get_supply(app: tauri::AppHandle) -> Result<IntentSupplyState, String>; // D8：slot 为空时惰性写入 builtin_default
#[tauri::command] #[specta::specta] pub async fn intent_set_slot(app: tauri::AppHandle, slot: Option<supply::PresetQuadruple>) -> Result<(), String>;
#[tauri::command] #[specta::specta] pub async fn intent_set_fallback_preset_id(app: tauri::AppHandle, preset_id: Option<String>) -> Result<(), String>;
```

- [ ] **Step 1: 写状态机命令的失败测试**

```rust
#[tokio::test]
async fn decide_rejects_non_shown_cards() {
    // 内存池 + 迁移（同 Task 1 手法），插入 proposed 卡，直接调内部 handler：
    // decide 应返回错误；mark_shown 后 accepted 成功
}
#[tokio::test]
async fn decide_is_idempotent_safe() { // R1 配套
    // mark_shown → accept 成功 → 再次 accept 返回错误，status 仍 accepted
}
```

- [ ] **Step 2: 实现各 command**

- `intent_card_decide` 校验 decision ∈ {"accepted","rejected"}，经 `finish()` 落库。
- `intent_spawn_onboarding_card`（D5）：固定 plans（D4 结构、`kind:"onboarding_mcp"`，`detected_agents` 取 skills.rs 探测函数结果，失败给空数组），origin=`system_onboarding`、dedup_key=`system_onboarding:onboarding`，入库后 emit（Task 6 的 `emit_intent_card_created`，本任务先留调用点、Task 6 接线）并返回 id。**不设 expires_at**（D10）。
- `intent_get_supply`：读三键组装；`intent_slot` 键不存在时写入 `builtin_default()`（D8 出厂默认惰性初始化）再返回。
- supply 写命令走 Task 3 的 extra helper。

- [ ] **Step 3: 注册与重新生成绑定**

command 函数保持 pub，registry 按完整路径命名；然后：

```bash
cd apps/screenpipe-app-tauri && bun run bindings:generate
```

- [ ] **Step 4: 跑漂移测试与 src-tauri 测试**

```bash
bun scripts/pre_build.js
cargo test --manifest-path apps/screenpipe-app-tauri/src-tauri/Cargo.toml tauri_bindings_are_current
cargo test --manifest-path apps/screenpipe-app-tauri/src-tauri/Cargo.toml intent
git checkout -- apps/screenpipe-app-tauri/src-tauri/gen/schemas/
```

- [ ] **Step 5: Commit**

```bash
git add apps/screenpipe-app-tauri/src-tauri/src/intent_agent apps/screenpipe-app-tauri/lib/utils/tauri.ts
git commit -m "feat(intent-agent): expose state-machine and supply commands with regenerated specta bindings"
```

---

### Task 6: 心跳循环宿主、通知 action 契约与推送

**Files:**
- Create: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/runner.rs`
- Modify: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/mod.rs`（`pub mod runner;`）
- Modify: `apps/screenpipe-app-tauri/src-tauri/src/events.rs`（新增事件常量）
- Modify: `apps/screenpipe-app-tauri/src-tauri/src/main.rs`（setup 里 spawn）

**Interfaces:**
- Consumes: Task 1 db 函数、Task 2 gate/parse/instruct、Task 3 supply、Task 4 session、`recording.rs::LocalApiContext` 与 `commands.rs::get_local_api_config`（取 localhost 端口与 key）、`notifications/client.rs::send_typed_with_actions_and_priority`（L37：返回 unit、强制成形 title/body、`actions: Vec<serde_json::Value>`）。
- Produces:

```rust
// events.rs 追加
pub const INTENT_CARD_EVENT: &str = "intent_card_created";
pub fn emit_intent_card_created(app: &tauri::AppHandle, card_id: i64);

// runner.rs
pub async fn start(app: tauri::AppHandle); // sleep(FIRST_RUN_DELAY_SECS) 后 interval(HEARTBEAT_INTERVAL_SECS)，tick 出错记 tracing 不退出
pub(crate) struct GenerationRecord { pub at: i64, pub ok: bool, pub detail: Option<String>, pub source: &'static str } // D9：at 每次尝试都更新
pub(crate) async fn tick(app: &tauri::AppHandle) -> Result<Option<GenerationRecord>, String>;
pub(crate) async fn fetch_activity_summary(app: &tauri::AppHandle, start: chrono::DateTime<chrono::Utc>, end: chrono::DateTime<chrono::Utc>) -> Result<serde_json::Value, String>;
pub(crate) async fn notify_new_card(app: &tauri::AppHandle, card_id: i64, card: &parse::GeneratedCard) -> Result<(), String>;
```

- [ ] **Step 1: 核对两处现成代码再动笔（只读）**

- ~~通知 action JSON 形状~~ **已钉死，无需再核**：action 对象的判别字段是 **`type`**（`notifications/store.rs` 的 `legacy_needs_attention` 按 `action.get("type")` 读取；native overlay 在 `commands/native_actions.rs` 按 `parsed["type"]` 分发后经 `emit_notification_action` 回传，事件体 `NotificationActionEvent{ action_type, raw_json, payload }`）；label 字段名是 `label` 且须非空（同 store.rs 判定）。跳转动作即：`json!({"type":"open_intent_workbench","label":"open workbench"})`——label 硬编码英文有 routes.rs 现成先例（cta label "open settings"），i18n 债务记入 PR 说明。
- 读 `crates/screenpipe-engine/src/routes/activity_summary.rs` 的 `ActivitySummaryQuery`：确认 `start_time/end_time` 吃 ISO 8601、`start>=end` 返回 400、`apps` 数组字段名与排序（Task 2 `dominant_app` 的核对点在此一并确认）。

- [ ] **Step 2: 实现 events.rs 追加**

```rust
pub const INTENT_CARD_EVENT: &str = "intent_card_created";
pub fn emit_intent_card_created(app: &tauri::AppHandle, card_id: i64) {
    let _ = app.emit(INTENT_CARD_EVENT, serde_json::json!({ "cardId": card_id }));
}
```

- [ ] **Step 3: 实现 runner.rs**

`tick` 流程（顺序固定，D9 锚点已内化）：

```rust
let db = live_db(app).await?;
let now = chrono::Utc::now().timestamp();
db_expire_due(&db, now).await?;                                    // 1. 过期结算先行（T8 决议 3）
let latest = latest_created_at(&db).await?;
let window_start_ts = gate::window_start(now, latest);             // 2. 材料窗：锚最后插入，封顶 7d
let last_attempt = read_last_generation(app).await.map(|r| r.at);  // 3. D9：信号窗锚最后尝试
let signal_since = gate::signal_window_start(now, last_attempt);
let signals = WindowSignals {
    app_switches: count_ui_events_since(&db, to_utc(signal_since)).await?,
    frame_changes: count_frame_changes_since(&db, to_utc(signal_since)).await?,
}; // to_utc: chrono::DateTime::from_timestamp(secs,0) → DateTime<Utc>
if !gate::should_attempt_generation(&signals) { return Ok(None); } // 4. 门槛
let end = chrono::Utc::now();
let start_dt = to_utc(window_start_ts);
let summary = fetch_activity_summary(app, start_dt, end).await?;   // 5. ISO 8601 rfc3339 传参，禁 unix 秒
let dominant = gate::dominant_app(&summary);
let input = GenerationInput {
    window_start_text: start_dt.to_rfc3339(), window_end_text: end.to_rfc3339(),
    activity_summary: summary, signals,
};
let (slot, mirror_id) = supply::read_supply(app).await;
let mirror = match mirror_id.as_deref() { Some(id) => supply::resolve_mirror_preset(app, id).await, None => None };
let (cfg, source) = supply::resolve_chain(slot, mirror);
let used_model = cfg.model.clone(); // cfg 下面被 move 进会话，先留底（供给追溯用）
let record = match session::run_intent_session(app, cfg, instruct::build_system_prompt(),
        instruct::build_user_payload(&input)).await
{
    Ok(raw) => match parse::parse_model_output(&raw) {
        Ok(ModelOutcome::InsufficientMaterial) => GenerationRecord { at: now, ok: true, detail: Some("material insufficient".into()), source },
        Ok(ModelOutcome::Card(c)) => {
            let key = gate::dedup_key(&c.card_type, &dominant);
            let date = chrono::Local::now().format("%Y-%m-%d").to_string(); // 本地自然日（T4 决议 5）
            let outcome = insert_intent_card(&db, &NewIntentCard {
                origin: "proactive".into(), card_type: c.card_type.clone(),
                proactive_view: Some(c.proactive_view.clone()), dedup_key: key,
                local_date: date, plans_json: serde_json::to_string(&c).unwrap(),
                model_id: Some(used_model),
            }).await?;                                                     // 6. D9/D10：InsertOutcome 区分；无 expires_at
            if let InsertOutcome::Inserted(id) = &outcome {                    // DedupHit 静默（D9）
                emit_intent_card_created(app, *id);
                notify_new_card(app, *id, &c).await?;                          // 7. notification-panel
            }
            GenerationRecord { at: now, ok: true,
                detail: (matches!(outcome, InsertOutcome::DedupHit(_))).then(|| "dedup hit".into()), source }
        }
        Err(e) => GenerationRecord { at: now, ok: false, detail: Some(e), source },
    },
    Err(e) => GenerationRecord { at: now, ok: false, detail: Some(e), source }, // D8：不跨级降级
};
write_last_generation(app, &record).await;                             // 8. D9：任何结局都更新尝试锚点
Ok(Some(record))
```

`fetch_activity_summary`：GET `http://127.0.0.1:{port}/activity-summary?start_time={rfc3339}&end_time={rfc3339}&include_apps=true&include_windows=true`，Bearer api_key（经 `get_local_api_config`），30s timeout，非 2xx warn 转 Err，成功解析为 `serde_json::Value`。

`notify_new_card`：调 `client::send_typed_with_actions_and_priority`，payload 带结构化字段 `{cardType, topPlanTitle}`（plan title 是模型产出的用户语言内容、不经字典直接用）；actions 数组一项：

```rust
let actions = vec![serde_json::json!({
    "type": "open_intent_workbench",   // native overlay 按 type 分发（commands/native_actions.rs）
    "label": "open workbench",          // 硬编码英文，先例 routes.rs cta；i18n 债务记 PR
})];
```

title 用 topPlanTitle、body 用 `truncate_string(proactive_view, 120)`。前端收到的回传事件体是 `NotificationActionEvent` 的序列化（字段 `action_type` 的 serde 名以 events.rs 为准，Task 8 Step 3 监听时对照 bindings 实测，v1 侦察记录为 camelCase `actionType`）。

`read/write_last_generation`：extra 键 `intent_last_generation`，JSON `{"at":i64,"ok":bool,"detail":null|string,"source":string}`。

- [ ] **Step 4: main.rs 接线**

setup 段 suggestions auto-start 那行旁加：

```rust
tauri::async_runtime::spawn(crate::intent_agent::runner::start(app_handle.clone()));
```

- [ ] **Step 5: 构建验证**

```bash
bun scripts/pre_build.js
cargo check --manifest-path apps/screenpipe-app-tauri/src-tauri/Cargo.toml
git checkout -- apps/screenpipe-app-tauri/src-tauri/gen/schemas/
```

- [ ] **Step 6: Commit**

```bash
git add apps/screenpipe-app-tauri/src-tauri/src/intent_agent apps/screenpipe-app-tauri/src-tauri/src/events.rs apps/screenpipe-app-tauri/src-tauri/src/main.rs
git commit -m "feat(intent-agent): add resident heartbeat with attempt-anchored gating and Pi session generation"
```

---

### Task 7: 工作台 section 骨架（前端）

**Files:**
- Modify: `apps/screenpipe-app-tauri/lib/utils/sidebar-nav-layout.ts`（SidebarNavId 联合类型加 `"workbench"`）
- Modify: `apps/screenpipe-app-tauri/app/(main)/home/page.tsx`（四处：`MainSection` 类型 L114、`ALL_SECTIONS` L123、`SIDEBAR_SECTION_DEFS` L1039、renderMainSection switch L955）
- Create: `apps/screenpipe-app-tauri/components/intent-workbench/index.tsx`
- Create: `apps/screenpipe-app-tauri/lib/i18n/en-workbench.ts` · `zh-workbench.ts`（命名对齐仓库现有 `en-shell.ts`/`en-home.ts` 分片风格，导出 `workbenchEn`/`workbenchZh`——审查低-8）
- Modify: `apps/screenpipe-app-tauri/lib/i18n/en.ts` · `zh-CN.ts`（合并分片）
- Modify: browser-mock IPC shim（`rg -l "SCREENPIPE_WEB_SCENARIO"` 定位，先例 `browser-tauri-mock.ts` L212）

**Interfaces:**
- Consumes: Task 5 生成的 `commands.intentList / intentGetSupply`。
- Produces: `<IntentWorkbench reloadKey={number} />`（Task 8 填充卡片体；**刷新走 prop 驱动**，见 Step 3，本仓无 react-query，禁用 invalidateQueries——审查 M2）；i18n 命名空间 `workbench.*`。

- [ ] **Step 1: 注册 section 四处改动**

照侦察钉死的位置：SidebarNavId 加 `"workbench"`；home/page.tsx 四处各加 workbench 条目（label 用 `t("shell.nav.workbench")`，icon 选 lucide `Sparkles`），默认排位放 activity 之后。行号会漂移，以名字检索为准。

- [ ] **Step 2: i18n 骨架键集**

`en-workbench.ts` 导出并入 en.ts 的 `workbench` 命名空间（zh 同构）。骨架键先行，卡片键随 Task 8 补进同一分片：

```ts
export const workbenchEn = {
  nav: "Workbench",
  filterPending: "Pending decisions",
  filterFinished: "Finished",
  empty: "No intent cards yet.",
  emptyOnboardingCta: "Generate the onboarding card",
  loading: "Loading…",
} as const;
```

zh-CN 对应：「工作台」「待决定」「已结束」「还没有意图卡片」「生成新手接入卡」「加载中…」。

- [ ] **Step 3: 列表骨架组件（prop 驱动刷新）**

`components/intent-workbench/index.tsx`：props 含 `reloadKey: number`；两个 Filter tab（本地 state），pending 时 `commands.intentList("pending")`、finished 时 `("accepted")`；`useEffect(..., [reloadKey, filter])` 触发加载。home/page.tsx 持有 `const [workbenchReloadKey, setWorkbenchReloadKey] = useState(0)`，`useTauriEvent<{cardId:number}>("intent_card_created", () => setWorkbenchReloadKey(k => k + 1))`，把 key 传进组件。加载态照 ActivityLedger skeleton，空态用上面键。视觉 token 对照原型：`#121212` 底、22% 灰边框、6px 圆角、白底黑字主按钮。

- [ ] **Step 4: browser-mock stub**

为**七个** intent command 加 fixture 分支（两张 pending 卡：一张 light 提案、一张 system_onboarding；一张 accepted 卡），空场景返回空数组。

- [ ] **Step 5: 验证**

```bash
cd apps/screenpipe-app-tauri
SCREENPIPE_WEB_SCENARIO=ready bun run dev:web   # http://127.0.0.1:1420/home?section=workbench 截图对照原型
bun run test
```

- [ ] **Step 6: Commit**

```bash
git add lib/utils/sidebar-nav-layout.ts app/\(main\)/home/page.tsx components/intent-workbench lib/i18n
git commit -m "feat(workbench): register workbench section with pending/finished filters"
```

---

### Task 8: 卡片组件、裁决交互与事件接线

**Files:**
- Create: `apps/screenpipe-app-tauri/components/intent-workbench/intent-card.tsx`
- Create: `apps/screenpipe-app-tauri/components/intent-workbench/plans-list.tsx`
- Modify: `apps/screenpipe-app-tauri/components/intent-workbench/index.tsx`（替换占位行）
- Modify: `apps/screenpipe-app-tauri/app/(main)/home/page.tsx`（notification:action 监听）

**Interfaces:**
- Consumes: `commands.intentCardMarkShown / intentCardDecide`；Task 7 的 `reloadKey` 刷新通道；`NOTIFICATION_ACTION_EVENT`（实值 `"notification:action"`，events.rs L17-18，macOS/Windows cfg 门控）。

- [ ] **Step 1: plans-list（方案选择）**

props: `plansJson: string`。解析 D4 结构（校验 `v===1`）；radio 列表，`recommended_index` 默认选中；选中项下方显示 consequence 行；末行虚线 radio + 输入框（原型 plan-compose 模式）：回车或失焦钉成本地方案并选中、挂「你的方案」角标。轻提示卡不显示方案列表，只显示 proactive_view 正文。

- [ ] **Step 2: intent-card（按钮矩阵与状态呈现）**

- pending 卡：提案按钮组「接受选中方案 / 不要」，轻提示「知道了 / 不要」，都调 `commands.intentCardDecide(id, ...)`，Result 错误分支 toast；点击后乐观移出列表。
- shown 回写：pending 列表渲染完成后对每张 `status==='proposed'` 的卡调 `intentCardMarkShown(id)`，组件内 `useRef<Set<number>>` 防重。幂等由 SQL 层兜底（R1 + D10：新手卡 mark_shown 不产生过期时钟）。
- finished 卡只读，显示终态徽标。
- 五状态样式对照原型图例；「正在准备」（proposed 未回写前）标注为库里存在、界面短暂过渡态。
- 新手接入卡（`origin==='system_onboarding'`）：按 T6 文案渲染 detected_agents 行，主按钮「接入」调 `commands.intentCardDecide(id,"accepted")`，Rust 侧触发连接（D5，Task 9 补触发点）。

- [ ] **Step 3: 事件接线（home/page.tsx）**

```tsx
// 刷新已在 Task 7 经 reloadKey 通道接好；这里补通知跳转：
useTauriEvent<{ actionType?: string }>("notification:action", (e) => {
  if (e.actionType === "open_intent_workbench") setActiveSection("workbench");
});
```

事件 payload 的动作字段名以 Task 6 Step 1 核对的现成调用方形状为准，与 `notify_new_card` 构造的 action 对象同字段（M1 契约闭环）。**平台门控备注**：`NOTIFICATION_ACTION_EVENT` 在 Rust 侧 macOS/Windows 才编译，Linux 走 webview 分支，「查看」类 action 的转发通路接线时单独确认；不存在则 Linux 降级为仅面板展示、无跳转（记入 PR 说明，不阻塞 macOS 主线）。

- [ ] **Step 4: i18n 卡片文案键**

`workbench.card.*` 并入 Task 7 分片：accept/reject/knownOk/noThanks/customPlanBadge/yourPlan/recommended/consequenceLabel/status 五值/onboarding.title/onboarding.detectLine 等，en 先加、zh 补齐。按钮文案对照 T6：「知道了 / 不要」「接受选中方案 / 不要」。至此 `workbench.*` 清单收口。

- [ ] **Step 5: 验证**

```bash
SCREENPIPE_WEB_SCENARIO=ready bun run dev:web   # 对照 wayfinder/assets/t6-workbench-proto.html 逐块核对
bun run test
```

截图贴 PR/issue。

- [ ] **Step 6: Commit**

```bash
git add components/intent-workbench app/\(main\)/home/page.tsx lib/i18n
git commit -m "feat(workbench): card rendering, decision buttons, shown writeback, and event wiring"
```

---

### Task 9: 设置页供给卡（ai-presets.tsx）、BYOK 引导、镜像触发点与端到端测通

**Files:**
- Modify: `apps/screenpipe-app-tauri/components/settings/ai-presets.tsx`（intent 供给卡落这里，不在 ai-settings.tsx——该文件只有三个开关，preset CRUD 与 `AIPreset` 枚举都在 ai-presets.tsx，审查 M4）
- Modify: `apps/screenpipe-app-tauri/lib/active-ai-preset.ts`（镜像写入点：`writeActiveAiPresetId` + 应用首次加载，审查 M3-2）
- Modify: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/commands.rs`（新手卡接受后触发连接）
- Modify: `doc/FEATURE_MODEL_INVOCATION_INVENTORY.md`（补 PATH 编号）

**Interfaces:**
- Consumes: `commands.intentSetSlot / intentSetFallbackPresetId / intentGetSupply / intentSpawnOnboardingCard`；`Settings.aiPresets: AIPreset[]`（单数 `AIPreset`，审查低-5）。

- [ ] **Step 1: 设置页 intent 供给卡**

AIPresets 组件内、preset 列表上方加一块卡片：

- preset 选择器枚举 `settings.aiPresets`，选项含「跟随 Chat」（对应 `intentSetSlot(null)`）；选定具体 preset 则 `intentSetSlot({provider: preset.provider, url: preset.url, model: preset.model, apiKey: preset.apiKey ?? null})`。
- 出厂默认展示为「本机 Ollama（默认）」——对应 slot 惰性初始化后的 `native-ollama` 值（D8），文案走 i18n。
- 下方常显两行信息（R7）：当前生效来源 tag 与端点 host+model（slot / mirror / builtin 三种来源都显示实际端点，mirror 显示现查解析结果）；以及 `last_generation`（最近成败 + 失败原因）。失败不打扰工作台（T7 决议 3）。
- **BYOK 引导块**（T7 修订）：两行说明文案走 i18n——意图卡片是多轮工具调用，吃模型能力；本机 Ollama 可用但效果可能偏弱，推荐给 intent 槽配云端强模型 preset。不做深链跳转，就在卡片内。

- [ ] **Step 2: fallback 镜像（D1，触发点按实况修正）**

`lib/active-ai-preset.ts`：在 `writeActiveAiPresetId` 函数体内（brain-overview.tsx L680 与 standalone-chat.tsx L321 是仅有的两个调用点，函数本身是唯一写入口）追加 fire-and-forget 的 `commands.intentSetFallbackPresetId(id).catch(...)`；应用首次加载（该模块顶层或 home 挂载处）同样上报当前 id。**不**挂在 `resolveActiveAiPreset` 上（全仓仅 brain-overview 一处 useMemo 调它，且 Pi 启动路径不经它）。api_key/url 变更无需重报——心跳按 id 现查 aiPresets，内容天然新鲜（D1 主路径，已核实 Rust 可读顶层 `ai_presets`）。

- [ ] **Step 3: 新手卡接受触发点**

`intent_card_decide` 命中 accepted 且卡 origin 为 system_onboarding 时，tokio spawn 调 `skills.rs::connect_detected_ai_tools_in_background(api_auth_enabled, api_port)`，失败仅 tracing（D5）。状态机铁律的唯一已知例外，备忘在 D5。

- [ ] **Step 4: 盘点文档补登**

按 `doc/FEATURE_MODEL_INVOCATION_INVENTORY.md` 阶段 0 要求为意图卡片生成补登 `PATH-*` 条目（T7 边界声明义务），路径描述写 Pi 会话形态。

- [ ] **Step 5: 端到端测通（真实 app，跨原生边界）**

```bash
bun run dev:tauri
```

清单：设置页看到出厂默认「本机 Ollama」与 BYOK 引导 → 选一个云端 preset 作 intent 槽 → 点「生成新手接入卡」→ 面板弹提醒（闸门静音时被抑制也算通过闸门验证）→ 点提醒跳转工作台 → 接受 → 状态变 accepted 且 skills 连接日志出现 → 手动插一张 expires_at 已过的 shown proactive 卡重启，验证心跳醒来先结算 expired → 重复 mark_shown 验证时钟不续命（R1）→ **新手卡 shown 后重启并快进时间，验证不被 expire_due 结算**（H1 端到端复核）→ 查 `~/.cue/pi-intent/.pi/skills/` 无 `.screenpipe-managed` 目录（D7）→ 会话 transcript 里工具调用仅白名单两项（D6）→ 同日同 app 二次出卡不重复弹通知（D9）。全程无账户登录。

- [ ] **Step 6: Commit**

```bash
git add components/settings/ai-presets.tsx lib/active-ai-preset.ts src-tauri/src/intent_agent doc/FEATURE_MODEL_INVOCATION_INVENTORY.md
git commit -m "feat(workbench): intent supply card with BYOK guidance, chat preset mirror, onboarding connect hook"
```

---

## 验收清单（对照 Spec）

| Spec 要求 | 落点 |
| --- | --- |
| intent_cards 十二列最小表 + dedup 唯一索引（T4） | Task 1 |
| Rust 心跳 + Pi 会话生成，节拍判据分离，随引擎常驻（T3 修订） | Task 2/3/4/6 |
| 只读工具白名单 + 仅基线 skills + 独占 project_dir（T3 修订 + D6/D7） | Task 4 |
| 上下文 = 查询窗口增长且有硬上限（T3 决议 4 + R2） | Task 2/6 window_start |
| 信号窗锚最后尝试，dedup 命中静默（D9） | Task 1/2/6 |
| 新手卡永不过期（T5 决议 4 + D10） | Task 1/6 |
| 主窗口新增 section，两个 Filter，新手卡随第一版（T5） | Task 7 |
| 到卡提醒复用 notification-panel 闸门，action 契约闭合（T5 + M1） | Task 6/8 |
| 五值状态机四条转移，写入唯一入口，过期挂心跳，时钟不可续命（T8 + R1） | Task 1/5/6 |
| 三级供给出厂默认本机 Ollama，不跨级降级，失败日志加设置页可见（T7 + D8） | Task 3/5/9 |
| BYOK 引导进 v1（T7 修订） | Task 9 |
| 按钮组收窄：知道了/不要、接受/不要，接受只写终态（T5） | Task 8 |
| 新手接入卡落 MCP 真实机制（T6/D5） | Task 5/8/9 |
| i18n 全覆盖、Cue 品牌边界、provenance 头 | 各任务 + Global Constraints |
| PATH-* 补登（T7 边界声明） | Task 9 |

## 明确不做（防蔓延）

执行与终态链路、重写流程、记忆基底、记账三件套、卡片快捷键、「执行中」Filter、Daily Summary 持久化、直调双路径回退、运行时跨级供给降级、用户自装 skills 镜像、bash/写侧工具、chat active preset 整体迁入 SettingsStore。出现这些诉求时停下来说明，另行开票。

## 评审修订记录

v2（2026-08-22）：R1 mark_shown 单向守卫；R2 窗口封顶；R3 镜像改 id 现查；R4 plans_json 版本字段；R5 CHECK 保留备忘；R6 新手卡例外记档；R7 设置页来源可见；R8 dedup 策略备忘。

v3（2026-08-23）：依据 T3/T7 修订与外部审查（DeepSeek，结论出具于修订前，逐条按修订后语境重估）：

- **H1（采纳，正确性）**：mark_shown 曾会无条件给新手卡写 48h 过期时钟，违反 T5 决议 4。修复为 D10：expiry 唯一写入点且按 origin 分支，`NewIntentCard` 删 expires_at 字段（顺带解决审查低-2 的职责重叠），新增 onboarding 不过期测试与端到端复核步。
- **H2（采纳，正确性，Pi 会话后加重）**：窗口锚最后插入会让非插入结局（材料不足/解析失败/dedup）导致门槛常开、每 15 分钟无退避重试——直调时代是重复 HTTP 调用，会话时代升级为重复 Bun 子进程 spawn，代价更高。修复为 D9：信号窗锚最后尝试 + InsertOutcome 区分 + DedupHit 静默（原 tick 对 dedup 命中仍 emit+notify 且记成功，属第二个 bug，一并修）。
- **H3（采纳，spec 忠实度）**：v1 把默认供给做成 slot=None（跟随 Chat）偏离 T7 决议 2 且与 Global Constraints 自相矛盾。修复为 D8：出厂默认非空的内置 native-ollama preset，跟随 Chat 降为显式选项；显式声明不跨级降级。
- **M1（采纳）**：通知 action 的 JSON 形状与 actionType 契约补进 Task 6 Step 1/3 与 Task 8 Step 3，以现成调用方形状为准，不发明字段。
- **M2（采纳）**：`invalidateQueries(["intent-list"])` 在本仓零使用且无该 query key，改为 reloadKey prop 驱动刷新（Task 7/8）。
- **M3（采纳澄清）**：aiPresets 在 store 顶层非 extra（主路径成立）；extra 读写钉 store.rs insert+save 模式；镜像触发点从 resolveActiveAiPreset 改钉 writeActiveAiPresetId + 启动（Task 9 Step 2）。
- **M4（采纳）**：intent 供给卡从 ai-settings.tsx 改落 ai-presets.tsx（该文件才有 preset 枚举）。
- **M5（采纳）**：dominant_app 定义为 gate.rs 纯 helper（apps[0].name 缺省 general），并加路由字段核对步。
- **低优先级全收**：七个 command（非八个）；count_* 收 DateTime<Utc>；write_queue.rs 表述修正；AIPreset 单数；MainSection L114；i18n 分片命名对齐 en-shell.ts 风格；suggestions Bearer/max_tokens 差异随直调任务废弃一并消失。
- **经核验采信的侦察事实**（两路只读核验命中）：DDL 迁移时序、strings helpers、DatabaseManager.pub pool、connect_detected_ai_tools_in_background 签名、NOTIFICATION_ACTION_EVENT 门控、localStorage 键、browser-mock shim、tauri_bindings_are_current、原型视觉 token 与按钮文案、绿地状态（cue-branding @ b3dc8a178 无 intent_* 残留）。
