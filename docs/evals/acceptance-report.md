# R1 实施验收记录

- 日期：2026-11-11（Asia/Singapore）。具体命令采用 UTC 时间，见 commands.jsonl。
- 源码：新建独立工作目录 xiaoban-r1；未创建提交，Git SHA 不适用。
- 环境：Windows PowerShell，Python 3.12.14，Node 24.20.0，pnpm 11.25.0。
- 依赖版本：apps/api/uv.lock、apps/web/pnpm-lock.yaml；后端 OpenAI SDK 2.54.0。
- 验证模式：Mock 规则助手 + SQLite；未验证真实模型、语音或 PostgreSQL。
- Prompt：base-v1 / companion-v1 / tutor-v1。默认真实模型名保留规范配置，未验证账户可用性。
- 最后复核：源码格式化及窄屏发送按钮修复后，lint、typecheck、build、contract均再次退出0；预览Web返回HTTP 200，ready明确返回mock + sqlite，最终本地smoke退出0。

## 实际执行

Windows实际以 `make PYTHON=apps/api/.venv/Scripts/python.exe <目标>` 或同义 `python scripts/tasks.py <目标>` 执行。`commands.jsonl`记录子命令、工作目录、UTC开始时间及退出码。早期直接shell验证和失败记录由本报告补充。

| 命令 / 场景 | 状态 | 退出码 / 实际观测 | 证据 |
|---|---|---|---|
| init | PASS | uv与pnpm冻结安装均0；本次临时把已安装uv加入进程PATH | commands.jsonl |
| doctor | BLOCKED | make退出2；缺Docker、jq、ffprobe，uv尚不在默认PATH | 本次实际终端输出 |
| db-up | BLOCKED | make退出2；docker可执行文件不存在 | commands.jsonl |
| lint | PASS | Python Ruff及前端ESLint均0 | commands.jsonl |
| typecheck | PASS | Mypy及TypeScript均0 | commands.jsonl |
| test-unit | PASS | 16 passed，退出0 | commands.jsonl |
| test-sqlite | PASS | 11 passed，退出0；不等于PostgreSQL集成验收 | commands.jsonl |
| test-web | PASS | 2 passed，退出0 | commands.jsonl |
| build | PASS | 后端导入及Vite构建0 | commands.jsonl |
| contract | PASS | OpenAPI快照及生成前端类型一致，退出0 | commands.jsonl |
| eval-mock | PASS | 独立意图holdout 10/10，退出0；不能推断真实模型准确率 | intent-mock.json |
| smoke | PASS | Mock/SQLite目录、浏览不加入、加入、重复请求及创建练习成功，退出0 | commands.jsonl |
| test-integration | BLOCKED | make退出2；未提供专用PostgreSQL TEST_DATABASE_URL | 本次实际终端输出 |
| e2e | PASS（Mock/SQLite） | 2 passed，最终退出0，耗时4.1分钟；前期启动和page超时失败保留在命令历史，改为单进程测试启动器、完整Chromium通道并增大启动超时后通过 | apps/web/test-results/.last-run.json、commands.jsonl、页面PNG |
| live-smoke | BLOCKED | make退出1；缺真实提供商配置与API Key，未发出收费调用 | commands.jsonl |
| eval-live | NOT_RUN | 缺真实API凭证 | — |
| make test / ci 完整门禁 | BLOCKED | PostgreSQL门禁未通过；不能声明完整R1验收 | — |
| Compose部署、备份恢复 | NOT_RUN | 无Docker、云资源、域名与生产认证 | — |
| 目标老年用户试验 | NOT_RUN | 未招募，不编造结果 | usability-report.md |

## 已覆盖行为

浏览不加入、目录外认字不替换、明确焦点加入、幂等与重放、请求ID冲突、加入后等待ACK、失败ACK保留加入、过期ACK为UNKNOWN、撤销保留进度、角色权限、用户隔离、自述完成不核验质量、暂停/复讲/继续、知识不足不编固定用量、无视觉判断、急症停止并求助、不猜急救号码、隐私删除和敏感事件拒绝均有后端自动化证据。

BC01–BC24完整原始条目保存到 `evals/cases/bad_cases.jsonl`。浏览器已验证小伴在陪练页不存在、Mock语音不可用时文字入口仍启用，以及核心旅程。BC16的真实麦克风拒绝、BC23的两次真实ASR失败、真实模型注入鲁棒性、真实ASR准确性和麦克风硬件均未验证。没有把24条全部标为已通过。

## 未解决实现差异

- 课程步骤与FAQ按版本化JSON保存，未拆成规范的独立两张表，见ADR-009。
- 当前模型使用单次严格计划函数、服务端确定执行；未实现通用多轮Function输出循环、复杂重规划及指数退避。SDK重试关闭。
- 澄清当前为前端退路，尚未实现持久待填槽位上下文；多设备配额原子预留、金额预算需完善。
- 无合成演示MP4，采用真实文字课件并明确视频未开放。
- 目前OIDC仅服务端验签；供应商端到端浏览器登录未完成。
- 初期E2E失败发生在启动和页面fixture阶段。修复启动器与通道后2项通过，已人工查看home-mobile.png和practice-mobile.png；窄屏发送按钮的换行已用flex-shrink与nowrap修复。200%自动化检查仅改变根字号，不替代真实浏览器缩放与目标设备手测。

## 发布阻断

真实模型LLM/ASR/TTS验收；PostgreSQL并发及事务验收；完整设备和适老真实用户验证；OIDC登录；TLS和镜像digest锁定；隐私与内容签核；备份恢复演练。见 `docs/security/release-gates.md`。

当前交付应称为**可本地运行的内部测试实现**。外部依赖准备及以上实现缺口完成后，才能再次申请完整R1验收。
