# 模型调用路径盘点与重构路线

<!-- doc-covers: crates/screenpipe-core/src/agents, crates/screenpipe-core/src/pipes, crates/screenpipe-audio/src, apps/screenpipe-app-tauri/lib, apps/screenpipe-app-tauri/src-tauri/src -->
<!-- doc-verified: c761541585c4f70e84ed5f77558bceae18732ca5 -->
> **Current。** 本文按上述提交核验，是重构基线，不代表后续实现不会变化。

## 1. 文档目的

Screenpipe 当前通过多个运行时访问模型。主 Chat 和 Pipe 路径使用 Pi 子进程；Suggestions、ACP Agent、音频转录、隐私过滤和说话人识别各自有独立边界。如果重构时把这些调用都归为 Pi 路径，就会漏掉模型请求、凭证、持久化和观测。

本文记录：

- 哪些产品能力会触发模型推理；
- 实际执行推理的技术路径；
- 输入和输出数据；
- 权限校验位置；
- 持久化行为；
- 任务属于 Agent LLM 还是其他模型工作负载；
- 后续统一调用和 Trace 层需要覆盖哪些接入点。

本文使用两层视角：

```text
功能路径
  → 技术路径
    → Provider / Model
      → 持久化、权限、观测
```

## 2. 统计口径

### 2.1 纳入统计

- Agent LLM；
- 视觉语言模型和云端媒体模型；
- 语音转文字模型及远程转录服务；
- PII 脱敏模型；
- 说话人分段和 Embedding 模型；
- 后台调用和诊断调用，只要可能把数据发送给模型 Provider，就纳入统计。

### 2.2 不计入模型推理

- `GET /v1/models` 模型发现；
- Screenpipe Cloud Gateway 的转发、鉴权和计量逻辑；
- 确定性的语义解析器和启发式 Suggestions；
- 测试 Fixture 和 Mock ACP Agent；
- 只读写已经生成的模型结果、但没有再次推理的 API。

语义解析器规格明确要求不按帧调用 LLM。它仍然影响模型输入数据，但不计入模型调用路径。

### 2.3 “路径”的含义

功能矩阵按产品能力统计一次；技术矩阵按运行时边界统计一次。因此多个功能路径可以共用同一技术路径。

例如，Interactive Chat、Daily Summary 和 Pipe 都使用 Pi 子进程，但它们的触发方式、输入范围、输出用途和持久化行为不同，仍然保留为三条功能路径。

## 3. 总览

### 3.1 技术路径

| 路径 ID | 运行时边界 | 典型工作负载 | 与 Pi SDK 的关系 |
|---|---|---|---|
| `ROUTE-PI` | Rust/Tauri 启动 Bun 和 Pi CLI，通过 JSON/RPC 或 NDJSON 传输事件 | Chat、Pipe、摘要、标题、Live View | 由 Pi 执行 |
| `ROUTE-ACP` | Tauri 启动 ACP Runtime，再通过 stdio JSON-RPC 启动外部 Adapter | Claude、Codex、Cursor、Copilot、OpenCode、Kimi | 不由 Pi Agent SDK 执行 |
| `ROUTE-DIRECT-CHAT` | Tauri Rust 或前端直接发送 OpenAI/Anthropic 兼容请求 | Suggestions、BYOK 连接测试 | 直连 |
| `ROUTE-PI-TOOL-HTTP` | Pi Agent 调用工具或命令，工具再发起模型请求 | 会议媒体分析 | Pi 触发，但请求独立 |
| `ROUTE-REMOTE-STT` | 音频进程向 Deepgram 或 Screenpipe Cloud 上传音频 | 批量和实时转录 | 不经过 Pi |
| `ROUTE-LOCAL-STT` | 音频进程加载 Whisper、Qwen3 ASR 或 Parakeet | 批量和实时转录 | 不经过 Pi |
| `ROUTE-PRIVACY-MODEL` | Server 选择 ONNX 或 Tinfoil Adapter | 文本/图像 PII 过滤 | 不经过 Pi |
| `ROUTE-SPEAKER-MODEL` | 音频进程运行分段和 Speaker Embedding | 说话人识别 | 不经过 Pi |

### 3.2 功能路径

