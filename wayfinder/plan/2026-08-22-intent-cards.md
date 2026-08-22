# 意图卡片 v1（生成 + 展示链路）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 screenpipe fork（品牌 Cue，分支 cue-branding）上落成意图卡片的完整「生成 → 落库 → 展示 → 裁决」链路：Rust 心跳驱动单次直调生成卡片，主窗口工作台 section 展示与裁决，notification-panel 提醒。

**Architecture:** 数据层新建 `intent_cards` 十二列表（screenpipe-db 迁移）；生成侧是 src-tauri 常驻 tokio 循环——每次醒来先结算过期，再拉增量信号过门槛，过门后经 localhost HTTP 取 activity-summary、拼 prompt、按两级回退选 preset 直调 OpenAI 兼容接口，解析 JSON 方案数组入库并推送事件与通知；展示侧是主窗口新增 workbench section，按钮只调 Tauri command 写状态。

**Tech Stack:** Rust（tokio / sqlx / reqwest / serde）、Tauri 2 + specta 绑定生成、Next.js App Router + TypeScript（bun）、SQLite（sqlx migrate）、i18n 双字典。

**Spec:** `wayfinder/MAP.md`（决策地图）与 `wayfinder/tickets/01` 至 `wayfinder/tickets/09`（逐项决议）。本计划从这些票出发；冲突时以票据为准。侦察事实来自两轮只读探查（前端挂点、Rust 挂点），关键签名已就地核实。

## Global Constraints

以下约束对每个任务隐式生效，值均抄自仓库约定或票据：

- 每个新建或编辑的源码文件，头部加 provenance 注释（Rust/TS 用 `//`），内容照根 `AGENTS.md` 原文。
- JS/TS 一律 bun，禁 npm/pnpm；Rust 用 cargo。
- 用户可见文案全部走 i18n 字典：先加 en 键、补 zh 同构键，组件内不写内联文案；测试默认英文环境断言逐字原文（`doc/FEATURE_I18N_UI_LANGUAGE.md`）。
- 品牌边界：用户可见处写 Cue；代码标识符、数据路径、env 保留 `screenpipe` 命名（`doc/FEATURE_CUE_BRANDING.md`）。
- local-first 基线：无账户可用，不得引去登录页；模型供给默认内置 Ollama `qwen3.5:9b` @ `http://localhost:11434/v1`（T7）。
- 状态写入唯一入口是 src-tauri 的 Tauri command；前端不直接写库，模型侧没有任何路径能写 `status`（T8 决议 4）。
- 状态机五值 `proposed/shown/accepted/rejected/expired`，v1 只生效四条转移：`proposed→shown`、`shown→accepted`、`shown→rejected`、`shown→expired`；过期统一 shown 后 48h，过期时钟只从第一次 shown 起算，不因重复回写续命（T4/T8 + 评审修订 R1）。
- OCR/活动文本截断一律走 `screenpipe_core::strings::{safe_byte_prefix, truncate_string}`，生成相关模块文件头加 `#![deny(clippy::string_slice)]`（T9 参考件纪律）。
- 不建：重写流程、`rewrite_prev_card_id`/`adjust_opened_at` 列、记账三件套、记忆基底、执行链路、独立过期定时器（MAP Out of scope + T3/T4/T8）。
- UI 验证走 browser-mock 循环（`bun run dev:web`），不为 React/布局改动编 Tauri；跨原生边界才用 `bun run dev:tauri`。
- src-tauri 测试：先 `bun scripts/pre_build.js`，再 `cargo test --manifest-path apps/screenpipe-app-tauri/src-tauri/Cargo.toml <filter>`；构建会改写 tracked 的 `gen/schemas/`，事后 `git checkout -- apps/screenpipe-app-tauri/src-tauri/gen/schemas/`。
- 改 Tauri command 前调 skill `screenpipe-tauri`；改用户可见文案前读两份 branding/i18n 合同。
- git：never `git reset`，不删非自己写的代码；每任务一提交。

## 计划期补裁决（D1–D5）

票据留白、本计划锁定的实现口径。D1/D4 已按外部评审修订（见文末修订记录），其余均有依据：

| # | 裁决 | 内容 | 依据 |
| --- | --- | --- | --- |
| D1 | 回退镜像机制（v2 修订） | chat active preset 存在前端 localStorage（`lib/active-ai-preset.ts`，键 `chat-active-preset-id`），心跳在主窗口关闭时读不到。前端只在启动与切换两处经 command 把 **active preset id** 镜像进 SettingsStore.extra 的 `intent_fallback_preset_id` 键——不镜像 endpoint 三元组。心跳取用顺序：intent 槽 → 按 id 去 store.bin 的 aiPresets 里现查端点 → 内置 Ollama 默认。现查保证 api_key 或 url 在设置页被改后天然新鲜，消灭「镜像陈旧凭证」的腐烂点。若实现期确认 Rust 读不到 aiPresets（读取入口见 Task 4 Step 1），退回镜像三元组并在 ai-presets.tsx 的保存回调补一个触发点。**语义偏离声明**：实际语义已从 T7 票面的「发起那一刻 chat 正用的 preset」变为「最近一次前端上报的 active preset」，此偏离是有意的，执行链路 effort 重估供给层时一并回收。 | T7 两级回退 + T3 常驻语义的交集 + 评审 R3 |
| D2 | dedup_key 口径 | `{card_type}:{dominant_app}`；dominant_app 取 activity-summary 的首位 app 名，缺省 `general`。**备忘**：unique(dedup_key, local_date) 编码的是「每 app 每类型每天最多一张」的产品策略，将来调策略动的是索引和迁移，不是常量。 | T4 决议 7 + 评审 R8 |
| D3 | 心跳节拍常量 | 间隔 900s，首轮延迟 120s；信号门槛：窗口内 app_switch+window_focus ≥ 3 或 frames hash 变化 ≥ 5；查询窗口上限 MAX_WINDOW_SECS = 7 天。常量集中在 gate.rs 顶部，属可调参数。 | T3 决议 3 + 评审 R2 |
| D4 | plans_json 结构（v2 修订） | 所有形态带版本字段 `"v": 1`。普通卡：`{"v":1,"recommended_index":0,"plans":[{"title","summary","consequence"}]}`；新手接入卡：`{"v":1,"kind":"onboarding_mcp","detected_agents":[...]}`。解析器先看 `v`，未知版本直接报错不猜；GeneratedPlan 保持 serde 默认宽容，不加 deny_unknown_fields，给 v2 加字段留路。检测到的 agent 名为专有名词不进字典。 | T6 定稿结论 + 评审 R4 |
| D5 | 新手卡接受语义 | 「接入」= 写 accepted 终态 + 调 skills.rs 现成的 `connect_detected_ai_tools_in_background`，失败记 tracing 不回滚状态。不建新执行基础设施。**备忘**：这是全计划唯一 accept 触发副作用的路径，与 T8「接受只写终态」不同源；执行链路 effort 启动时必须回来统一这条语义，做信任演示审批时此处是已知例外。 | T6 主按钮落在真实 MCP 注册机制 + T5 收窄 + 评审 R6 |

