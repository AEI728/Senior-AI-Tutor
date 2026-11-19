# 小伴 System Prompt 与 Skill 实际接入说明

## 文件与格式

共享提示词：`apps/api/app/prompts/shared-system.md`。

五项应用 Skill 位于 `apps/api/app/skills/`：

| 包目录 | 实际职责 | 运行入口 |
|---|---|---|
| `intent-recognition/` | 识别页面、学习操作、推荐、停止和闲聊 | `agent.model_plan` |
| `course-recommendation/` | 从真实课程筛选、排序最多两项 | `skill_runtime.recommend_courses` |
| `operation-execution/` | 计划白名单和真实对象检查、受控执行 | `skill_runtime.validate_plan`、`main.agent_turn` |
| `response-generation/` | 固定结果模板与简短模型话术 | `skill_runtime.template/response_text`、`main.response_for` |
| `failure-recovery/` | 澄清、停止、确认纠正、手动降级、有限重试 | `skill_runtime.recover/correction_turn`、`providers.retry` |

每个包包含 `SKILL.md`，以 YAML `name`、`description`、版本元数据开头，正文规定触发、输入输出、权限及处理规则。对应 `references/policy.json` 是代码读取的运行策略。识别包另有从 Pydantic 导出的 `references/plan.schema.json`。

原来的普通 Markdown 规格本身不是错误文件，但缺少标准包入口，不能仅凭放进 skills 目录自动运行。此次还修正了规格和 Schema 不一致、示例课程 ID 不存在、未接入字段被写成现有能力，以及所有角色都要求 JSON 等问题。

原始上传路径保留：五份中文文件现在链接到同目录下的标准包；共享提示词更新为相同运行版本。项目自带完整副本，部署到另一台电脑不需要 `9.1` 目录。它们是应用自己的 Skill，不会注册为 Codex 的全局技能。

## 实际调用

```text
用户语音 → 原有录音/ASR → agent/turns
    → 共享提示词 + 意图 Skill + 本轮目录/页面/待澄清信息 + Plan Schema
    → 服务端校验计划
       ├─ 课程推荐：真实目录规则筛选，等待用户选课
       ├─ 页面/学习操作：幂等写入或创建页面 Action
       └─ 理解失败/纠正：恢复规则，必要时明确确认
    → 固定结果话术；导航必须等待前端回执
    → 原有 TTS 播报
```

闲聊、课程问答、语音陪练、视频陪练实际模型请求均合并共享提示词与话术 Skill，再附当前角色约束。语音助手和陪练仍独立；视频请求只有抽样帧。进入陪练只导航，不自动开摄像头或开始陪练收音。前端不新增聊天文字、弹窗或说明文案。

三个规则 Skill 由代码执行，不额外调用三个模型。更改 Markdown 不能绕过权限；更改模板、排序权重、恢复阈值通过受版本控制的策略文件生效，修改后应运行验证并重启服务。

## 当前契约和边界

- Plan 严格包含 `intent`、`skill_id`、`course_id`，不适用 ID 为 null。模型只能选择提供的真实目录，执行前再次校验。
- API 继续使用 `reply.display_text/speech_text`、`state`、`ui_actions` 等既有字段，避免让前端读取另一套未实现协议。
- 支持一个主要意图及“加入技能后打开课程”组合。任意多目标依赖图、通用状态版本锁和通用撤销令牌尚未加入；Skill 不得假称支持。
- 课程推荐使用真实学习记录和加入状态排序；时长/难度为用户硬条件时，字段缺失便返回缺失条件，不凭标题或模型推测。
- 首页“今日推荐”仍是社区分享，不调用课程推荐替换。
- “不是这个，换成摄影”先确认，并绑定原操作；过期或重新加入的技能不能凭旧确认删除。明确撤销仍保留进度。
- 连续两次理解失败停止语音追问，提示现有技能广场入口。没有转写文本的收音失败仍由前端音频诊断处理。
- 提供商临时错误最多重试一次，鉴权错误不重试。支付未开放，公开发布/删除数据/设备权限保留既有确认。

## 查看是否真的接入

`GET /api/v1/agent/skills` 需要当前会话身份，返回共享提示词指纹及五个 Skill 的版本和内容指纹。每个助手返回结果包含本轮实际经过的 `skill_trace`；模型操作记录也保存已用版本的脱敏摘要。它们不包含密钥或额外录音。

示例：“推荐一门摄影课程”会经过识别、执行校验、推荐和话术；“打开技能广场”只经过识别、执行和话术；理解失败时再加入恢复。

检查及维护（在项目根目录，使用后端虚拟环境）：

```powershell
.\apps\api\.venv\Scripts\python.exe scripts/check_agent_skills.py
# 修改 Plan 后重新导出 Schema；同时更新原始设计目录中的包
.\apps\api\.venv\Scripts\python.exe scripts/check_agent_skills.py --write --sync-design
.\apps\api\.venv\Scripts\python.exe scripts/tasks.py contract
# 显式真实API验收，会调用当前提供商；隔离账号，不操作本人的学习库
.\apps\api\.venv\Scripts\python.exe scripts/agent_skills_smoke.py --live
```

`--sync-design` 仅在本机原始 `9.1/docs/02-方案设计` 存在时使用。正常运行、CI、源码打包不依赖该目录。上线所需资产都在 `apps/api/app/`，已有 Dockerfile 会一起复制。

修改前源码及原始六份文档备份：`backups/agent-before-20261119T111908Z.zip`。