| 路径 ID | 功能 | 模型类别 | 技术路径 | 是否远程 | 主要结果 |
|---|---|---|---|---|---|
| `PATH-PI-CHAT` | 交互式 Chat | `agent-llm` | `ROUTE-PI` / `ROUTE-ACP` | 取决于 Provider | 回复、工具调用、会话 |
| `PATH-PI-PIPE` | 定时、手动和事件触发的 Pipe | `agent-llm` | `ROUTE-PI` | 取决于 Provider | Pipe 输出、文件、外部副作用 |
| `PATH-PI-DAILY` | Daily Summary | `agent-llm` | `ROUTE-PI` | 取决于 Provider | 摘要文本 |
| `PATH-PI-LIVE-VIEW` | Live View 生成 | `agent-llm` | `ROUTE-PI` | 取决于 Provider | 结构化视图操作 |
| `PATH-PI-FIRST-RUN` | 首次运行摘要 | `agent-llm` | `ROUTE-PI` | 取决于 Provider | 引导摘要 |
| `PATH-PI-TITLE` | AI 标题生成 | `agent-llm` | `ROUTE-PI` | 取决于 Provider | 短标题 |
| `PATH-PI-NOTIFICATION` | 通知触发的 Chat/Pipe | `agent-llm` | `ROUTE-PI` | 取决于 Provider | Chat 或 Pipe 结果 |
| `PATH-ACP` | 外部 ACP Agent | `agent-llm` | `ROUTE-ACP` | 通常是 | 外部 Agent 回复和工具调用 |
| `PATH-SUGGESTIONS` | Enhanced AI Suggestions | `agent-llm` | `ROUTE-DIRECT-CHAT` | 是 | 缓存的 Suggestions |
| `PATH-PRESET-TEST` | AI Preset 连接测试 | `agent-llm` | `ROUTE-DIRECT-CHAT` | 取决于 Preset | 测试结果 |
| `PATH-MEETING-MEDIA` | 可选的会议视觉分析 | `vision-language-model` | `ROUTE-PI-TOOL-HTTP` | 是 | 会议摘要所需视觉事实 |
| `PATH-REMOTE-STT` | Deepgram 和 Screenpipe Cloud 转录 | `speech-to-text` | `ROUTE-REMOTE-STT` | 是 | 转录片段 |
| `PATH-LOCAL-STT` | Whisper、Qwen3 ASR、Parakeet | `speech-to-text` | `ROUTE-LOCAL-STT` | 否 | 转录片段 |
| `PATH-PII` | 本地或 Tinfoil PII 脱敏 | `pii-redaction-model` | `ROUTE-PRIVACY-MODEL` | 取决于后端 | 脱敏文本或图像 |
| `PATH-SPEAKER` | 说话人分段和 Embedding | `embedding-model` / `classifier` | `ROUTE-SPEAKER-MODEL` | 否 | 说话人片段和匹配结果 |

## 4. 每条路径必须记录的字段

### 场景与触发

- 用户或系统执行了什么动作；
- 手动、定时、事件、启动或后台轮询；
- 默认是否开启；
- 是否允许并发；
- 是否支持取消。

### 实现

- 前端、Rust 或 TypeScript 入口；
- 实际发起请求的进程；
- 子进程、SDK、本地 Runtime 或 HTTP Endpoint；
- 是否流式；
- 重试、限流和 fallback；
- 失败和取消行为。

### Pi SDK 关系

| 值 | 含义 |
|---|---|
| `direct-pi` | 主模型请求由 Pi Runtime 发起 |
| `pi-mediated` | Pi 通过工具或命令触发二次模型请求 |
| `acp` | 请求由 ACP Adapter 发起 |
| `direct-http` | Screenpipe 自己发送模型请求 |
| `local-runtime` | 推理在本地模型 Runtime 中执行 |
| `provider-sdk` | 直接调用 Provider SDK |
| `not-applicable` | 没有模型推理 |

### 持久化

分别记录：

- Prompt、音频、图像和上下文；
- Session ID、Execution ID；
- Stream、Tool Call、Retry 和 Error；
- 模型输出；
- Cache；
- Token、Cost、Latency；
- Credential 及其存储位置；
- 删除、保留期和历史开关。

请求发生、请求输入、模型输出、Usage 被记录，是四个不同的持久化问题。

### 权限

分为四层：

1. 功能开关和用户确认；
2. 登录、JWT、订阅和 Cloud Entitlement；
3. API Key、OAuth、Ollama 和 ACP Adapter 鉴权；
4. 麦克风、屏幕录制、Local API 和外部连接器写入权限。