**Schema 备忘**（评审 R5 的处置）：`card_type`/`status` 的 CHECK 约束保留——T4 决议 4 已显式裁决「SQLite CHECK 改值要重建表，多留一个值比日后迁移便宜」，五值就是为执行链路留的余量，推翻它违反票据纪律。代价照单全收：将来加新状态或类型走 rebuild 迁移，fork 先例在 activity_ledger。

---

### Task 1: intent_cards 表与数据访问层

**Files:**
- Create: `crates/screenpipe-db/src/migrations/20260822120000_create_intent_cards.sql`
- Create: `crates/screenpipe-db/src/db/intent_cards.rs`
- Modify: `crates/screenpipe-db/src/db/mod.rs`（注册模块）

**Interfaces:**
- Consumes: sqlx migrate 宏（`db/setup.rs` 已有 `migrate!("./src/migrations")`）。
- Produces（后续任务依赖的确切签名，均在 `crates/screenpipe-db` 内，由 `db/mod.rs` re-export）:

```rust
pub struct IntentCardRow {
    pub id: i64, pub origin: String, pub card_type: String, pub status: String,
    pub proactive_view: Option<String>, pub dedup_key: String, pub local_date: String,
    pub plans_json: String, pub model_id: Option<String>,
    pub shown_at: Option<i64>, pub expires_at: Option<i64>, pub created_at: i64,
}
pub struct NewIntentCard {
    pub origin: String, pub card_type: String, pub proactive_view: Option<String>,
    pub dedup_key: String, pub local_date: String, pub plans_json: String,
    pub model_id: Option<String>, pub expires_at: Option<i64>, // None = 不过期（新手卡）
}
pub async fn insert_intent_card(pool: &SqlitePool, card: &NewIntentCard) -> Result<i64, sqlx::Error>; // dedup 命中返回已存在 id
pub async fn list_pending(pool: &SqlitePool) -> Result<Vec<IntentCardRow>, sqlx::Error>;   // status IN ('proposed','shown')
pub async fn list_accepted(pool: &SqlitePool) -> Result<Vec<IntentCardRow>, sqlx::Error>;
// R1：仅允许 proposed→shown 单向转移（SQL 带 WHERE status='proposed'）。
// 重复调用返回 false 且绝不改写 shown_at/expires_at——重挂载、Strict Mode 双渲染、
// 多窗口都不得续命过期时钟。
pub async fn mark_shown(pool: &SqlitePool, id: i64, now: i64) -> Result<bool, sqlx::Error>;
pub async fn finish(pool: &SqlitePool, id: i64, terminal: &str) -> Result<bool, sqlx::Error>; // 仅 accepted/rejected，WHERE status='shown'
pub async fn expire_due(pool: &SqlitePool, now: i64) -> Result<u64, sqlx::Error>;
pub async fn latest_created_at(pool: &SqlitePool) -> Result<Option<i64>, sqlx::Error>;
pub async fn count_ui_events_since(pool: &SqlitePool, since_ts_text: &str) -> Result<i64, sqlx::Error>; // event_type IN ('app_switch','window_focus')
pub async fn count_frame_changes_since(pool: &SqlitePool, since_ts_text: &str) -> Result<i64, sqlx::Error>;
```

- [ ] **Step 1: 写迁移文件**

`20260822120000_create_intent_cards.sql`，DDL 抄 T4 决议原文：

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

- [ ] **Step 2: 写数据访问层与失败测试**

新建 `db/intent_cards.rs`。测试建池方式照 crate 内既有先例（`write_queue.rs` 测试用 `SqlitePool::connect("sqlite::memory:")`），再跑迁移：

```rust
#[cfg(test)]
async fn test_pool() -> sqlx::SqlitePool {
    let pool = sqlx::SqlitePool::connect("sqlite::memory:").await.unwrap();
    sqlx::migrate!("./src/migrations").run(&pool).await.unwrap();
    pool
}

#[tokio::test]
async fn mark_shown_sets_expiry_and_finish_only_from_shown() {
    let pool = test_pool().await;
    let id = insert_intent_card(&pool, &sample_card()).await.unwrap();
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
    let id = insert_intent_card(&pool, &sample_card()).await.unwrap();
    assert!(mark_shown(&pool, id, 1_000_000).await.unwrap());
    assert!(!mark_shown(&pool, id, 99_000_000).await.unwrap()); // 二次调用拒绝
    let row = list_pending(&pool).await.unwrap().into_iter().next().unwrap();
    assert_eq!(row.shown_at, Some(1_000_000));                  // 时钟未被续命
    assert_eq!(row.expires_at, Some(1_000_000 + 48 * 3600));
}
```

