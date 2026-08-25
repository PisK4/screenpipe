# 参考索引

## 契约与决策文档（screenpipe 仓库内）

- `doc/FEATURE_TOOLS_REFERENCE.md` — 工具契约总表、技能装载机制（§6）、集成步骤（§9）、变更检查表（§10）
- `doc/FEATURE_INTENT_CARDS.md` — 管线全景、状态机、软去重重设计（作废 D2 的三宗罪论证）、L0/L1/L2 评估口径（§11）、明确不做清单（§12）、改动联动表（§13）
- `doc/FEATURE_AGENT_CAPABILITY_SURFACE.md` — Skill / Tool / API 四层关系与隔离论述

## 配套技能

- `ata` — 轨迹服务操作：会话发现、四步下钻、usage/tools/events 语义、已知陷阱
- `screenpipe-local-queries` — 本地 REST 查询语法与时区陷阱
- `ponytail` — 修复方案的最小化审查

## 关键 trace 索引（意图卡生成器调优期）

| trace | 教训 |
| --- | --- |
| 01a02fee | execute 签名错弹掉全部合法载荷：协议层校验先行拦截的代价 |
| 01a033b6 | 近期卡全文诱发逐卡枚举，输出预算截断死 |
| 01a03407 | 同上复现 + frame_count 泄入用户面文案 |
| 01a0343a / 01a03457 | 流挂起 pending 死 / STOP:error 两类死法的标本，且 ATA 与 jsonl 记录矛盾——定类必须两源对照 |
| 01a03314 | ~/.agents/skills 无条件涌入会话的证据，--no-skills 白名单装载的起点 |

## 数据位置

- ATA 服务：`$ATA_URL`（生产 17877），账本 `~/.ata/ata.sqlite`
- pi 原始会话：`~/.cue/pi-config/sessions/<agent-dir>/*.jsonl`
- 受管技能根：`~/.cue/agent/skills/`（所有权说明见根下 README）