### 多模态

需要同时记录输入和传输方式：

- Text、OCR、Accessibility Tree、Audio、Image、Frame、Video-derived Frame；
- 本地内存、文件路径、Multipart、Base64、URL 或 Tool Result；
- Text、Transcript、结构化对象、Embedding、Classification 或 Redaction。

### 模型类别

建议使用工作负载类别，而不是只写“大模型/小模型”：

- `agent-llm`
- `vision-language-model`
- `speech-to-text`
- `embedding-model`
- `pii-redaction-model`
- `classifier`
- `heuristic-no-model`

只有源码或模型配置明确给出参数量时，才记录参数规模。

## 5. 功能路径详情

### PATH-PI-CHAT：交互式 Chat

**场景。** 用户在 Chat UI 发送 Prompt。选中的 AI Preset 决定使用 Pi Backend 还是 ACP Backend。

**实现。** Tauri Sidecar 以 RPC 模式启动 Pi。`piStart`、`piPrompt`、`piStop` 管理进程。Pi 配置写入 Screenpipe 专用 Pi 安装目录，Pi 通过 JSON 事件把消息和工具状态交回应用。

**Pi SDK。** Pi Preset 为 `direct-pi`；ACP Preset 为 `acp`。Screenpipe 通过外部 Bun 子进程使用 Pi，不是在自身代码中直接调用 `createAgentSession`。

**持久化。** 应用保存 Session ID、流式消息、Tool 状态和 Chat History。Provider 请求体和统一模型调用 Ledger 目前不是独立持久化边界。

**权限。** Screenpipe Cloud 使用 Cloud Token；BYOK 使用 Preset 中的 Key 或本地 Provider；ACP 使用 Adapter 自己的鉴权。

**多模态。** 主接口是文本，但 Pi 可以通过工具查询 OCR、Accessibility、Audio、Memory 和 Frame。

**模型类别。** `agent-llm`。Provider 和 Model 可配置。

### PATH-PI-PIPE：Pipe 和自动化

**场景。** Pipe 可以手动、定时、事件触发或由通知触发，也可以继续已有会话。

**实现。** Pipe Scheduler 调用 `PiExecutor`，以 Print 或 Streaming JSON 模式启动 Pi。运行中的 Pi 可以查询 Local API、调用 Extension/MCP、写 Artifact 并输出 NDJSON。

**Pi SDK。** `direct-pi`。

**持久化。** Pipe 配置、执行日志、输出文件和会话视图分开保存。Pipe 规格记录了 `~/.screenpipe/pipes/{name}/logs/`、Pi 配置目录和 Pipe Output 目录。Prompt、Usage、Cost、Retry 目前没有统一记录保证。

**权限。** 需要 Pipe 已启用或被显式执行。Provider Credential 来自解析后的 Preset 和 Pi 配置。Tool 可能读取 Local API、写文件或调用连接器。

**多模态。** Agent 通过 Tool 查询 OCR、Accessibility、Audio Transcript 和 Frame，也可能按 Pipe 指令上传图像。

**模型类别。** `agent-llm`。模型可以是 Cloud Provider、Ollama 或其他配置的 Provider。

### PATH-PI-DAILY、PATH-PI-LIVE-VIEW、PATH-PI-FIRST-RUN、PATH-PI-TITLE

这四项都使用独立的 Pi Session，但应保留为不同功能路径：

| 路径 | 入口 | 输出 | 持久化差异 | 特殊条件 |
|---|---|---|---|---|
| Daily Summary | `lib/daily-summary-pi.ts` | Markdown 摘要 | 结果由 Summary 功能消费，临时 Session 不一定是产品记录 | 只调查指定日期 |
| Live View | `lib/live-views/generate-live-view-with-pi.ts` | 结构化 View 操作 | 保存后的 Live View 是持久记录 | Tool Allowlist 更窄 |
| First-run Summary | `lib/first-run/summarize-with-ai.ts` | 引导文案 | 结果写入 Onboarding 状态，有确定性 Fallback | ACP Preset 被拒绝 |
| AI Title | `lib/utils/generate-title-with-preset.ts` | 短标题 | 标题写回目标 Conversation | ACP Chat 不会把消息转给另一个 Provider 生成标题 |

它们共同使用 `direct-pi` 和 `agent-llm`，但输入范围、输出用途、Fallback 和隐私要求不同。

