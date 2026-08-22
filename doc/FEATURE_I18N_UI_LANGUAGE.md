# 界面多语言（i18n）

<!-- doc-covers: apps/screenpipe-app-tauri/lib/i18n, apps/screenpipe-app-tauri/lib/i18n/en.ts, apps/screenpipe-app-tauri/lib/i18n/zh-CN.ts, apps/screenpipe-app-tauri/lib/i18n/translate.ts, apps/screenpipe-app-tauri/lib/i18n/index.ts, apps/screenpipe-app-tauri/lib/utils/locale.ts, apps/screenpipe-app-tauri/lib/hooks/use-settings.tsx, apps/screenpipe-app-tauri/components/settings/display-section.tsx -->
<!-- doc-verified: 553ab58cfea82f75e7dd82317173a8757705bbd7 -->
> **Current。** 本文按上述提交核验，记录 UI 多语言层的结构与约定。后续改动应以代码和测试为准。

## 1. 目的

桌面端界面支持简体中文与英文两种显示语言，语言可在 Settings → Display 切换，默认跟随系统语言。i18n 层是自建的轻量实现：不引入第三方 i18n 依赖，不做路由级 locale，只解决「字典查找 + 插值 + 回退」三件事。

## 2. 结构

```text
lib/i18n/
  en.ts          英文字典，Dictionary 类型的 source of truth
  zh-CN.ts       中文字典，satisfies Dictionary 保证键结构一致
  translate.ts   纯函数翻译，无 React/Tauri 依赖
  index.ts       useT() hook 与 re-export
  en-*.ts        按区域拆分的英文字典分片
  zh-*.ts        对应中文分片
```

分片按组件区域组织（account、chat、meeting-notes、notifications、onboarding、settings-misc、storage），在 `en.ts` / `zh-CN.ts` 里合并为 `chat`、`onboarding`、`meetingNotes`、`settings.*` 命名空间。并行抽取时各 worker 只写自己的分片文件，避免对主字典的写冲突；合并由主会话一次性完成。

键路径用点分命名空间，如 `settings.display.language`、`chat.quota.viewBusiness`。`{name}` 占位符做参数插值；查不到时回退英文，再回退到原始键名。

## 3. 语言判定与应用链路

1. 设置项 `locale?: AppLocale` 存在设置存储中（`"en" | "zh-CN"`），未设置表示跟随系统。
2. `resolveAppLocale()` 先取显式设置，否则按 `navigator.languages` 匹配（`zh*` → zh-CN，`en*` → en）。
3. Provider 的 effect 在 `settings.locale` 变化时调用 `applyLocale()`：写 `document.documentElement.lang` 并镜像到 localStorage（键 `screenpipe-app-locale`）。
4. layout 的 head 启动脚本在 React 挂载前读取该 localStorage 并提前设置 `lang`，避免首帧语言闪烁——与主题的处理方式相同。

语言切换入口在 Settings → Display 的 Language 卡片，三个选项：跟随系统 / English / 简体中文。语言名固定用自己的文字书写，不进字典翻译。

## 4. 新增文案的规则

1. 组件内不写内联用户可见文案，统一 `const t = useT();` 后 `t("ns.key")`。
2. en 分片先加键，zh 分片补齐同构键；`satisfies Dictionary` 和 `i18n.test.ts` 的键完整性测试会在编译期和测试期双重拦截漏翻。
3. 中文文案要求：桌面应用惯用语、简短自然、不用「赋能/打造/助力/梳理」一类腔调词；品牌词一律 Cue（见 `FEATURE_CUE_BRANDING.md`）；插值占位符原样保留且参数名必须与调用处一致。
4. 语言名（English、简体中文）固定原文，不翻译。
5. 非用户可见的字符串不进字典：发给 LLM 的 prompt、系统提示词、API 错误码前缀（如 `account_required:`）、searchIndex 的 label/keywords（搜索匹配用）保持英文原样。

## 5. 测试约定

- 组件测试默认运行在英文环境，断言英文字典里的逐字原文；改英文字典措辞时同步检查断言。
- 渲染树里有 `useT()` 但测试没有包 Provider 时，给测试加 `vi.mock("@/lib/hooks/use-settings")` 提供 settings/updateSettings。
- `lib/i18n/i18n.test.ts` 负责字典同构性与翻译行为本身；新增分片不需要单独的测试文件，键完整性测试自动覆盖。

## 6. 当前覆盖范围与剩余工作

已完成抽取：settings 全部主要 section（display/general/recording/account/notifications/storage 及 misc 小节）、chat/standalone 全部组件、onboarding、meeting-notes。

尚未抽取（界面仍为英文硬编码）：connections-section、pipes-section、live-view 系列、ai-presets、rewind 区域（timeline/search-modal 等）、根组件若干（app-entitlement-gate、notification-feedback 等）。这些文件继续按第 4 节规则分批迁移即可，架构无需再动。

Rust 侧（tray/dock/通知）暂未接语言切换，当前只完成品牌替换；接入时从设置读 locale，在菜单构建与通知发送处选字典。

## 7. 证据索引

- 字典与翻译核心：`lib/i18n/en.ts`、`lib/i18n/zh-CN.ts`、`lib/i18n/translate.ts`、`lib/i18n/index.ts`。
- 语言判定与应用：`lib/utils/locale.ts`、`lib/hooks/use-settings.tsx`（locale 设置项与 effect）、`app/layout.tsx`（head 启动脚本）。
- 切换入口：`components/settings/display-section.tsx` Language 卡片。
- 同构性测试：`lib/i18n/i18n.test.ts`。
