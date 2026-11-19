---
name: operation-execution
description: 对已解析计划校验白名单、真实对象与权限，提交学习操作并等待页面回执；不负责开放语言猜测。
metadata:
  version: "1.1.0"
---

# Skill 03 · 操作执行

## 执行主体
这是服务端代码 Skill，不让模型直接执行网络、数据库、设备或文件系统操作。
入口先用 Plan Schema、[白名单策略](references/policy.json)和真实目录校验，再由 main.agent_turn 的分支执行。客户端不能指定任意工具名。
每次请求使用当前用户和 client_request_id；同 ID 同内容回放，同 ID 不同内容拒绝。数据库变更与结果写入同事务。

## 结果契约
继续使用应用接口字段：state、intent、reply、ui_actions、completed_steps、needs_clarification、choices、fallback_actions。
状态为 SUCCEEDED、WAITING_USER、WAITING_UI_ACK、PARTIAL、FAILED、UNKNOWN；不能把设计稿的 success/partial_success 等直接当成 API 字段。
技能加入返回真实 added/already_joined；导航生成有期限的 Action，只有当前用户的 applied 回执后才能宣布打开。失败保留已成功的步骤。

## 校验与撤销
- ID 必须在可用目录中，course_id 必须属于对应技能；课程访问用服务端现有审核/权限检查。
- 先加入后开课按顺序执行；加入失败不创建后续导航。页面失败只报已完成的真实技能名，不固定说“园艺”。
- 撤销通过当前用户最近 library.add Operation 绑定，相当于服务端撤销凭证；不声称接口存在 undo_token 或 state_version 字段。
- 已存在的加入、已撤销或已失效的加入不能再次移除；保留学习进度。明确“撤销刚才加入”可执行；“不是这个，换成摄影”先确认替换方案。
- STOP 清除未执行的旧页面动作和待澄清计划；没有持久化写入要撤销时不伪称已撤销。
- START_PRACTICE 只发页面导航，设备仍等用户在陪练页点击开始。
- 分享发布、清除学习数据和设备授权保持原有确认界面；支付不在工具白名单。

## 边界
当前不提供任意 DAG 任务、通用状态版本锁或所有动作的撤销令牌；需要这些能力时先扩展代码和契约。不能仅靠提示词宣称支持。