同文件再加三个测试：dedup 同 key 同日命中返回原 id、`expire_due` 只结算 shown 且 expires_at 已到、新手卡 `expires_at = NULL` 不被结算。先跑一遍确认编译失败/断言失败。

- [ ] **Step 3: 实现**

逐函数实现到测试全绿。`mark_shown` 与 `finish` 同款守卫：UPDATE 带 `WHERE status='proposed'` / `WHERE status='shown'`，受影响行数为 0 即返回 false。两个时间格式注意点：
- `intent_cards` 自身时间列是 INTEGER unixepoch（chrono `Utc::now().timestamp()`）。
- `ui_events.timestamp` 与 `frames.timestamp` 是 SQLite DATETIME 文本列（RFC3339 文本）。传参格式照既有查询函数抄：`db/search.rs` 的 `get_frames_in_range_for_export` 怎么 bind 时间范围，这两个函数就怎么 bind。先读该函数确认格式再落码，不要传 unix 秒。

- [ ] **Step 4: 注册模块**

`db/mod.rs` 在 `mod memories;` 一组里插 `mod intent_cards;`，文件尾部加 `pub use self::intent_cards::{...};`（列出上面 Interfaces 全部公开项），风格与相邻 `pub use self::semantic::{...}` 一致。结构衔接点一并确认：这些是自由函数（吃 `&SqlitePool`），而 src-tauri 侧经 `live_db()` 拿到的是 `Arc<DatabaseManager>`。落码时读 `db/setup.rs` 与 semantic 模块：若 DatabaseManager 有公开的池访问入口，自由函数照用；若没有，就把这组函数改成 `impl DatabaseManager` 的方法（semantic 模块同款风格），签名不变、只挪宿主。

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

### Task 2: intent_agent 模块骨架与纯逻辑

**Files:**
- Create: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/mod.rs`
- Create: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/gate.rs`
- Create: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/prompt.rs`
- Create: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/parse.rs`
- Modify: `apps/screenpipe-app-tauri/src-tauri/src/main.rs`（声明模块）

**Interfaces:**
- Consumes: 无外部依赖，全部纯函数。
- Produces（Task 3/4 依赖）:

```rust
// mod.rs
pub mod gate; pub mod parse; pub mod prompt;
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
pub const DEFAULT_WINDOW_SECS: i64 = 24 * 3600;      // 无卡时的默认窗口
pub const MAX_WINDOW_SECS: i64 = 7 * 24 * 3600;      // R2：窗口硬上限
pub const GATE_SOURCE: &str = "gate";
pub fn should_attempt_generation(s: &WindowSignals) -> bool;
pub fn dedup_key(card_type: &str, dominant_app: &str) -> String;
pub fn window_start(now: i64, latest_card_at: Option<i64>) -> i64;

// parse.rs
pub struct GeneratedPlan { pub title: String, pub summary: String, #[serde(default)] pub consequence: String }
pub struct GeneratedCard { pub card_type: String, pub proactive_view: String, pub recommended_index: usize, pub plans: Vec<GeneratedPlan> }
pub enum ModelOutcome { Card(GeneratedCard), InsufficientMaterial }
pub fn parse_model_output(raw: &str) -> Result<ModelOutcome, String>;

// prompt.rs
pub fn build_messages(input: &GenerationInput) -> Vec<serde_json::Value>;
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
    // 无卡：默认 24h 窗口
    assert_eq!(window_start(now, None), now - DEFAULT_WINDOW_SECS);
    // 最近一张卡很久以前：窗口封顶在 MAX_WINDOW_SECS，不无限增长
    assert_eq!(window_start(now, Some(now - 90 * 24 * 3600)), now - MAX_WINDOW_SECS);
    // 最近一张卡很近：从卡时刻起算
    assert_eq!(window_start(now, Some(now - 3600)), now - 3600);
}
```

Run: `bun scripts/pre_build.js && cargo test --manifest-path apps/screenpipe-app-tauri/src-tauri/Cargo.toml intent_agent::gate`
Expected: 编译失败（函数未定义）。此后纯逻辑文件的测试先行步骤相同，不再重复写 Expected。

- [ ] **Step 2: 实现 gate.rs**

常量按 Interfaces 原文；`should_attempt_generation` 为两个 OR；`dedup_key` 空 app 归 `general`；`window_start = max(latest_card_at.unwrap_or(now - DEFAULT_WINDOW_SECS), now - MAX_WINDOW_SECS)`。窗口封顶的理由：连续 insufficient_material 时 latest_created_at 不更新，无上限窗口会让 activity-summary 变慢、材料更稀释，正反馈恶化（R2）。

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
    let card: GeneratedCard = serde_json::from_value(v).map_err(|e| e.to_string())?; // 默认宽容未知字段
    if card.plans.is_empty() { return Err("empty plans".into()); }
    if !matches!(card.card_type.as_str(), "light" | "side_effect" | "read_only") {
        return Err(format!("bad card_type {}", card.card_type));
    }
    Ok(ModelOutcome::Card(card))
}
```

测试覆盖：围栏剥离、`insufficient_material:true` 分支、缺 `v` 或 `v!=1` 报错、空 plans 报错、非法 card_type 报错、正常解析出 recommended_index、未知额外字段不报错。

- [ ] **Step 4: 写并实现 prompt.rs**

system 消息要点：角色说明；输出必须是单个 JSON 对象且顶层带 `"v": 1`；三种 card_type 定义（light/side_effect/read_only）；plans 数组 1–3 项、首项为推荐项；材料不足时返回 `{"insufficient_material": true}`。user 消息放 `activity_summary` 的 JSON 文本（超长时先 `truncate_string(summary, 12_000)`，文件头加 `#![deny(clippy::string_slice)]`）与信号计数。测试断言 messages[0] 含 "JSON"、user 消息含传入的窗口起止文本。

