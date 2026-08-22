# Cue 品牌与文案边界

<!-- doc-covers: AGENTS.md, apps/screenpipe-app-tauri/lib/i18n/en.ts, apps/screenpipe-app-tauri/lib/i18n/zh-CN.ts, apps/screenpipe-app-tauri/src-tauri/src/dock_menu.rs, apps/screenpipe-app-tauri/src-tauri/src/tray.rs, apps/screenpipe-app-tauri/src-tauri/Info.plist -->
<!-- doc-verified: 553ab58cfea82f75e7dd82317173a8757705bbd7 -->
> **Current。** 本文按上述提交核验，记录 Cue 品牌化的文案边界。后续改动应以代码为准。

## 1. 目的

本仓库是 Screenpipe 的本地个人版，产品对外呈现的名字是 **Cue**。用户能看到的每一个字符串都不再出现 "screenpipe"；代码层面的标识保持原命名不动。

这条边界存在的意义：改名只发生在「人读的层」，不碰「机器读的层」。机器层一改，数据目录、深链、升级通道、企业策略全会断。

## 2. 必须改（用户可见）

| 位置 | 已落地 | 后续新增 |
|---|---|---|
| React 组件内联文案 | 经 i18n 字典抽取，字典里写 Cue | 新文案直接写进字典，见 `FEATURE_I18N_UI_LANGUAGE.md` |
| tray / dock 菜单（Rust） | "Show Cue"、"Open Cue"、"Quit Cue" 等 | 沿用所在文件的现有写法 |
| 系统通知标题与正文（Rust） | 会议、录制暂停恢复、音频设备回退等 | 同上 |
| macOS 权限弹窗描述 | Info.plist 五条已去品牌化 | 新增 usage description 用 Cue |
| 错误提示里带主语的句子 | "sign in to start Cue recording" 等 | 用户会把整句读出来，主语必须是 Cue |

判断标准：把这句话念给用户听，或显示在系统级 UI（通知、权限弹窗、菜单）里——出现 screenpipe 就是 bug。

## 3. 绝不改（机器标识）

以下内容保留 `screenpipe` 原名，替换它们会破坏数据兼容或运行链路：

- bundle identifier（`com.screenpipe.app` 等）与数据目录（`~/.screenpipe`）；
- 深链 scheme `screenpipe://`；
- 环境变量（`SCREENPIPE_*`）与设置键（如 `showScreenpipeShortcut`）；
- Rust crate 名、npm 包名、import 路径、日志与 tracing 文案、线程名；
- analytics 的 release 标识、遥测字段、上游 API 路径；
- 源文件头部的 provenance 注释（AGENTS.md 规定的头注释，属出处追踪而非 UI）。

灰色地带的处理原则：先问「这个字符串有没有被代码、脚本或外部系统当作标识匹配」。有匹配关系的，一律留在机器层。

## 4. 后续改动检查

- 新增 UI 字符串：进字典时 en 与 zh-CN 都用 Cue，不要在组件里绕过字典硬编码。
- 新增 Rust 面向用户的字符串：检查是否含品牌词；同时检查是否有测试按字面量匹配它（如 `restart_failure_detail` 的匹配串），匹配串和测试要一起改。
- 新增配置键或协议字段：用原名风格（screenpipe），不要新造 cue 前缀造成两套命名并存。

## 5. 证据索引

- 品牌替换的 Rust 提交范围：tray/dock/process_exit/meeting_live_notes/meeting_stall_notifications/engine_events/audio_device/recording/overlay_health/meeting_export/gate + Info.plist。
- 前端文案以字典为准：`lib/i18n/en.ts` 与各分片 `en-*.ts` 中不含 "screenpipe"（路径、URL 类值除外）。
