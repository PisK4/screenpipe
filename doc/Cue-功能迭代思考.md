> 此文档是开发者的思考，Agent 不允许修改，但 Agent 可以重点参考这里面的想法



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