- [ ] **Step 5: main.rs 声明模块**

在 crate 根作用域加 `mod intent_agent;`（与 `mod suggestions;` 相邻）。

- [ ] **Step 6: 跑测试**

```bash
cargo test --manifest-path apps/screenpipe-app-tauri/src-tauri/Cargo.toml intent_agent
git checkout -- apps/screenpipe-app-tauri/src-tauri/gen/schemas/
```

- [ ] **Step 7: Commit**

```bash
git add apps/screenpipe-app-tauri/src-tauri/src/intent_agent apps/screenpipe-app-tauri/src-tauri/src/main.rs
git commit -m "feat(intent-agent): add capped generation gate, versioned output parser, and prompt builder"
```

---

### Task 3: 模型直调客户端与 endpoint 解析

**Files:**
- Create: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/model_call.rs`
- Modify: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/mod.rs`（`pub mod model_call;`）

**Interfaces:**
- Consumes: Task 2 的 `build_messages`。
- Produces:

```rust
#[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct IntentModelEndpoint { pub url: String, pub model: String, pub api_key: String }

pub fn builtin_ollama_default() -> IntentModelEndpoint; // http://localhost:11434/v1 + qwen3.5:9b + ""
pub fn resolve_endpoint(slot: Option<IntentModelEndpoint>, mirror_resolved: Option<IntentModelEndpoint>)
    -> (IntentModelEndpoint, &'static str); // ("slot"|"mirror"|"builtin")
pub async fn generate_card(ep: &IntentModelEndpoint, messages: &[serde_json::Value])
    -> Result<String, String>; // 返回 choices[0].message.content
```

注意：`resolve_endpoint` 吃的是**已解析**的 mirror endpoint。mirror preset id 到 endpoint 的现查在 runner 层做（Task 4），本模块保持纯解析。

- [ ] **Step 1: resolve_endpoint 失败测试**

slot 有值用 slot；slot 空用 mirror；两者皆空用 `builtin_ollama_default()`。三断言各验 tag 与 url。

- [ ] **Step 2: 实现 resolve_endpoint 与 generate_card**

`generate_card` 照 `suggestions.rs::generate_ai_suggestions` 的 reqwest 构造（POST `{url}/chat/completions`，api_key 非空才加 Bearer 头，30s timeout，非 2xx warn 并转 Err，成功取 `choices[0].message.content`）。`temperature` 取 0.7、`max_tokens` 取 800。

- [ ] **Step 3: 跑测试并提交**

```bash
cargo test --manifest-path apps/screenpipe-app-tauri/src-tauri/Cargo.toml resolve_endpoint
git checkout -- apps/screenpipe-app-tauri/src-tauri/gen/schemas/
git add apps/screenpipe-app-tauri/src-tauri/src/intent_agent/model_call.rs apps/screenpipe-app-tauri/src-tauri/src/intent_agent/mod.rs
git commit -m "feat(intent-agent): add two-level fallback endpoint resolution and direct model call"
```

---

### Task 4: 心跳循环宿主与推送

**Files:**
- Create: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/runner.rs`
- Modify: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/mod.rs`（`pub mod runner;`）
- Modify: `apps/screenpipe-app-tauri/src-tauri/src/events.rs`（新增事件常量）
- Modify: `apps/screenpipe-app-tauri/src-tauri/src/main.rs`（setup 里 spawn）

**Interfaces:**
- Consumes: Task 1 db 函数、Task 2 gate/parse/prompt、Task 3 model_call、现成 `live_db()` 模式（`meeting_export.rs`）、`recording.rs::LocalApiContext`、`events.rs` emit 模式。
- Produces:

```rust
// events.rs 追加
pub const INTENT_CARD_EVENT: &str = "intent_card_created";
pub fn emit_intent_card_created(app: &tauri::AppHandle, card_id: i64);

// runner.rs
pub async fn start(app: tauri::AppHandle); // 常驻循环，永不返回
pub(crate) struct GenerationRecord { pub ok: bool, pub detail: Option<String>, pub source: &'static str }
pub(crate) async fn tick(app: &tauri::AppHandle) -> Result<Option<GenerationRecord>, String>;
pub(crate) async fn read_supply(app: &tauri::AppHandle)
    -> (Option<model_call::IntentModelEndpoint>, Option<String>); // (slot, mirror_preset_id)，读 SettingsStore.extra
pub(crate) async fn resolve_mirror_endpoint(app: &tauri::AppHandle, preset_id: &str)
    -> Option<model_call::IntentModelEndpoint>; // 按 id 去 store.bin 的 aiPresets 现查（D1）
pub(crate) fn write_last_generation(app: &tauri::AppHandle, rec: &GenerationRecord); // 写 extra 的 intent_last_generation 键
```

- [ ] **Step 1: 核对四处现成签名再动笔**

- 读 `notifications/client.rs` 的 `send_typed_with_actions_and_priority` 参数表与 `NotificationPriority` 类型；
- 读 `recording.rs::LocalApiContext` 与 `commands.rs::get_local_api_config` 的取用法；
- 读 `notifications/gate.rs` 的 `load_guard` 看 SettingsStore.extra 的读取入口，并找它的写入侧函数；
- **D1 关键确认**：store.bin 里 aiPresets 的存储键名，以及 Rust 侧能否读到该 JSON（哪怕以 `serde_json::Value` 形式）。读得到就走 id 现查主路径；读不到则退回镜像三元组方案（前端改镜像 endpoint，并在 `components/settings/ai-presets.tsx` 保存回调补触发点），此时 Task 5 的 `intent_set_fallback_mirror` 参数改为 `Option<IntentModelEndpoint>` 并同步改 Task 8 Step 2。

