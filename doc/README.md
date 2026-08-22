# Feature 合同索引

本目录存放 Cue 本地个人版（源码名 Screenpipe）这一版的 Feature 合同。`docs/` 里是历史规格，多数已落后数百个提交；改这版的行为之前，以下面的合同为准。

## 现行合同

| 文档 | 管什么 | 动手前必读的场景 |
|---|---|---|
| FEATURE_CUE_BRANDING.md | 用户可见文案用 Cue，机器标识保留 screenpipe | 写或改任何用户可见字符串 |
| FEATURE_I18N_UI_LANGUAGE.md | UI 多语言层结构，新增文案的规则 | 新增或编辑界面文案 |
| FEATURE_LOCAL_FIRST_MODE.md | 本地优先构建的默认运行边界 | 录制资格、账户 gate、遥测、Provider 配置 |
| FEATURE_AGENT_CAPABILITY_SURFACE.md | Pi、Skill、Tool 与本地 API 的能力供给关系 | 改 Agent 能力入口、extension 或媒体代理 |
| FEATURE_MODEL_INVOCATION_INVENTORY.md | 全部模型调用路径盘点，重构基线 | 触及任何会发起模型推理的代码 |

## 合同格式

每份合同头部有两个 marker：`doc-covers` 列出它声明的覆盖文件，`doc-verified` 钉住核验时的提交。标题下另有一行横幅声明核验状态。引用合同结论时以 marker 为准，不单看正文措辞。

覆盖文件在锚点之后发生变化时：重读 diff，核对正文断言；没有实质行为变化就直接把 `doc-verified` 换成当前 HEAD，有变化则先修正文再换。

新写合同时有两种已验证的形态可参照。横切行为类看 `FEATURE_LOCAL_FIRST_MODE.md`：模式判定、「必须同时成立的行为」清单、后续改动检查表。模块契约类看 `FEATURE_MODEL_INVOCATION_INVENTORY.md`：路径 ID、每条路径必记字段、横向对照表、验收标准。

## 维护现状

`bun scripts/check-doc-freshness.ts` 目前只扫 `docs/`，不覆盖本目录。合同的保鲜依赖改到覆盖文件的人自觉重锚。
