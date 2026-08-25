# T8 · ATA 轨迹验证新指引效果

Labels: wayfinder:task (AFK)
Blocked by: [09-统一实现落地](09-统一实现落地.md)
Claimed by:

## Question

流程文本与多卡契约落地后，用 ATA 攒拍对比验证（调 `cue-agent-tuning` skill）：

1. 观察若干拍新指引下的真实运行轨迹，按失败分类计数（不出卡、出泛卡、草稿滥用、判重误伤等）；
2. 与改动前的历史拍对照：出卡率、卡片具体度、草稿收敛行为是否朝 T1 标准方向移动；
3. 结论回写本票；若某类失败反复出现，先判断该修提示词还是引擎层，再决定是否毕业新票。

## Resolution

Status: Open
