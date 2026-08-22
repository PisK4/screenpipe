# 本地优先构建模式重构

<!-- doc-covers: apps/screenpipe-app-tauri/lib/local-learning-mode.ts, apps/screenpipe-app-tauri/app/providers.tsx, apps/screenpipe-app-tauri/app/onboarding/page.tsx, apps/screenpipe-app-tauri/app/(main)/settings/page.tsx, apps/screenpipe-app-tauri/components/app-entitlement-gate.tsx, apps/screenpipe-app-tauri/components/chat/standalone/free-plan-wall.tsx, apps/screenpipe-app-tauri/components/chat/standalone/upgrade-quota-banner.tsx, apps/screenpipe-app-tauri/components/settings/ai-presets.tsx, apps/screenpipe-app-tauri/lib/chat/provider-errors.ts, apps/screenpipe-app-tauri/lib/hooks/use-settings.tsx, apps/screenpipe-app-tauri/lib/hooks/use-usage-status.tsx, apps/screenpipe-app-tauri/components/rewind/timeline/daily-summary.tsx, apps/screenpipe-app-tauri/scripts/build-frontend.js, apps/screenpipe-app-tauri/scripts/dev-enterprise.ts, apps/screenpipe-app-tauri/src-tauri/Cargo.toml, apps/screenpipe-app-tauri/src-tauri/src/main.rs, apps/screenpipe-app-tauri/src-tauri/src/pi.rs, apps/screenpipe-app-tauri/src-tauri/src/recording.rs, apps/screenpipe-app-tauri/src-tauri/src/analytics.rs, apps/screenpipe-app-tauri/src-tauri/tauri.enterprise.conf.json -->
<!-- doc-verified: b6bed101f1763d9baf570e2b2cdedeca56152291 -->
> **Current。** 本文按上述提交核验，记录桌面端本地优先模式的基线。后续改动应以代码和测试为准。

## 1. 目的

Screenpipe 的默认桌面构建以本地优先方式运行。屏幕和音频采集、录制、设置保存，以及用户已经配置好的模型 Provider，不以 Screenpipe 账户、订阅资格或云端用量为前提。

这项重构改变的是桌面端的默认运行边界，不是把产品变成绝对离线软件。默认预设指向本机 Ollama，但用户可以把 Provider URL 改为内网或互联网地址；模型请求是否离开设备，取决于所选 Provider。

云端账户构建和企业构建仍是独立路径。企业构建继续使用自己的认证、策略和原生授权逻辑。

## 2. 模式判定与构建边界

前端的唯一模式判定在 `lib/local-learning-mode.ts`：

```text
NEXT_PUBLIC_SCREENPIPE_LOCAL_LEARNING !== "false"
```

没有显式设置该变量时，Next 静态导出把它固定为 `"true"`。原生端的默认 Cargo feature 也包含 `local-learning`。因此，普通消费者构建和本地开发默认进入本地优先模式。

企业路径显式退出该模式：

| 构建场景 | 前端模式 | 原生 feature | 结果 |
|---|---|---|---|
| 默认消费者构建 | 未设置或非 `"false"` | `local-learning` | 本地优先 |
| 显式非本地前端构建 | `"false"` | 由调用方决定 | 保留云端账户界面和 gate |
| 企业开发与打包 | `"false"` | `enterprise-build` | 企业策略优先，不走本地绕过 |

`tauri.enterprise.conf.json` 使用 `dev:enterprise` 和 `build-frontend.js --enterprise` 设置前端变量；原生的录制和遥测绕过同时排除 `enterprise-build`。仅改前端环境变量，不能把企业二进制变成本地模式。

## 3. 必须同时成立的行为

这个模式跨越前端、原生端和构建配置，不能只做一个页面的条件渲染。下列边界需要一起成立：

1. **采集和录制。** 非企业本地构建允许开始录制，不要求云端账户或订阅状态。`recording_access_allowed` 在这一组合下直接允许。
2. **账户和资格。** `AuthBoundary` 不挂载 `AuthGuard`，`AppEntitlementGate` 直接放行子树。设置初始化也不安装账户失效拦截器，不在启动时刷新账户资料。
3. **产品遥测。** 前端不初始化 PostHog，不发送 onboarding 与设置变更事件，也不轮询 hosted AI 用量。原生启动前设置 `SCREENPIPE_DISABLE_TELEMETRY=1`，分析管理器同样拒绝启用产品遥测。
4. **云端商业界面。** 账户、团队、推荐、免费额度墙和升级提示不渲染；设置导航和设置搜索结果也不能把这些入口暴露出来。
5. **AI 能力。** 新建默认设置提供 Ollama 预设，用户可调整 Base URL、模型和可选 API Key。Pi 配置在有 Key 时通过 `OLLAMA_API_KEY` 传递，没有 Key 时不伪造认证值。
6. **企业隔离。** 本地模式下的放行、遥测禁用和云端界面收起都不能覆盖企业构建的策略。

