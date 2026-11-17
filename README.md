# 小伴 · 银发 AI 私教

已支持真实DeepSeek文本操作、语音识别和语音合成。2026-11-16已验证真实语音→操作计划→数据库→浏览器导航ACK→语音回复。详情见 [本次验收](docs/evals/upgrade-acceptance-2026-11-16.md)。当前仍为内部测试工程。

旧前端原型已保留在 `legacy/prototype/`，历史PRD位于 `docs/prd/`。当前应用使用 `apps/api/` 和 `apps/web/`，请按下方方式启动。

## 本机启动

```powershell
cd '<你的项目目录>/Senior-AI-Tutor'
./scripts/start-local.ps1
```

打开 http://localhost:5173 。脚本读取根目录.env，不再强制Mock；PORT用于后端，前端代理自动跟随，当前为4312。默认SQLite保存于local-preview.db，真实模型体验无需Docker。不要重复启动两份服务。修改.env后重启。

现有.env可直接使用DEEPSEEK_API_KEY、DEEPSEEK_BASE_URL、DEEPSEEK_MODEL、USE_MOCK_LLM=false和PORT。LLM_PROVIDER/AUDIO_PROVIDER未设置时自动选择已配置服务；真实调用失败不会静默回退Mock。密钥仅保留在后端，不要提交Git。

## 体验方式

点击“进入本地测试”，或注册独立账号。独立账号可重新登录恢复服务端学习记录；演示入口仍为共用开发身份。

打开小伴，点击“开始语音对话”并授权麦克风。停顿约1.1秒后自动发送；单段最多19秒，8秒无声音停止。可说：

- “我想学养花”“我想学书法”“把园艺加入技能库，再打开第一节课”。
- “看看摄影有什么课”“打开技能广场”“返回首页”“打开我的设置”“看看作品社区”。
- “接着上次的学”“撤销刚才的加入”“开始陪练”。
- 课程页“暂停视频”“继续播放视频”。

低风险明确操作直接执行；导航等页面加载及ACK后才说成功。关闭“说完自动执行并播报”可核对转写后手动发送。界面显示听到的文字及目录同音词纠正。连续两次不理解会暂停语音。原始录音不保存，录音会发送至后端及当前语音提供商。

播报期间暂停采音，避免助手听到自身而循环操作；打断请点击“停止播报”。目前不是全双工实时语音通话，真人口音、设备和噪声环境仍需测试。

## 已实现功能

- 园艺、书法入门、手机摄影、节奏入门四类原创草稿课程，文字步骤与合成流程示意视频；不是专家审核或真人授课。
- 独立私教答疑、暂停/继续/复讲/自述完成/退出。非模板表达采用结构化模型决策；沉默不推进，自述不冒充动作核验。
- 单张照片参考反馈：需用户明确同意，不保存原图、不改变进度、不做质量认证；无实时摄像头自动推进。
- 独立本地账号、用户隔离、进度保存与个人业务数据删除。
- 图文作品投稿、明确分享确认、人工审核、举报转回复核、本人撤下。更换图片重新审核；图片去除EXIF。支付未做。
- 持久化澄清意图、限次Provider重试、请求幂等与重放、导航失败回执及过期UNKNOWN。
- 本地按课程隔离的关键词检索。KNOWLEDGE_BASE_PATH/<course_id>/*.md或txt，RAG_TOP_K控制条数；未配置或目录不存在时用data/knowledge内置资料。这不是向量搜索。

## 审核管理员

先注册独立账号，再通过具有本机访问权限的终端授予角色：

```powershell
cd apps/api
./.venv/Scripts/python.exe -m app.manage grant-admin 你的账号名
```

退出重登后，作品社区显示审核队列。没有管理员时作品保持待审核。正式OIDC管理员可使用ADMIN_SUBJECTS配置iss:sub。

## 验证命令

```powershell
./apps/api/.venv/Scripts/python.exe scripts/tasks.py lint
./apps/api/.venv/Scripts/python.exe scripts/tasks.py typecheck
./apps/api/.venv/Scripts/python.exe scripts/tasks.py test-unit
./apps/api/.venv/Scripts/python.exe scripts/tasks.py test-sqlite
./apps/api/.venv/Scripts/python.exe scripts/tasks.py test-web
./apps/api/.venv/Scripts/python.exe scripts/tasks.py build
./apps/api/.venv/Scripts/python.exe scripts/tasks.py contract
./apps/api/.venv/Scripts/python.exe scripts/tasks.py e2e
```

普通E2E使用独立Mock/SQLite服务8000/5174，不使用真实密钥。真实实例4312/5173可同时运行。测试重建专用test库，不能指向个人数据库。

live-smoke和eval-live会调用真实API，单独执行；默认CI不收费。DeepSeek live-smoke使用隔离测试账号验证ASR、真实计划、数据库幂等及TTS。真实浏览器语音测试位于live-e2e，只在显式运行playwright.live.config.ts时执行，使用自制语音模拟麦克风，不代表真人硬件验收。

新安装需要Python3.12+、Node22+、pnpm11及uv。在apps/api执行uv sync --frozen，在apps/web执行pnpm install --frozen-lockfile和pnpm exec playwright install chromium。显式模拟启动为python scripts/tasks.py preview-local。

## 备份及部署

```powershell
./apps/api/.venv/Scripts/python.exe scripts/backup.py
./apps/api/.venv/Scripts/python.exe scripts/backup.py --source backups/某次备份.db --restore-to backups/新的恢复副本.db
```

SQLite使用一致性backup和integrity_check，拒绝覆盖已有目标。备份含私人数据，已排除Git及源码包。PostgreSQL分支采用pg_dump，本机尚未验收，恢复必须先在新库验证。

正式认证代码包含OIDC授权码+PKCE、state、nonce、JWKS校验及HttpOnly cookie。需配置AUTH_MODE=oidc、OIDC_ISSUER、OIDC_AUDIENCE、OIDC_JWKS_URL、OIDC_CLIENT_ID、PUBLIC_API_ORIGIN及供应商需要的OIDC_CLIENT_SECRET。回调地址为PUBLIC_API_ORIGIN/api/v1/auth/oidc/callback。真实身份供应商尚未配置验收。

Dockerfile、Compose、Caddy模板保留。公开发布前仍需真实OIDC、TLS域名、PostgreSQL和容器验收、备份恢复、隐私与内容审核及老年用户测试。不要把开发身份暴露到公网。

接口依据：[DeepSeek Chat](https://api-docs.deepseek.com/api/create-chat-completion/)、[ASR](https://api-docs.deepseek.com/api/asr/)、[TTS](https://api-docs.deepseek.com/api/tts/)。
