# Agent Skill

共享提示词位于 `apps/api/app/prompts/shared-system.md`，任务 Skill 位于 `apps/api/app/skills/`。

| Skill | 职责 | 运行入口 |
|---|---|---|
| `intent-recognition` | 将用户输入转换为结构化操作计划 | `agent.model_plan` |
| `course-recommendation` | 真实课程筛选与排序 | `skill_runtime.recommend_courses` |
| `operation-execution` | 工具白名单、参数与对象校验 | `skill_runtime.validate_plan`、`main.agent_turn` |
| `response-generation` | 操作反馈模板与简短口语回复 | `skill_runtime.template/response_text`、`main.response_for` |
| `failure-recovery` | 澄清、确认纠正、撤销与手动入口 | `skill_runtime.recover/correction_turn`、`providers.retry` |

每个包包含带 `name`、`description` 和版本元数据的 `SKILL.md`，以及代码读取的 `references/policy.json`。意图识别包另有由 Pydantic 导出的 `references/plan.schema.json`。

## 请求流程

```text
语音识别文本 + 页面上下文 + 可用目录
  → 共享提示词 + 意图识别 Skill + Plan Schema
  → 参数、身份与工具校验
  → 只读推荐 / 学习操作 / 页面 Action / 失败恢复
  → 数据库结果与页面回执
  → 回复模板与 TTS
```

助手、语音陪练与视频陪练使用独立上下文。闲聊和陪练模型请求合并共享提示词、话术 Skill 与角色规则。规则模块由代码执行，模型不能取得额外的写入或设备权限。

## 契约

- Plan 包含 `intent`、`skill_id`、`course_id`，不适用的 ID 为 null。
- ID 必须来自真实目录，导航结果由前端回执确认。
- 支持单项操作及“加入后开课”组合。
- 课程推荐最多返回两项，理由取自实际课程字段和学习状态。
- 撤销绑定当前用户有效的最近加入操作，保留学习进度；替换技能需确认。
- 连续两次理解失败后提示手动入口，临时提供商错误最多安全重试一次。

`GET /api/v1/agent/skills` 返回提示词指纹及 Skill 版本；助手结果中的 `skill_trace` 记录本次请求经过的模块。接口需要当前会话身份。

## 校验

在项目根目录使用后端虚拟环境：

```powershell
.\apps\api\.venv\Scripts\python.exe scripts/check_agent_skills.py
# 修改 Plan 后重新导出 Schema
.\apps\api\.venv\Scripts\python.exe scripts/check_agent_skills.py --write
.\apps\api\.venv\Scripts\python.exe scripts/tasks.py contract
```

修改提示词或运行策略后重启后端。