这里的“产品遥测”不包含用户主动配置的模型 Provider 请求。调用远程 Provider 时，模型输入仍可能按该 Provider 的协议离开设备。

## 4. 首次运行与功能入口

本地模式的 onboarding 只引导完成运行应用所需的动作：

```text
权限
  → 时间线选择（仅低配置设备）
    → 引擎启动
      → Home
```

登录、来源归因和套餐选择不在这个流程中。已完成 onboarding 的判断和窗口跳转仍复用原有存储与命令边界。

功能入口不能只因其位于 Timeline、Chat 或 Pipe 之外，就重新要求云端身份。Daily Summary 的修复是现有例子：本地模式直接使用当前默认的非 ACP AI 预设生成摘要，不要求登录或开启 Enhanced AI。未配置模型时，界面应提示去 Settings 配置 Provider，而不是把用户带到登录页。

## 5. Provider 与数据边界

新安装的本地默认预设为：

| 字段 | 默认值 |
|---|---|
| Provider | `native-ollama` |
| URL | `http://localhost:11434/v1` |
| Model | `qwen3.5:9b` |
| 默认预设 | 是 |

Ollama Provider 不再假定服务一定在固定 localhost 地址，也可以带可选 API Key。模型列表、预检、连接测试和 Pi 子进程配置都必须使用同一 URL 与认证信息。已有用户的预设不会被这项默认值覆盖；本地模式下也不会为已有预设自动补入 Screenpipe Cloud 预设。

“本地优先”的数据承诺应在这里止步：

- Screenpipe 的录制资格、账户校验和产品遥测不依赖云端；
- 默认 Provider 是本机 Ollama；
- 用户改用远程或内网 Provider 后，模型请求的传输与保留策略由该 Provider 决定；
- 不得借“本地模式”暗示所有 AI 请求、模型下载或用户配置的网络连接都被禁止。

## 6. 后续改动检查

涉及下列内容的改动，应同时检查本地模式与企业模式：

| 改动类型 | 本地优先模式应检查的结果 |
|---|---|
| 新的录制、采集或健康 gate | 不得把账户、套餐或 hosted entitlement 变成启动前提 |
| 新的 AI 功能 | 已配置的本地/兼容 Provider 可用；缺少 Provider 时提示配置，不跳转登录 |
| 新的用量、升级或账户 UI | 本地模式不显示入口，也不能通过搜索、深链或覆盖层绕过隐藏 |
| 新的 analytics 或远程日志 | 不初始化、不排队、不发送 Screenpipe 产品遥测 |
| Provider 配置或 Pi 接入 | URL、可选认证和模型发现路径一致；不把 Key 写进日志或文档 |
| 企业构建改动 | `enterprise-build` 继续优先，不能继承消费者本地放行 |

检查时至少覆盖一个首次启动路径、一个已存在设置的路径，以及一个由用户主动触发的 AI 功能。这样能发现“主入口已放行、外围功能仍被登录或额度拦截”的遗漏。

## 7. 回归证据

本次基线包含以下回归点：

- Ollama 的自定义 URL 和可选 API Key 能用于连接测试；
- Ollama URL 与 API Key 的输入校验允许该组合；
- Pi 的 `models.json` 只在 Ollama Key 非空时引用 `OLLAMA_API_KEY`；
- Ollama 的模型预检、模型列表和上下文窗口读取使用配置后的 URL 与认证；
- Daily Summary 优先使用用户显式选择的默认预设；本地模式不因未登录或未开启 Enhanced AI 阻止生成。

新增本地模式分支时，应在其最窄的边界加入测试。不要只验证模式函数返回值，也不要只验证页面是否隐藏。

## 8. 证据索引

- `apps/screenpipe-app-tauri/lib/local-learning-mode.ts`：前端模式判定。
- `apps/screenpipe-app-tauri/app/providers.tsx`、`components/app-entitlement-gate.tsx`：认证和 entitlement 边界。
- `apps/screenpipe-app-tauri/app/onboarding/page.tsx`：本地 onboarding 流程。
- `apps/screenpipe-app-tauri/lib/hooks/use-settings.tsx`、`components/settings/ai-presets.tsx`、`src-tauri/src/pi.rs`：默认 Provider 与 Ollama 配置链路。
- `apps/screenpipe-app-tauri/lib/hooks/use-usage-status.tsx`、`components/chat/standalone/`、`app/(main)/settings/page.tsx`：用量、升级和账户界面的收起。
- `apps/screenpipe-app-tauri/src-tauri/src/main.rs`、`src-tauri/src/analytics.rs`、`src-tauri/src/recording.rs`：原生端遥测与录制边界。
- `apps/screenpipe-app-tauri/src-tauri/Cargo.toml`、`src-tauri/tauri.enterprise.conf.json`、`scripts/dev-enterprise.ts`：消费者与企业构建隔离。
- `apps/screenpipe-app-tauri/components/rewind/timeline/daily-summary.tsx`：本地模式下的 Daily Summary 回归。