runner 的代码以下一步为准，签名不一致处以实测为准。

- [ ] **Step 2: 实现 events.rs 追加**

```rust
pub const INTENT_CARD_EVENT: &str = "intent_card_created";
pub fn emit_intent_card_created(app: &tauri::AppHandle, card_id: i64) {
    let _ = app.emit(INTENT_CARD_EVENT, serde_json::json!({ "cardId": card_id }));
}
```

- [ ] **Step 3: 实现 runner.rs**

`start`：`sleep(FIRST_RUN_DELAY_SECS)` 后进 `interval(HEARTBEAT_INTERVAL_SECS)` 循环，tick 出错记 tracing 不退出。spawn 方式照 `main.rs` setup 里 suggestions scheduler 那行。

`tick` 流程（顺序固定）：

```rust
let db = live_db(app).await?;                                  // 照 meeting_export.rs 的 live_db
let now = chrono::Utc::now().timestamp();
db_expire_due(&db, now).await?;                                // 1. 过期结算先行（T8 决议 3）
let latest = latest_created_at(..).await?;
let window_start_ts = gate::window_start(now, latest);         // 2. 封顶窗口（R2）
let signals = WindowSignals {
    app_switches: count_ui_events_since(..).await?,
    frame_changes: count_frame_changes_since(..).await?,
};
if !gate::should_attempt_generation(&signals) { return Ok(None); } // 3. 门槛
let summary = fetch_activity_summary(app, window_start_ts).await?; // 4. localhost GET :3030/activity-summary
let input = GenerationInput { /* 窗口文本、summary、signals */ };
let (slot, mirror_id) = read_supply(app).await;
let mirror_ep = match mirror_id.as_deref() {
    Some(id) => resolve_mirror_endpoint(app, id).await, None => None };
let (ep, source) = model_call::resolve_endpoint(slot, mirror_ep);
let record = match model_call::generate_card(&ep, &prompt::build_messages(&input)).await {
    Ok(raw) => match parse::parse_model_output(&raw) {
        Ok(ModelOutcome::InsufficientMaterial) => GenerationRecord { ok: true, detail: Some("material insufficient".into()), source },
        Ok(ModelOutcome::Card(c)) => {
            let key = gate::dedup_key(&c.card_type, &dominant_app(&input));
            let date = chrono::Local::now().format("%Y-%m-%d").to_string(); // 本地自然日（T4 决议 5）
            let id = insert_intent_card(/* D4 结构序列化 plans_json */).await?;
            emit_intent_card_created(app, id);
            notify_new_card(app, id, &c).await?;                  // 5. notification-panel，闸门照单全收
            GenerationRecord { ok: true, detail: None, source }
        }
        Err(e) => GenerationRecord { ok: false, detail: Some(e), source },
    },
    Err(e) => GenerationRecord { ok: false, detail: Some(e), source },
};
write_last_generation(app, &record);
Ok(Some(record))
```

`notify_new_card` 组 payload 调 client.rs 的发送函数，闸门照单全收（T5 决议 2）。payload 带结构化字段 `{cardType, topPlanTitle}`：plan title 是模型产出的用户语言内容、不经字典直接用；面板上的静态词与 i18n 渲染归前端侧。若 client.rs 签名强制传成形的 title/body 字符串，title 用 topPlanTitle、body 用 proactive_view 截断（`truncate_string(_, 120)`）。

`fetch_activity_summary`：GET `http://127.0.0.1:{port}/activity-summary?start_time={}&end_time={}&include_apps=true&include_windows=true`，Bearer api_key，30s timeout。时间格式先读 `crates/screenpipe-engine/src/routes/activity_summary.rs` 的 `ActivitySummaryQuery` 解析方式再定：它是 flexible 解析、吃 ISO 8601 / 相对时间 / 日历日，`start_time >= end_time` 直接 400——传 ISO 8601，不要传 unix 秒。

- [ ] **Step 4: main.rs 接线**

setup 段 suggestions auto-start 那行旁边加：

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
git commit -m "feat(intent-agent): add resident heartbeat loop with capped window, expiry settlement, and panel notification"
```

---

### Task 5: Tauri commands（唯一写入口）与绑定生成

**Files:**
- Create: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/commands.rs`
- Modify: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/mod.rs`（`pub mod commands;`）
- Generated: `apps/screenpipe-app-tauri/lib/utils/tauri.ts`（bindings:generate 产出，不手编）

前置动作：调 skill `screenpipe-tauri`。

**Interfaces:**
- Consumes: Task 1 db 函数（经 `live_db`）、Task 3 `IntentModelEndpoint`、Task 4 supply 读写。
- Produces（TS 侧经 `commands.*` 调用，Result 包装 `{status:"ok",data}|{status:"error",error}`）:

```rust
#[derive(Serialize, Deserialize, specta::Type)] pub struct IntentCardDto { /* IntentCardRow 全字段 */ }
#[derive(Serialize, Deserialize, specta::Type)]
pub struct IntentSupplyState { slot: Option<IntentModelEndpoint>,
    fallback_preset_id: Option<String>,           // D1 v2：镜像存 id 不存三元组
    last_generation: Option<LastGenerationStatus> }
#[derive(Serialize, Deserialize, specta::Type)]
pub struct LastGenerationStatus { at: i64, ok: bool, detail: Option<String>, source: String }

