# T5 · api_hint 注入评估

Labels: wayfinder:research (AFK)
Blocked by: （无，前沿票）
Claimed by:

## Question

评估是否照 `pi.rs:3101-3104` 的现成模式（`is_local_model` 时 `--append-system-prompt` 注入一条提示），给意图卡片会话注入「先从 skill 读完整工作流程」的 api_hint：

1. 意图卡片会话走的是 Pi 子进程会话（T3 上张图修订），system prompt 是 REPLACE 注入（`instruct.rs::build_system_prompt`）；确认 REPLACE 后 pi 的 `<available_skills>` 索引仍然附加、skill 可被发现（上张图已验证过一次，找到该结论的出处并复核对当前版本仍成立）；
2. hint 应指向哪些 skill：cue-tools 必读没有争议；要不要同时点名 screenpipe-api？给出取舍理由（上下文预算 vs 信息完整性）；
3. 只对 local model 注入还是所有模型注入；hint 的措辞草案；
4. 结论供流程文本票直接采用。

## Resolution

Status: Resolved
Claimed by: pis（调研会话，2026-08-25）

### 结论

照做，但收窄三点：hint 直接写进 `instruct.rs::build_system_prompt()` 的 REPLACE 文本，不必新开 `--append-system-prompt` 旗标；只点名 cue-tools，不点名 screenpipe-api；对所有模型注入，不只 local。措辞与注入位置供票 06 落地时直接采用。

### 1. REPLACE 后 skill 仍可被发现：出处与复核

- **出处不在归档《意图卡片落点》里。** 归档 tickets/plan 全文检索 `available_skills`、`api_hint` 均无命中。这条结论首次成文是 commit `428d534b0`（2026-08-24，「replace pi's built-in persona with a static Chinese prompt」，即引入 REPLACE 注入的那个提交）写进 instruct.rs 的注释："verified against pi dist source"。此前只存在于验证过程，没有落过书面档案。
- **复核对当前版本成立。** 复核对象是本机安装的 pi 0.84.1（`~/.cue/pi-agent/node_modules/@earendil-works/pi-coding-agent/dist/`）：
  - `core/system-prompt.js::buildSystemPrompt` 的 customPrompt 分支：替换 prompt 之后依次拼接 append 文本、project context files、`<available_skills>` 技能索引、cwd 行。索引附加条件是 selectedTools 含 `read`——意图白名单含 `read`（`INTENT_ALLOWED_TOOLS` 经 `apply_pi_tool_allowlist` 以 `--tools` 下发）。
  - `core/resource-loader.js` L329-331、L501：`--no-skills` 只关闭自动发现，显式传入的技能路径（CLI enabled 路径与 additional 路径两路合并）仍然加载，两路皆空才得到空技能集。宿主的技能物化（baseline 三件 + cue-tools + store 镜像，见 core `ensure_cue_agent_skills`）全部经显式 `--skill` 进入会话。
  - 附带确认：`--system-prompt` 与 `--append-system-prompt` 可以共存，append 文本拼在替换文本之后（同一分支的 appendSection 逻辑）。这意味着现有通用 hint 在 local 模型下已经能与 REPLACE prompt 同场出现。

### 2. hint 指向哪些 skill

- **cue-tools 必点名。** 工作流正典（工具分工地图、判重纪律、草稿收敛规则、时区约定）都在这份技能里；instruct.rs 刻意只留指针不复述细节，hint 是把指针变成硬指令。本图终点「完整生成流程写进 system prompt 与 cue-tools skill」也要求两处互相咬合。
- **screenpipe-api 不点名。** 意图会话没有 bash，结构上不能直连本地 HTTP API；它的本地数据访问全部走预包装扩展工具（intent-search.ts 四件 + sp_mcp_*），鉴权由宿主 env 注入，模型用不上该技能教的 auth/endpoint 细则。点名只会多诱导一次无收益的 read，占首拍上下文预算。
- **附带事实（票外）**：现有通用 api_hint（pi.rs:3099-3104，`is_local_model` 时 append「先读 screenpipe-api」）位于 `pi_start_inner` 的 native 公共链路，意图会话同样经过——供给解析映射到 ollama/custom 时，每次 tick 都会把这条英文 hint 拼在中文 persona 后面。对意图会话属于轻微跑靶：无害，但引导一次无关 read。要不要抑制留给实现期裁决，不在本票范围。

### 3. 注入范围：所有模型

- 建议不限 local。理由：(a) 一句话成本可忽略；(b) 出卡质量取决于流程被遵循，无人值守下失败是静默的，不该赌模型自觉读技能；(c) 现有 `is_local_model` 门控的性质是补偿弱模型的指令遵循，与这条「去哪读流程」的路由指令不同类。
- 若沿用 local 门控，注入与否就跟随供给解析结果：内置兜底 `native-ollama` 经 `pi_registry_provider`（pi.rs:2403）映射为 `ollama`，命中现有判定（绑定在 pi.rs:2633，判定在 3101）；mirror/slot 为 Ollama 类 preset 的用户同样命中。slot/mirror 选 openai / anthropic / screenpipe-cloud 的用户则拿不到任何保障。
- 注入位置建议直接写进 build_system_prompt() 的 REPLACE 文本，一行即可。最终拼接顺序与单独旗标完全等价（persona → hint → 技能索引），少一个移动部件；票 06 重写该函数时顺势落地。

### 4. 措辞草案（中文）

> 开始分析前，先用 read 工具完整读取 cue-tools 技能文件（路径见下方 `<available_skills>` 索引）。工具分工地图、判重纪律、草稿收敛规则与时区约定以该文件为准，对本任务强制适用。

选中文的理由：整条 persona 与卡片产出都是中文，内置默认模型 qwen3.5 也是中文强模型，单一语言域减少切换成本。现有 chat 侧 api_hint 用英文大写祈使句，那是无实测支撑的既有惯例；实现期若想对齐先例，把草案译成英文不影响以上任何一条结论。

### 未复核项

- 未跑真实 intent tick 做端到端观察。验证方式是 dist 源码走读加 spawn 链路代码核对：`cli/args.js` → `main.js` resourceLoaderOptions → `resource-loader.js` → `agent-session.js::_rebuildSystemPrompt` → `system-prompt.js`，主链闭合，但没有运行时输出佐证。
- 复核钉在本机安装的 pi 0.84.1；pi 升级后此结论需重验。
