> 此文档是开发者的思考，Agent 不允许修改，但 Agent 可以重点参考这里面的想法





### 当前遇到的一些问题

1. 随着 Agent 的角色增多，每个 Agent 都有自己的业务逻辑、可调用工具范围，如何动态可靠地注入规则类信息到 Agent Loop



### 待办事项

1. 构建事件处理机制，将所有外部输入事件进行结构化建模
2. 构建新 Agent
   1. Intent Agent: 根据用户的活动记录, 向用户推送用户待处理事项解决方案
   2. Todo agent, 捕获与记录用户的 todo 项并列出
   3. Connection Agent: 梳理与记录用户与各 App /Agent 的关系, 来往记录
   4. Session Agent: 捕获 Claude code/Codex/Pi 中用户与 Agent 协作记录, 整理用户数据
   5. Summary Agent: 为用户产生日报/周报









### 观察到的点

1. 有 bug, 上一轮加 title 的的本意是加一个卡片的 title, 能在前端从上到下展示 title, proactive_view, plans 让用户快速理解到意图卡片的重点, 但误把 title 加到 plans 中, 参考:

   ```
   {
     "card_type": "read_only",
     "plans": [
       {
         "summary": "从系统信息确认当前接入的输入设备型号，梳理修饰键与组合键的现行映射（含豆包输入法里刚翻过的 fn/command/option/control 那组设置），先分清异常属于硬件还是映射层。",
         "title": "认清设备与现有按键映射"
       },
       {
         "summary": "把翰林阅里这份说明书的 USB 连接与蓝牙配对排障章节提炼成步骤清单，并对照刚才几个在线测试页暴露的现象逐条标注：已排除 / 待验证 / 与现象无关。",
         "title": "对齐说明书里的排障步骤"
       },
       {
         "summary": "按「测试现象 × 说明书步骤 × 系统与输入法侧可调项」三列汇总，标出下一步最该动的环节——哪些其实改系统快捷键或输入法设置就能解决，不用怪硬件。",
         "title": "汇成一张排查清单"
       }
     ],
     "proactive_view": "这一个小时你的动作几乎全押在一件硬件上：Chrome 连开四个在线键盘测试（zfrontier 的 keyboardTester 停得最久，中途还弹出「www.zfrontier.com 想连接到 HID 设备」的授权框——你在用它的键盘配置器直读设备），「mac 键盘测试」的搜索一直持续到 22:03，顺手还在补配列科普（100%/TKL/60%）；豆包输入法那边在翻 fn、command、option、control 单键或组合键的设置；翰林阅里读了十几分钟的说明书恰好是排障页——「更换电脑 USB 接口，PC 请换后置接口插紧」「遥控器会自动进入配对模式（指示灯呼吸闪烁）」。看着像是刚接上一个新键盘或带蓝牙遥控的外设，正在确认按键到底灵不灵、修饰键怎么映射才对。与其在四个网页和说明书之间来回点着对照，要不要我只读盘一遍：先从系统信息认出当前接的是哪个输入设备、修饰键现在被映射成了什么，再把翰林阅说明书里 USB 连接和蓝牙配对的排障步骤提炼出来，跟你刚才几个测试页里暴露的现象逐条对成一张排查清单——顺带标出哪些问题其实改系统快捷键或输入法设置就能解决、根本不用怪硬件？全程只读不动任何设置。",
     "recommended_index": 0,
     "v": 1
   }
   ```

   改完之后要在前端工作台中将意图卡片的 title 也显示出来, 另外报一个前端已存在很久的 bug: 选中某个 plan, 这个 plan 最左的白点没有变实心, 选中自选方案应该默认开始编辑, 最左的白点也要变实心, 这个 bug 可以一并修复

2. x-preview-f-free 端点不可靠, 这个先不认为是模型问题, 需要先调研: 是否是当前系统问题, 如缺乏心跳重试机制, 出一个报告给我
3. 我看到 agent 经常用 search_activity, 但都没有匹配结果, 或者返回垃圾 OCR result 乱码，最重一轮 ≈40 行, 这个要找一下原因到底是什么这个你需要出一个报告给我







