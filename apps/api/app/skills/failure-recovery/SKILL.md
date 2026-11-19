---
name: failure-recovery
description: 在理解失败、用户停止或纠正、工具失败时选择澄清、有限重试、撤销或手动入口；不扩张权限。
metadata:
  version: "1.1.0"
---

# Skill 05 · 失败恢复

## 优先级
停止/取消 > 权限和风险阻断 > 明确纠正 > 有效撤销或一次安全重试 > 最小澄清 > 手动入口。
本 Skill 由服务端规则实现，恢复判断不再调用一个额外模型。

## 运行策略
[策略](references/policy.json)规定连续两次理解失败转 manual_fallback，最多两个真实候选。
第一次 UNKNOWN 返回 WAITING_USER、一个问题和真实候选；第二次停止语音追问，保留现有技能广场手动入口，不要求新增弹窗。
明确的新请求重置上一项失败上下文；模型不能沿用旧澄清来制造额外写入。
提供商连接、限流和暂时不可用最多安全重试一次，由 providers.retry 执行；权限、鉴权、参数或未知业务 ID 不重试。
幂等键复用与数据库事务由应用执行层负责；不重跑已经成功的写操作。
“不是这个，换成摄影”只准备替换方案并确认；确认时重新校验当前用户最近可撤销 Operation。无有效凭证不自动删技能。
纯“停/取消”清除待澄清和待执行页面动作；已成功的数据操作必须明确撤销，不假装自动回滚。
部分成功保留成功步骤，给出真实技能名；页面回执失败或超时不能声称已经打开。
收音失败发生在前端音频链路，没有可执行文本时不执行业务工具；麦克风诊断仍走现有 debug/audio，不虚构 ASR 置信度。

## 输出
recovery 包含 strategy、attempts、stop_voice_followups、choices、speech_text。API 的 reply 承载语音；当前 UI 继续只播报，不展示对话文本。
支持 clarify、manual_fallback、stop、confirm_correction；临时网络重试由提供商层完成，不让模型无限规划。