### PATH-PI-NOTIFICATION：通知触发

通知可以打开一个带 Prompt 的新 Chat，也可以后台运行指定 Pipe。通知层本身不是模型 Runtime，而是触发源，实际执行分别归入 `PATH-PI-CHAT` 或 `PATH-PI-PIPE`。

### PATH-ACP：外部 ACP Agent

**场景。** 用户选择 Claude Code、Codex、Cursor、GitHub Copilot、OpenCode 或 Kimi 等 ACP Preset。

**实现。** Tauri 启动隐藏 ACP Runtime。Runtime 使用 Rust `agent-client-protocol` SDK，通过 stdio JSON-RPC 与外部 Adapter 通讯，并注入 MCP Server、Session Defaults、Screenpipe Skills 和指定环境变量。

**Pi SDK。** `acp`。模型循环和 Provider 请求由外部 Adapter 管理，不能因为从 Chat 入口启动就归类为 Pi。

**持久化。** Screenpipe 可以保存 Conversation 和 UI Event；Adapter 原生 Session、Provider Request Body 和 Usage 是否能保存，取决于 ACP 暴露的信息。

**权限。** Runtime 会过滤敏感环境变量并注入 Adapter Credential。Screenpipe MCP 和用户注册 MCP 是独立权限边界。

**多模态。** 取决于 Adapter 能力。Screenpipe 可以通过 MCP 提供 Screen、Audio、OCR 等上下文，但 Provider 层能力并不统一。

**模型类别。** `agent-llm`。

### PATH-SUGGESTIONS：Enhanced AI Suggestions

**场景。** 应用可以每十分钟生成一次 Suggestions，也可以在会议开始或结束后刷新。Force Regenerate 会绕过 CPU 和电源调度限制。

**实现。** `src-tauri/src/suggestions.rs` 收集近期 Activity，直接向 Screenpipe Gateway 发送 OpenAI-compatible 请求，模型为 `auto`。Enhanced AI 未开启或没有 Token 时，使用确定性模板。

**Pi SDK。** `direct-http`。

**持久化。** 当前结果放在内存 Cache 中。它不创建 Pi Session，也没有统一模型调用记录。

**权限。** 需要开启 Enhanced AI 且提供非空 Cloud Token。近期 Activity Context 会发送到 Cloud。CPU 和电源检查是调度条件，不是数据权限。

**多模态。** 请求主要由 Activity、Window、OCR 和 Transcript 组成的文本上下文构成，不上传图像。

**模型类别。** `agent-llm`，远程，具体 Provider 由 Gateway 决定。

### PATH-PRESET-TEST：AI Preset 连接测试

**场景。** 用户在 Settings 中测试 BYOK 或本地 Provider。

**实现。** `lib/utils/ai-preset-connection.ts` 直接选择以下 Endpoint：

- OpenAI：`/v1/chat/completions`；
- Anthropic：`/v1/messages`；
- Ollama：`/v1/chat/completions`；
- Custom：用户配置的 OpenAI-compatible Endpoint。

请求是有边界的非流式测试请求，部分 Provider 的 Token Limit 字段不兼容时会重试。

**Pi SDK。** `direct-http`。

**持久化。** 测试结果返回给 Settings，不创建 Pi Session 或普通 Chat Transcript。Provider Settings 和 Credential 的存储不能与请求持久化混为一谈。

**权限。** 使用 Preset 中的 Provider Credential。它不是 Screenpipe Cloud Entitlement 的替代品。

**多模态。** Text-only。

**模型类别。** `agent-llm`，通常是一次短 Prompt，但仍具有真实 Provider 请求的隐私和鉴权影响。

### PATH-MEETING-MEDIA：可选会议视觉分析

**场景。** 会议摘要指令要求：只有 Transcript 和 OCR 无法回答具体的图表、白板、幻灯片或演示问题时，才分析 Frame。

**实现。** Pi Agent 获取有限数量的 Frame ID，最多取四张图，以 `image_url[]` 发送到 `/v1/chat/completions`，模型为 `gemma4-e4b`。这条指令是条件性的，不代表每次会议都会调用视觉模型。

**Pi SDK。** `pi-mediated`。Pi 触发调用，但媒体请求是独立的模型调用，不能只从 Pi Text Stream 统计。

