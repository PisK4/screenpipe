---
name: cue-agent-tuning
description: >
  调优 Cue 的无人值守 agent（意图卡生成、chat、daily-summary 及后续新增的任何
  agent）时使用：攒拍观察 ATA 轨迹、给失败分类计数、裁决修复应该落在哪一层。
  也用于回答「某几拍为什么没出结果」「这次改动有没有效果」「这个 agent 反复
  死在同一个地方怎么办」这类问题。轨迹查询语法见 ata 与
  screenpipe-local-queries 技能，本文不重复。
---

# Cue Agent 轨迹驱动调优循环

这份 skill 沉淀自意图卡片生成器的多轮调优（2026-08-22 至 08-25）。那期间出现过五类失败，每类的死状不同、对症层不同，混在一起看会修错地方。核心循环只有一段：

```
部署 → 攒 ≥3 拍 → ATA 取证 → 失败分类计数 → 找正确层修 → 再攒 ≥3 拍对照基线
```

## 1. 失败分类学

动手前先把坏轮次逐个定类，数出频次。每一类都有可辨认的死状：

| 类 | 死状特征 | 对症层 | 实例 |
| --- | --- | --- | --- |
| 输出预算截断 | 消息停在单词中间；usage 的 output 接近模型 maxTokens 声明值 | 材料瘦身（砍诱发冗长的字段）+ 抬预算；换槽只是治标 | trace 01a033b6 / 01a03407：逐张枚举近期卡写到一半被掐 |
| 流挂起 | 最后一条助手消息 status 停在 pending，只吐几个 token 就再无下文；发生在拍中段而非超时点 | 端点病，代码治不了——换稳定模型槽 | x-preview-f-free 六轮挂三轮 |
| 散文收尾 | turn 正常结束（status completed）但没调任何提交工具，结论躺在正文里 | system prompt 硬规则 + 提交工具 description 强调 MUST call；复发再考虑 parse 层兜底 | ATA 见过一例 6181 字分析后直接结束；注意 jsonl 里该轮记的是 STOP:error，两源矛盾时以磁盘为准 |
| 技能低采纳 | 该读的 skill 长期没人读，行为偏离学说 | 改 skill 的 frontmatter description：把「不确定时读」这类自门槛改成任务触发式；仍不行再上 prompt 硬指向 | cue-tools 阅读率 1/5 → 6/6 |
| 垃圾工具结果 | 工具返回大量占位行（如 `[OCR] ? | ? |`），模型反复换参数重查直到耗尽回合 | wrapper 过滤折叠，不是劝模型别重试 | search_activity 连返占位行诱发无效循环 |
| 协议层拒收 | 合法载荷全被打回，错误信息指向签名或 schema | 修 execute 签名/schema 分层，与模型无关 | trace 01a02fee：execute(args) 签名错弹掉五个合法载荷 |

定类时用 `scripts/session_tail_audit.py` 一条命令扫完某 agent 全部会话的收尾状态，再对可疑个体下钻。

## 2. 分层裁决规则

修错层是最大的浪费。四条裁决按顺序问：

1. **能焊进 wrapper 的不写进 prompt。** 时间窗必填、截断、上限、垃圾行过滤都是代码的事；prompt 只承担判断语义。护栏焊死后，模型的自觉从需求变成加分项。
2. **材料即诱导。** 材料的字段和语言会渗进产出：近期卡带全文，模型就逐张复述；材料写「帧数」，用户就读到「34 帧」。瘦身先砍诱发物，再考虑劝诫。判重语境只需要最小集 `{id, gist, status, created_at}`，详情让模型拿 id 自己查工具。
3. **机器面与用户面分语言。** 工具 schema、参数描述、材料标记、技能 frontmatter 是模型解析面，用英文；system prompt 主体与产出文案是中文锚点与交付面，保持中文。同一份 schema 里双语混排是最差形态。
4. **改契约两侧同步。** submit 载荷加字段要同时动 extension schema、parse.rs、DB 列、文档；漏一侧就是下一个 01a02fee。

## 3. 度量纪律

- 改动前后各攒至少 3 拍才许下结论，单轮好坏不算证据。
- 每次汇报三样：目标行为发生率（阅读率/出卡率）、失败分类计数对比、输入输出 token 区间。
- 基线记在本文件末尾的「调优台账」，新调优先查台账找同类基线。
- L0 指标口径（采纳率、不足率、生成健康度）以 FEATURE_INTENT_CARDS.md §11 为准，不自造口径。

## 4. 取证操作

ATA 四步：`read sessions` → `read usage` → `read tools --status failed` → `read events` 翻到底。ATA 解释不了或数据缺失时直读原始文件：

```
~/.cue/pi-config/sessions/<agent-dir>/*.jsonl
```

jsonl 尾部三行能定生死：最后一条 assistant 是否 pending、stopReason 是什么、toolResult 里有没有成片的占位行。批量定类用本技能目录下的 `scripts/session_tail_audit.py`。

注意两个已知陷阱：pending 消息在 jsonl 里可能来不及落盘（ATA 有、磁盘无），两边对照才算数；usage 的 input 是多轮累计值，跨会话比大小要看轮数。

## 5. 修复落地后的固定动作

extension 或契约改动要重装才生效（资产 include_str! 编译进二进制）；skill 文件与 models.json 是运行时读取，改完下一拍生效。重装走 screenpipe 仓库 `apps/screenpipe-app-tauri/` 的 `make install`，装完必须完全退出旧进程再启动。

## 调优台账

| 日期 | 改动 | 基线 → 结果 |
| --- | --- | --- |
| 08-24 | cue-tools description 自门槛改任务触发 + 英文 | 阅读率 1/5 → 6/6 |
| 08-24 | title 契约 + [RECENT_CARDS] 瘦身 {id,gist,status,created_at} + 128K 预算 | 截断 2/8 → 0/6；输入 ~17.9K 字符 → ~10.5K |