1. System prompt 需要优化
   1. 角色改名: 意图卡片生成器 -> Intent card Agent
   2. 上一个 优化迭代版本集成 cue tool skill，让 Agent 知道它有哪些工具可以用。但是我们始终没有解释生成意图卡片的完整流程是怎样的, 当前 System Prompt 里面只告诉 Agent 它可以 submit 意图卡片以及拒绝。并没有告诉他怎么样去储存草稿, 我觉得需要把整一个流程理一理，写在 cue tool skill 的**## 2. 角色边界** 中 (其实还有另外的考量，就是外部的 Agent 激活这个 skill 后也能使用我们公开的接口，能够去生成卡片, 不一定在我们系统中)
   3. 可以参考 @repos-external/screenpipe/apps/screenpipe-app-tauri/src-tauri/src/pi.rs 判定is_local_model 然后注入 api_hint, 提醒 Intent card Agent 需要从 skill 中找到自己角色完整工作流程 (可以同时读 cue-tools + screenpipe-api ? 你可以评估一下)
   4. 当前指引做的不好, 没有一个次 loop Agent 去尝试存草稿





@repos-external/screenpipe/



意图卡片的生成是一个新的 feature，所以当前生成的卡片还不是很满意，无论是生成的质量以及代码的逻辑都是有些 bug，所以需要修复。针对此，我觉得需要通知生成意图卡片的 Agent 怎么样去生成标准让用户满意的意图卡片。以下是我理的一些思绪，只是初版，你需要帮我一步步的把它落实到一个非常可靠的版本



我自己理了下生成意图卡片的流程, 你可以参考

如何让 agent 精准生成意图卡片全流程

1. 描述意图卡片的定义: 用户下一步最后可能手动执行的任务, 比如在 IM 上接收到的工作安排, 当前工作推进到 Step1, 提早准备可能的 Step2/Step3 给用户, Cue 会在电脑上持续收集用户的信息, 提供多种(这里补一下有哪些)辅助你 (Intent card Agent) 判定出用户的下一步意图
2. 使用 Intent  tools 以及 screenpipe  tools 获取足够的上下文，据此判定用户下一步有可能会采取的一些动作，提早准备预案给用户
3. Cue Intent card 会按照15min 的频率触发一次Intent card 生成窗口, 当前窗口期会有很大的可能不足以生成让用户满意的 Intent card, 这时可以通过 `save_intent_draft`先暂存意图卡片的进度
4. 补充 `save_intent_draft`的逻辑, 比如有硬顶, 超过一段时间的草稿会废弃等
5. 可以同时准备生成多张意图卡片, 因为用户不止专注于一件事情
6. 生成的意图卡片中有三项(title, proactive_view, plans)会在前端展示给用户去看, 所以需要用一个恰当的文案风格展示, 具体风格没没想好要讨论

额外的思考:

```
System prompt 需要优化

1. 角色改名: 意图卡片生成器 -> Intent card Agent
2. 上一个 优化迭代版本集成 cue tool skill，让 Agent 知道它有哪些工具可以用。但是我们始终没有解释生成意图卡片的完整流程是怎样的, 当前 System Prompt 里面只告诉 Agent 它可以 submit 意图卡片以及拒绝。并没有告诉他怎么样去储存草稿, 我觉得需要把整一个流程理一理，写在 cue tool skill 的**## 2. 角色边界** 中 (其实还有另外的考量，就是外部的 Agent 激活这个 skill 后也能使用我们公开的接口，能够去生成卡片, 不一定在我们系统中)
3. 可以参考 @repos-external/screenpipe/apps/screenpipe-app-tauri/src-tauri/src/pi.rs 判定is_local_model 然后注入 api_hint, 提醒 Intent card Agent 需要从 skill 中找到自己角色完整工作流程 (可以同时读 cue-tools + screenpipe-api ? 你可以评估一下)
4. 当前指引做的不好, Agent 没有一次 loop 去尝试存草稿
```







Intent card

1. 将当前系统中所有的 Tools 用法写入 Skill: `cue-tools`
2. 将 `cue-tools` 塞进 Cue 中的 Agent, 提醒 Agent 根据当前场景阅读 skill, 但不同 Agent 的 tool 调用侧重点不一样(差异化 System Prompt)
   1. Intent card Generator: 主力使用 intent 系列工具
   2. chat agent: 主力使用 screenpipe 系列工具
3. 之后如果工具有迭代的话，我们只需要维护: Skill: `cue-tools`



新增一个 Intent 系列工具:

1. submit_intent_card_draft(名字还没想好)
   1. 这个工具是可以提供给 Intent Card Generator, 生成卡片不再是二元式的，要么直接提交生成，要么拒绝。而是告诉 Generator，如果当前的任务有持续性的倾向，可以先将当前的草稿存档, 在下一个心跳轮次，我们可以拉出来再跑一次

另外如果多了这个工具的话，我初步评估，我们提早给它准备好的一些预处理数据，以及我们之前提供的去获取最近的意图卡片的工具，也要相对调整