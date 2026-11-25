# 小伴 · 银发 AI 私教

面向中老年用户的兴趣学习应用，支持语音操作、课程学习、语音与视频陪练，以及图片和视频分享。界面适配手机和电脑浏览器，提供大按钮与字号调节。

## 功能

- **首页**：查看正在学习的技能和社区推荐作品，调节字号。
- **技能广场**：搜索或浏览园艺、书法、摄影、乐器四类技能，共十二节教程，保存学习进度和已完成技能。
- **小伴语音助手**：通过底部麦克风对话，加入或移除正在学习的技能、推荐课程、切换页面和控制教程播放。在分享页观看作品时，可说“我想学这个”加入对应技能。
- **陪练**：语音陪练根据描述给出指导；视频陪练根据摄像头抽样画面给出提示，支持切换可用镜头。
- **分享**：社区浏览与“我的作品”，支持图片、视频上传及全屏查看。

项目由 React / TypeScript 前端和 FastAPI 后端组成，默认使用 SQLite 保存本地数据。目前通过浏览器运行，未提供 Android/iOS 安装包；支付功能未开放。

## 本地部署

### 环境要求

- Python 3.12 或更新版本
- Node.js 22 或更新版本
- pnpm 11
- uv
- Git

### 1. 克隆项目

```sh
git clone https://github.com/AEI728/Senior-AI-Tutor.git
cd Senior-AI-Tutor
```

也可使用 SSH 地址：`git@github.com:AEI728/Senior-AI-Tutor.git`。

### 2. 安装依赖

在项目根目录打开终端：

```sh
cd apps/api
uv sync --frozen
cd ../web
pnpm install --frozen-lockfile
cd ../..
```

### 3. 配置环境变量

首次安装时复制配置模板。已有 `.env` 的项目保留现有配置。

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

macOS / Linux：

```sh
cp .env.example .env
```

默认使用 SQLite 和模拟模型，无需启动 Docker，可以查看页面及课程流程。真实对话、语音识别、播报与图像反馈需要配置对应模型服务。

使用 DeepSeek 兼容服务时，在 `.env` 中填写：

```dotenv
LLM_PROVIDER=deepseek
AUDIO_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
APP_PORT=4312
```

服务地址、模型和音色应使用提供商实际支持的值。语音需要 ASR/TTS 接口，视频陪练需要图像输入能力；只有文本接口不能提供全部功能。更多配置见 [.env.example](.env.example)。

### 4. 启动

Windows PowerShell：

```powershell
.\apps\api\.venv\Scripts\python.exe scripts/tasks.py local
```

macOS / Linux：

```sh
./apps/api/.venv/bin/python scripts/tasks.py local
```

启动脚本会创建数据库、初始化课程并启动前后端。保持终端运行，在浏览器打开：

- 应用：[http://localhost:5173](http://localhost:5173)
- 接口文档：[http://localhost:4312/docs](http://localhost:4312/docs)

在 VS Code 中也可打开项目根目录，运行任务“**小伴：启动前后端**”。终端按 **Ctrl+C** 停止服务，修改 `.env` 后需要重新启动。

## 使用

1. 在技能广场选择技能并加入学习，点击技能卡片查看教程。
2. 按住底部麦克风说话，松开后提交，例如“打开技能广场”“把书法加入，再打开第一节课”。
3. 在陪练页选择语音或视频模式，点击开始。语音陪练在停顿后自动提交，结束时点击结束按钮；AI 回复以语音播报。
4. 在分享页浏览社区内容，或切换到“我的”上传图片、视频。

首次使用语音或视频时允许浏览器访问麦克风、摄像头。收音异常可打开 [音频诊断页](http://localhost:5173/debug/audio)，检查实际输入设备与输入峰值。

学习记录及作品保存在项目根目录 `local-preview.db`；配置保存在 `.env`。这两个文件由本机生成，不随仓库分发。

## 运行说明

- 模拟模式用于页面与流程体验，不提供真实语音识别和视觉反馈。
- 视频陪练使用抽样画面，不进行动作达标认证；课程与内置分享是演示内容。
- 手机访问麦克风、摄像头需要 HTTPS 等安全上下文。电脑本地调试使用 `localhost`。
- 默认配置面向本地运行。对外部署需配置认证、数据库与 HTTPS。

## 项目目录

```text
apps/web/       前端页面与语音、摄像头交互
apps/api/       后端接口、模型调用、System Prompt 与 Skill
data/           课程、知识资料和示例元数据
media/          内置视频素材
scripts/        启动与维护工具
docs/           技术文档与接口契约
```