#[tauri::command] #[specta::specta] pub async fn intent_list(filter: String) -> Result<Vec<IntentCardDto>, String>; // "pending"|"accepted"
#[tauri::command] #[specta::specta] pub async fn intent_card_mark_shown(app: tauri::AppHandle, card_id: i64) -> Result<(), String>;
#[tauri::command] #[specta::specta] pub async fn intent_card_decide(app: tauri::AppHandle, card_id: i64, decision: String) -> Result<(), String>; // "accepted"|"rejected"
#[tauri::command] #[specta::specta] pub async fn intent_spawn_onboarding_card(app: tauri::AppHandle) -> Result<i64, String>;
#[tauri::command] #[specta::specta] pub async fn intent_get_supply(app: tauri::AppHandle) -> Result<IntentSupplyState, String>;
#[tauri::command] #[specta::specta] pub async fn intent_set_slot(app: tauri::AppHandle, endpoint: Option<IntentModelEndpoint>) -> Result<(), String>;
#[tauri::command] #[specta::specta] pub async fn intent_set_fallback_preset_id(app: tauri::AppHandle, preset_id: Option<String>) -> Result<(), String>;
```

若 Task 4 Step 1 走了退回路径（Rust 读不到 aiPresets），`fallback_preset_id` 与 `intent_set_fallback_preset_id` 相应换成 `fallback_endpoint: Option<IntentModelEndpoint>` / `intent_set_fallback_mirror`，命名保持与数据同构。

- [ ] **Step 1: 写状态机命令的失败测试**

```rust
// commands.rs 内 #[cfg(test)]
#[tokio::test]
async fn decide_rejects_non_shown_cards() {
    // 内存池 + 迁移（同 Task 1 测试手法），插入 proposed 卡
    // 直接调内部 handler：decide 应返回错误，mark_shown 后 accepted 成功
}

#[tokio::test]
async fn decide_is_idempotent_safe() { // R1 配套：重复 decide 第二次失败且不改终态
    // mark_shown → accept 成功 → 再次 accept 返回错误，status 仍 accepted
}
```

- [ ] **Step 2: 实现各 command**

- `intent_card_decide` 校验 decision ∈ {"accepted","rejected"}，经 `finish()` 落库（SQL WHERE status='shown' 保证四条转移之外不可能发生）。
- `intent_spawn_onboarding_card`（D5）：构造固定 plans（D4 结构、kind onboarding_mcp，detected_agents 从 `skills.rs` 的探测函数结果取；探测失败给空数组），origin=`system_onboarding`、dedup_key=`system_onboarding:onboarding`、expires_at=NULL，入库后 emit 事件并发面板提醒，返回 id。
- supply 三件套读写 SettingsStore.extra 的 `intent_slot` / `intent_fallback_preset_id` / `intent_last_generation` JSON 键，读写入口以 Task 4 Step 1 核对的 gate.rs 及其写入侧为准。

- [ ] **Step 3: 注册与重新生成绑定**

command 函数保持 pub（registry 按完整路径命名）。然后：

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

### Task 6: 工作台 section 骨架（前端）

**Files:**
- Modify: `apps/screenpipe-app-tauri/lib/utils/sidebar-nav-layout.ts`（SidebarNavId 加 `"workbench"`）
- Modify: `apps/screenpipe-app-tauri/app/(main)/home/page.tsx`（四处：MainSection 类型、ALL_SECTIONS、SIDEBAR_SECTION_DEFS、renderMainSection case）
- Create: `apps/screenpipe-app-tauri/components/intent-workbench/index.tsx`
- Create: `apps/screenpipe-app-tauri/lib/i18n/en-intent-workbench.ts` · `zh-intent-workbench.ts`
- Modify: `apps/screenpipe-app-tauri/lib/i18n/en.ts` · `zh-CN.ts`（合并分片）
- Modify: browser-mock IPC shim（位置见 Step 4）

**Interfaces:**
- Consumes: Task 5 生成的 `commands.intentList / intentGetSupply`。
- Produces: `<IntentWorkbench />`（Task 7 在其中填充卡片体）；i18n 命名空间 `workbench.*`。

- [ ] **Step 1: 注册 section 四处改动**

照侦察钉死的位置：`sidebar-nav-layout.ts` 的 SidebarNavId 联合类型加 `"workbench"`；`home/page.tsx` 的 ALL_SECTIONS 数组（当前约 L123）、SIDEBAR_SECTION_DEFS（当前约 L1039）、renderMainSection switch（当前约 L955）三处各加 workbench 条目（label 用 `t("shell.nav.workbench")`，icon 选 lucide 的 `Sparkles`）。行号会随分支演进漂移，以名字检索为准。默认排位放 activity 之后。

- [ ] **Step 2: i18n 骨架键集**

`en-intent-workbench.ts` 导出对象并入 en.ts 的 `workbench` 命名空间（zh 同构）。本任务先落骨架键；卡片文案键（`workbench.card.*`）随 Task 7 补进同一分片，两批键合起来才是 v1 完整清单：

```ts
export const intentWorkbenchEn = {
  nav: "Workbench",
  filterPending: "Pending decisions",
  filterFinished: "Finished",
  empty: "No intent cards yet.",
  emptyOnboardingCta: "Generate the onboarding card",
  loading: "Loading…",
} as const;
```

zh-CN 对应简短桌面语（「工作台」「待决定」「已结束」「还没有意图卡片」「生成新手接入卡」「加载中…」）。

- [ ] **Step 3: 列表骨架组件**

`components/intent-workbench/index.tsx`：两个 Filter tab（本地 state），pending 时 `commands.intentList("pending")`、finished 时 `("accepted")`；加载态照 ActivityLedger 的 skeleton 写法，空态用上面的键。列表项先渲染占位行，Task 7 替换为真卡片。视觉 token 对照原型资产：`#121212` 底、22% 灰边框、6px 圆角、白底黑字主按钮。

- [ ] **Step 4: browser-mock stub**

