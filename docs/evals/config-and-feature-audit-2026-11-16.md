# 配置与功能核查（2026-11-16）

本次仅检查代码、本地配置解析及本机端口；没有输出密钥，没有调用收费模型，没有修改.env或业务代码。旧验收报告是2026-11-11的历史结果，本次没有重跑完整测试。

## 当前结论

加入现有.env后，真实模型没有启用。当前是具备持久化业务能力的内测工程，尚未接通用户期望的自然语音操作闭环。

### 直接核验

- .env存在，DEEPSEEK_API_KEY有值；有效性、额度、模型权限未验证。
- 该文件包含DEEPSEEK_API_KEY、DEEPSEEK_BASE_URL、DEEPSEEK_MODEL、USE_MOCK_LLM、KNOWLEDGE_BASE_PATH、RAG_TOP_K、PORT。
- 上述7个字段均不在Settings字段中；extra=ignore导致全部被忽略。
- 当前Settings解析结果：llm_provider=mock，audio_provider=mock，auth_mode=dev，app_env=local；OpenAI凭证未配置。
- 常规启动数据库默认指向PostgreSQL，但.env没有DATABASE_URL；未发现Docker命令，不能确认该默认数据库可连接。
- start-local.ps1调用preview-local。该任务强制将LLM_PROVIDER及AUDIO_PROVIDER设为mock，优先于.env；并强制使用SQLite。
- 检查时localhost:5173、localhost:8000均无法连接；端口检查未发现两端口监听。浏览器留有标签不代表服务正在运行。
- 未发现PATH上的ffprobe，当前WebM音频时长校验依赖尚未满足。

### 代码证据

- apps/api/app/config.py：读取根目录.env，仅支持mock/openai，忽略额外字段。
- apps/api/app/agent.py：OpenAI Responses调用；不读取DeepSeek的Key/Base URL/Model。
- scripts/tasks.py：preview-local显式覆盖提供商与数据库设置。
- apps/web/src/main.tsx：识别后仅setMessage，仍要求点击发送；TTS仅绑定播放回复按钮。
- apps/web/src/main.tsx：导航执行仅OPEN_LESSON和START_PRACTICE。
- apps/api/app/main.py：DISCOVER_SKILL仅回复目录介绍，不产生打开技能列表的UI动作。
- apps/api/app/main.py：私教控制与自述完成主要由关键词规则处理；课程问答才走模型分支。

## 功能与未完成原因

| 能力 | 当前实际情况 | 未完成原因及可行性 |
|---|---|---|
| 加入园艺、持久化、撤销、课程/陪练导航ACK | 代码已有，历史Mock/SQLite E2E通过 | 真实业务逻辑，不等于真实AI理解已验证；可继续使用 |
| DeepSeek自然语言意图理解 | 未接入 | 原实现按规范默认OpenAI开发，尚未新增DeepSeek适配器；可实现，非.env改名即可 |
| 真实ASR与TTS | 已有OpenAI调用代码，未接通验收 | 当前配置不匹配、缺语音提供商配置、ffprobe缺失；可实现 |
| 说完直接执行、自动语音反馈 | 未实现 | 前端刻意采用核对后发送和手动播放；需新增用户可控的语音操作模式、自动发送和播报、错误退路；不是只补Key |
| 连续对话与自然打断 | 未实现 | 当前为最长19秒的单段录音，无实时会话/VAD/打断状态管理；可实现，工程范围高于单段录音 |
| 返回首页、打开技能广场等通用语音导航 | 未覆盖 | 白名单只实现打开课程和进入陪练；需扩展意图、动作分发及页面ACK |
| “看看园艺有什么课”直接打开列表 | 未实现 | 当前只产生介绍文字；与目标体验有差距，需补导航动作 |
| 跨轮澄清、指代、复杂任务恢复 | 不完整 | 未保存待澄清槽位，无通用多轮工具循环和退避恢复；可实现，属于上一轮未完成项 |
| 私教自由表述的步骤推进 | 部分实现 | 关键控制依赖关键词；不保证识别各种同义说法或步骤相关性；需语义解析及状态校验 |
| 多技能、视频课 | 仅一门园艺文字草稿 | 首版范围收缩，且无已审核授权视频；功能可开发，内容需制作/授权/审核 |
| RAG知识库 | 未实现 | R1采用结构化课程，不依赖RAG；现有RAG变量无作用。课程扩张后可按需要开发 |
| 视觉动作判断、自动推进 | 未实现 | R1明确排除，可靠性需要限定任务、数据集与评估；不能承诺任意动作均可靠判断 |
| 社区、作品发布、支付 | 未实现 | 明确不在R1范围，还需独立业务和审核流程 |
| 正式账号、跨设备同步、生产部署 | 不完整/未验收 | 本地共用开发身份，OIDC仅后端验签，缺登录流程；PostgreSQL、TLS、备份恢复等未验证 |
| 内容与用户效果认证 | 未完成 | 需专业内容审核及真实目标用户研究，不能用代码或Mock测试代替 |

## 建议优先顺序

1. 继续使用用户已有DeepSeek时，先增加独立提供商适配器及配置校验，使未识别变量显式报错；区分模拟启动和读取真实配置的启动入口。
2. 本地可先显式使用SQLite验证真实模型操作，不必把Docker当作本地语音体验的先决条件；PostgreSQL是后续独立验收。
3. 分别接入并验证ASR/TTS，补音频解码和时长兼容处理。
4. 完成说完执行、自动反馈、通用页面导航和跨轮澄清；保留文字/手动确认退路。
5. 验证真实语音→模型工具→数据库→页面就绪ACK→语音回执，再扩内容、实时语音或视觉。

上一轮交付没有完成原文档全部R1要求，原因包含外部资源不足，也包含实现尚未补齐，不能全部归因于用户未提供API Key。

语音能力接口说明参考：[OpenAI Audio and voice](https://developers.openai.com/api/docs/guides/audio)。是否继续采用OpenAI语音或其他提供商，需要与DeepSeek文本模型适配分开配置与验证。