**持久化。** Frame、Meeting Note 和最终 Summary 可能持久化；媒体请求、图像、Usage 和 Cost 目前没有统一持久化保证。

**权限。** 需要 Cloud Token。缺少 Cloud Media 配置或收到 `cloud_token_missing` 时跳过。会议和 Frame 数据会离开设备。

**多模态。** Text 加 Frame Image。

**模型类别。** `vision-language-model`，远程。仓库只明确了模型 ID，没有给出参数规模。

### PATH-REMOTE-STT：远程转录

**场景。** Audio Capture 可以选择 Deepgram、Screenpipe Cloud 或 OpenAI-compatible 远程转录 Endpoint。会议实时转录还有独立的 Provider 选择。

**实现。** Audio Crate 提供 Deepgram 和 OpenAI-compatible Batch Client；Meeting Streaming Controller 在 Cloud、Deepgram-live、本地引擎和 Disabled 之间选择。

**Pi SDK。** `direct-http` 或 `provider-sdk`，不经过 Pi。

**持久化。** Transcript Segment 会进入 Audio 和 Meeting 数据。原始上传 Audio、请求 Body、Retry 和 Usage 的保留规则需要单独确定。

**权限。** 需要音频采集权限、Provider API Key 或 Cloud Entitlement。Cloud Transcription 是明确的数据出机选择。

**多模态。** Audio 输入、Text Transcript 输出。

**模型类别。** `speech-to-text`，不能归入 Agent LLM。

### PATH-LOCAL-STT：本地转录

**场景。** 用户选择本地 Transcription Engine，或设备按配置使用本地引擎。

**实现。** `screenpipe-audio` 通过 `whisper_rs` 加载 Whisper，通过 `audiopipe` 加载 Qwen3 ASR、Parakeet 和 Parakeet MLX。

**Pi SDK。** `local-runtime`。

**持久化。** Model Weight 在本地 Cache；Transcript 进入 Audio 和 Meeting Storage。不存在 Provider Request 或 Pi Session。

**权限。** 需要 Audio Capture 权限和本地 Model 可用。模型下载是网络操作，但不属于推理本身。

**多模态。** Audio 输入、Text 输出。

**模型类别。** `speech-to-text`。具体参数规模应从实际 Model 配置读取。

### PATH-PII：隐私过滤

**场景。** Captured 或生成的 Text、Image 在保存或下游使用前进行脱敏。

**实现。** Tauri Server 根据配置选择本地 ONNX 或 Tinfoil Adapter，处理 Text 和 Image。

**Pi SDK。** ONNX 为 `local-runtime`，Tinfoil 为 `provider-sdk`。

**持久化。** Redacted Result 可能替代或伴随原始数据保存。原始输入保留规则、远程 Tinfoil 请求记录和删除规则必须单独制定。

**权限。** Local Backend 需要本地 Model；Tinfoil 需要 Token、Attestation 和相关配置。Backend 选择本身就是数据出机决策。

**多模态。** 取决于 Adapter，可以是 Text、Image 或两者。

**模型类别。** `pii-redaction-model`。

### PATH-SPEAKER：说话人分段和 Embedding

**场景。** Audio Pipeline 对说话人分段，并将匿名说话人与已有身份匹配。

**实现。** Audio Pipeline 使用本地 Segmentation 和 ONNX Embedding，再使用相似度和聚类逻辑。

**Pi SDK。** `local-runtime`。

**持久化。** Model File 在本地 Cache；Speaker Segment、Label 和 Match 结果可能随 Audio/Meeting 保存。Embedding 的保留期限需要隐私策略。

**权限。** 使用已采集的 Audio 和本地 Model，不需要已识别生产路径中的远程 Provider Credential。

**多模态。** Audio 输入、Vector 和 Speaker Label 输出。

**模型类别。** `embedding-model` 和 `classifier`。

## 6. 持久化横向对照