```bash
rg -l "SCREENPIPE_WEB_SCENARIO" apps/screenpipe-app-tauri --glob '!node_modules'
```

定位 mock IPC shim 后为八个 intent command 加 fixture 分支（两张 pending 卡：一张 light 提案、一张 system_onboarding；一张 accepted 卡），空场景返回空数组。

- [ ] **Step 5: 验证**

```bash
cd apps/screenpipe-app-tauri
SCREENPIPE_WEB_SCENARIO=ready bun run dev:web   # 打开 http://127.0.0.1:1420/home?section=workbench 截图对照原型
bun run test                                    # i18n 键完整性等
```

- [ ] **Step 6: Commit**

```bash
git add lib/utils/sidebar-nav-layout.ts app/\(main\)/home/page.tsx components/intent-workbench lib/i18n
git commit -m "feat(workbench): register workbench section with pending/finished filters"
```

---

### Task 7: 卡片组件、裁决交互与事件接线

**Files:**
- Create: `apps/screenpipe-app-tauri/components/intent-workbench/intent-card.tsx`
- Create: `apps/screenpipe-app-tauri/components/intent-workbench/plans-list.tsx`
- Modify: `apps/screenpipe-app-tauri/components/intent-workbench/index.tsx`（替换占位行）
- Modify: `apps/screenpipe-app-tauri/app/(main)/home/page.tsx`（两个事件监听）

**Interfaces:**
- Consumes: `commands.intentCardMarkShown / intentCardDecide`；`useTauriEvent`；INTENT_CARD_EVENT payload `{cardId:number}`。
- Produces: 完整可裁决工作台。

- [ ] **Step 1: plans-list（方案选择）**

props: `plansJson: string`。解析 D4 结构（校验 `v===1`）；radio 列表，`recommended_index` 默认选中；选中项下方显示 consequence 行；末行虚线 radio + 输入框（原型 plan-compose 模式）：回车或失焦把输入钉成本地方案并选中、挂「你的方案」角标。轻提示卡不显示方案列表，只显示 proactive_view 正文。

- [ ] **Step 2: intent-card（按钮矩阵与状态呈现）**

- pending 卡：提案按钮组「接受选中方案 / 不要」，轻提示「知道了 / 不要」，都调 `commands.intentCardDecide(id, ...)`，Result 错误分支 toast；点击后乐观移出列表。
- shown 回写：pending 列表渲染完成后对每张 `status==='proposed'` 的卡调 `intentCardMarkShown(id)`，组件内 `useRef<Set<number>>` 防重。**幂等由 SQL 层兜底（R1）**：即使组件重挂载或多窗口导致重复调用，第二次调用被 WHERE status='proposed' 拒绝，时钟不会续命；前端防重只是省一次往返。
- finished 卡只读，显示终态徽标。
- 五状态样式对照原型图例；「正在准备」（proposed 未回写前）标注为库里存在、界面短暂过渡态。
- 新手接入卡（`origin==='system_onboarding'`）：按 T6 文案渲染 detected_agents 行，主按钮「接入」调 `commands.intentCardDecide(id,"accepted")` 后由 Rust 侧触发连接（D5，Task 8 补触发点）。

- [ ] **Step 3: 事件接线（home/page.tsx）**

```tsx
useTauriEvent<{ cardId: number }>("intent_card_created", () => queryClient.invalidateQueries(["intent-list"]));
useTauriEvent<{ actionType?: string }>("notification:action", (e) => {
  if (e.actionType === "open_intent_workbench") setActiveSection("workbench");
});
```

事件名以 `events.rs` 的 `NOTIFICATION_ACTION_EVENT` 实值为准（侦察记录为 `"notification:action"`）。**平台门控备注**：该事件常量在 Rust 侧是 cfg 门控的（macOS/Windows 才编译），目标平台 macOS 下无影响；Linux 走 webview 分支，「查看」action 的转发通路接线时需单独确认这条分支是否存在，不存在则 Linux 上降级为仅面板展示、无跳转（记入 PR 说明即可，不阻塞 macOS 主线）。

- [ ] **Step 4: i18n 卡片文案键**

`workbench.card.*` 并入 Task 6 建立的分片：accept/reject/knownOk/noThanks/customPlanBadge/yourPlan/recommended/consequenceLabel/status 五值/onboarding.title/onboarding.detectLine 等，en 先加、zh 补齐。按钮文案对照 T6 定稿：「知道了 / 不要」「接受选中方案 / 不要」。至此 `workbench.*` 清单收口，后续任务不再新增键。

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

### Task 8: 设置页 intent 槽、fallback 镜像与端到端测通

**Files:**
- Modify: `apps/screenpipe-app-tauri/components/settings/ai-settings.tsx`
- Modify: `apps/screenpipe-app-tauri/lib/active-ai-preset.ts`（镜像写入点）
- Modify: `apps/screenpipe-app-tauri/src-tauri/src/intent_agent/commands.rs`（新手卡接受后触发连接）
- Modify: `doc/FEATURE_MODEL_INVOCATION_INVENTORY.md`（补 PATH 编号）

**Interfaces:**
- Consumes: `commands.intentSetSlot / intentSetFallbackPresetId / intentGetSupply / intentSpawnOnboardingCard`；`AIPresets`（use-settings.tsx）。

- [ ] **Step 1: 设置页 intent 槽卡片**

AISettings 内加一块卡片：preset 选择器枚举 `AIPresets`（选项含「跟随 Chat（默认）」，对应 slot=None）；选定后把该 preset 的 `{url, model, api_key}` 经 `intentSetSlot` 写入。下方常显两行信息（评审 R7）：当前生效来源 tag 与端点 host+model（slot / mirror / builtin 三种来源都要显示，mirror 来源显示解析出的实际端点而非仅「跟随 Chat」字样）；以及 `last_generation`（最近成败 + 失败原因）。这样 slot/mirror 指向远端 URL 时，发往哪里在设置页始终可见。失败不打扰工作台（T7 决议 3）。