| 数据 | 当前行为 | 重构问题 |
|---|---|---|
| Pi Session 和 Stream Message | Chat/事件层维护 | 每个 Pi Event 能否携带统一 Invocation ID |
| Pipe Execution Log | Pipe Log 目录和 Conversation Materialization | Prompt、Provider、Retry、Usage、Output 能否进入同一记录 |
| Suggestions | Suggestions State 中的内存 Cache | 是否保留请求和结果，保留多久 |
| Preset Test | 返回 Settings，无普通 Chat Transcript | 诊断请求是否进入 Audit View |
| Meeting Summary | Meeting Note 和 Summary Output | 媒体调用能否关联到 Summary Turn |
| Remote STT | Transcript 和 Meeting Storage | 原始上传 Audio 是否保留 |
| Local STT | Local Model Cache 和 Transcript Storage | 如何记录 Model Load、Latency 和 Failure |
| PII | Redacted Content 和 Privacy Backend | 原始和脱敏版本如何区分和删除 |
| Speaker Model | Segment、Label 和 Local Model Cache | Embedding 保留多久 |
| Token、Cost、Latency | Gateway 可能计量部分请求，本地路径不统一 | 哪个系统是权威 Usage Record |

## 7. 权限横向对照

| 边界 | 示例 | 当前问题 |
|---|---|---|
| 功能开关 | Enhanced Suggestions、Pipe、Transcription Engine | 状态分散在 Settings 和 Runtime |
| 账户权限 | Cloud Token、Plan、Cloud Media、Cloud STT | Token 证明身份，不一定证明工作负载有权限 |
| Provider Credential | BYOK Key、OAuth、Ollama、ACP Auth | Pi、ACP、前端和 Audio 的注入方式不同 |
| 本地采集 | 麦克风、System Audio、Screen、Accessibility | 模型输入来源离模型调用点较远 |
| 外部副作用 | Pipe Output、Tool Call、Connected Apps | 模型请求只读，不代表模型结果不会写外部系统 |
| 数据出机 | Cloud Chat、Cloud Media、Deepgram、Tinfoil | 没有统一的出机前记录 |

## 8. 当前观测缺口

1. Pi 有 JSON/RPC 和 NDJSON Event，但还不是完整的 Provider Request Ledger。
2. ACP 有自己的生命周期和 Adapter 边界，Pi Hook 无法观察 Adapter 内部请求。
3. Direct Chat 和 STT 没有共用 Invocation Event Contract。
4. Pi Turn 可能触发二次媒体请求，Agent Event 不能代表全部模型流量。
5. Gateway Usage 与本地 Session Event 不一定有稳定关联 ID。
6. Local Model 的加载、Inference Latency、Cache 和 Failure 没有和远程请求统一。
7. API Key、JWT、原始 Audio、Image 和 Screen Context 在进入日志或外部 Trace 前需要统一脱敏。

## 9. 重构目标

建议建立与 Provider 无关的 Model Invocation Envelope：

```text
功能调用
  → Invocation ID
    → Model Route
      → Provider Adapter 或 Local Runtime
        → request.started
        → request.completed / request.failed
        → usage.reported
```

默认只携带元数据，不携带敏感 Payload：

```json
{
  "invocation_id": "每次请求唯一",
  "parent_session_id": "可选的 Agent 或 Meeting Session",
  "feature_path": "PATH-SUGGESTIONS",
  "route": "ROUTE-DIRECT-CHAT",
  "runtime": "tauri-rust",
  "provider": "screenpipe-cloud",
  "model": "auto",
  "modality": ["text"],
  "data_egress": "remote",
  "trigger": "scheduled",
  "status": "started"
}
```

Envelope 至少需要支持：

- Pi Turn、Tool Call、二次媒体请求的父子关系；
- 本地和远程 Runtime；
- Retry 和 Provider Fallback；
- 已报告、估算和缺失的 Usage；
- 已脱敏的 Prompt 和 Payload 摘要；
- Retention 和 Delete Metadata；
- ATA 等外部 Trace Consumer 的稳定导出接口。

## 10. 重构路线

### 阶段 0：冻结盘点

- 保留本文的核验 Commit；
- 新增生产 Model Runtime 时同步新增 `PATH-*`；
- 功能路径和技术路径分开编号；
- Review 时检查新的 `chat/completions`、`messages`、STT、Redaction 和 Local Runtime 入口。

### 阶段 1：建立调用身份

- 在功能边界生成 `invocation_id`；
- 保留 Pi Session、Pipe Execution、Meeting、Audio Chunk 等现有 ID；
- 为二次媒体请求增加 Parent ID；
- 不把 API Key、JWT、原始 Audio、原始 Image 放进 Envelope。

### 阶段 2：接入 Pi 和 Pipe

- 将 Pi JSON/RPC 和 Pipe NDJSON 转换为统一 Envelope；
- 记录 Provider、Model、功能路径、触发源、Retry 和终止状态；
- 保留当前 UI Event Contract，不让 Audit Contract 反向污染 UI；
- 继续以 Screenpipe 专用 Pi 安装目录和 `PI_CODING_AGENT_DIR` 为边界。

### 阶段 3：包装直连请求

- 接入 Suggestions；
- 将 AI Preset Connection Test 标记为诊断调用；
- 接入 Deepgram、Screenpipe Cloud STT、OpenAI-compatible STT 和会议媒体请求；
- Provider 暴露 Usage 时记录 Usage。

### 阶段 4：接入 ACP

- 在 ACP Session 创建、Prompt、Tool Call、Result、完成和失败处发出事件；
- 协议提供 Usage 时记录 Usage；
- 保持 Adapter 身份与 Pi 身份分离；
- 不猜测 Adapter 没有暴露的 Provider HTTP 细节。

### 阶段 5：接入本地模型

- 记录 Model Load、Cache Hit/Miss、Inference Start/End、Device 和 Failure；
- 覆盖 Whisper、Qwen3 ASR、Parakeet、ONNX PII、Tinfoil、Segmentation 和 Speaker Embedding；
- 通用 Trace 只保存 Model ID、Hash 和受限元数据。

### 阶段 6：接入 ATA

ATA 的现有 Pi Plugin 可以作为 Pi Hook 的第一消费者。要覆盖 Screenpipe 全部模型调用，还需要 Direct Call、ACP 和 Local Model 的额外接入。

推荐映射：

```text
Pi Agent Event
  → ATA 现有 Pi Translation

Direct Agent / HTTP Call
  → Canonical Message/Turn 或 Model Invocation Event

STT、PII、Embedding、Local Inference
  → Model Invocation Event
```

给 ATA 增加 `screenpipe` 标签有助于筛选，但不会自动产生缺失的事件。

## 11. 验收标准

重构完成后应满足：

- 每个生产模型入口都有稳定的 `PATH-*`；
- 每次调用都能识别 `ROUTE-*`、Runtime、Provider 和 Model；
- Pi、ACP、Direct HTTP、Remote STT、Local Inference 可区分；
- Feature Trigger、Parent Session、Child Invocation 可查询；
- Retry、Fallback、Cancel 和 Failure 可观测；
- Usage、Cost、Latency 有值，或明确标记为不可用；
- 数据是否出机是显式字段；
- 请求元数据进入日志和外部 Trace 前已脱敏；
- Input、Output、Cache、Usage 的持久化和删除行为有文档；
- 新增 Model Route 必须同步更新 Inventory 和 Instrumentation Test；
- ATA 可以消费 Agent Trace，而不会把 STT、PII、Embedding 伪装成 Agent Turn。

## 12. 证据索引

- `crates/screenpipe-core/src/agents/pi.rs`：Pi 包版本、Provider 配置、Pi 子进程和流式输出。
- `crates/screenpipe-core/src/pipes/mod.rs`：Pipe 调度和执行。
- `apps/screenpipe-app-tauri/src-tauri/src/pi.rs`：交互式 Pi Sidecar、ACP Dispatch、Event Routing 和 Provider 配置。
- `apps/screenpipe-app-tauri/src-tauri/src/acp_runtime.rs`：ACP Runtime、Adapter 启动、MCP 注入和环境过滤。
- `apps/screenpipe-app-tauri/src-tauri/src/suggestions.rs`：Direct Suggestions 请求和 Enhanced AI Gate。
- `apps/screenpipe-app-tauri/lib/utils/ai-preset-connection.ts`：Provider 连接测试。
- `apps/screenpipe-app-tauri/lib/utils/meeting-context.ts`：可选 Cloud Media 请求指令。
- `crates/screenpipe-audio/src/transcription/engine.rs`：Whisper、Qwen3 ASR 和 Parakeet。
- `crates/screenpipe-audio/src/transcription/deepgram`：Deepgram 转录。
- `crates/screenpipe-audio/src/transcription/openai_compatible`：OpenAI-compatible STT。
- `apps/screenpipe-app-tauri/src-tauri/src/server_core.rs`、`crates/screenpipe-redact/src/adapters/tinfoil.rs`：隐私模型选择和 Tinfoil Adapter。
- `crates/screenpipe-semantic`：确定性语义解析，以及不按帧调用 LLM 的边界。