- [ ] **Step 2: fallback 镜像（D1 v2：镜像 id 不镜像三元组）**

`lib/active-ai-preset.ts`：`resolveActiveAiPreset` 结果变化与应用首次加载两个时机，把 **preset id** 经 `intentSetFallbackPresetId` 上送。api_key 编辑、url 变更等 preset 内容修改不需要重新上报——心跳每次按 id 去 aiPresets 现查，内容天然新鲜（D1 主路径）。若 Task 4 Step 1 走了退回路径（Rust 读不到 aiPresets），此处改上送三元组，并把 `ai-presets.tsx` 的保存回调加入镜像触发点。

- [ ] **Step 3: 新手卡接受触发点**

`intent_card_decide` 命中 accepted 且卡 origin 为 system_onboarding 时，tokio spawn 调 `skills.rs::connect_detected_ai_tools_in_background(api_auth_enabled, api_port)`，失败仅 tracing（D5）。此路径是状态机铁律的唯一已知例外，备忘已在 D5 记档。

- [ ] **Step 4: 盘点文档补登**

按 `doc/FEATURE_MODEL_INVOCATION_INVENTORY.md` 阶段 0 要求为意图卡片生成补登一个 `PATH-*` 条目（T7 边界声明的义务）。

- [ ] **Step 5: 端到端测通（真实 app，跨原生边界）**

```bash
bun run dev:tauri
```

清单：设置页选 Ollama 槽 → 点「生成新手接入卡」→ 面板弹提醒（闸门静音时被抑制也算通过闸门验证）→ 点开进工作台 → 接受 → 状态变 accepted 且 skills 连接日志出现 → 手动插一张 expires_at 已过的 shown 卡重启，验证心跳醒来先结算 expired → 把系统时间快进场景下重复 mark_shown，验证时钟不被续命（R1 端到端复核）。全程无账户登录。

- [ ] **Step 6: Commit**

```bash
git add components/settings/ai-settings.tsx lib/active-ai-preset.ts src-tauri/src/intent_agent doc/FEATURE_MODEL_INVOCATION_INVENTORY.md
git commit -m "feat(workbench): intent model slot in settings, chat preset mirror, onboarding connect hook"
```

---

## 验收清单（对照 Spec）

| Spec 要求 | 落点 |
| --- | --- |
| intent_cards 十二列最小表 + dedup 唯一索引（T4） | Task 1 |
| Rust 心跳 + 单次直调，节拍判据分离，随引擎常驻（T3） | Task 2/3/4 |
| 上下文 = 查询窗口增长且有硬上限（T3 决议 4 + R2） | Task 4 window_start 逻辑 |
| 主窗口新增 section，两个 Filter，新手卡随第一版（T5） | Task 6 |
| 到卡提醒复用 notification-panel 闸门（T5） | Task 4 notify_new_card |
| 五值状态机四条转移，写入唯一入口，过期挂心跳，时钟不可续命（T8 + R1） | Task 1/4/5 |
| 两级回退 + 内置 Ollama 默认，失败日志加设置页可见，来源可感知（T7 + R7） | Task 3/5/8 |
| 按钮组收窄：知道了/不要、接受/不要，接受只写终态（T5） | Task 7 |
| 新手接入卡落 MCP 真实机制（T6/D5） | Task 5/7/8 |
| i18n 全覆盖、Cue 品牌边界、provenance 头 | 各任务 + Global Constraints |
| PATH-* 补登（T7 边界声明） | Task 8 Step 4 |

## 明确不做（防蔓延）

执行与终态链路、重写流程、记忆基底、记账三件套、BYOK 引导 UI、卡片快捷键、「执行中」Filter、Daily Summary 持久化、chat active preset 整体迁入 SettingsStore（D1 只镜像 id，整迁移留给执行链路 effort）。出现这些诉求时停下来说明，另行开票。

## 评审修订记录

v2（2026-08-22），依据外部评审采纳情况：

- **R1（采纳，正确性）**：`mark_shown` 加 WHERE status='proposed' 单向守卫，新增重复调用测试与端到端复核步；Global Constraints 补「过期时钟不续命」。
- **R2（采纳，正确性）**：gate.rs 新增 MAX_WINDOW_SECS=7 天与 window_start 封顶逻辑及测试，杜绝 insufficient_material 连发导致的窗口正反馈膨胀。
- **R3（改良采纳）**：镜像从 endpoint 三元组改为 preset id，心跳侧现查 aiPresets，消除凭证陈旧腐烂点；chat 激活态整体迁入 SettingsStore 不在本 effort 做（爆炸半径超范围），列入明确不做；T7 语义偏离在 D1 显式声明。
- **R4（采纳）**：plans_json 全形态带 `"v":1`，解析器拒未知版本、宽容未知字段。
- **R5（不采纳改动，采纳备忘）**：CHECK 保留，理由是 T4 决议 4 的显式裁决优先；rebuild 成本写入 Schema 备忘。
- **R6（采纳）**：新手卡 accept 例外记入 D5 备忘，执行链路 effort 启动时统一。
- **R7（部分已覆盖，补强）**：设置页 supply 卡常显生效来源+端点 host，覆盖 mirror 来源。
- **R8（采纳备忘）**：dedup 索引编码产品策略一事记入 D2 备忘。
- 实测核对项：前端行号更新为当前实况（注明漂移风险）、NOTIFICATION_ACTION_EVENT 平台门控备注入 Task 7、i18n 键清单矛盾句修正（骨架键/卡片键分两批、Task 7 收口）、activity-summary 时间格式明令禁 unix 秒。
