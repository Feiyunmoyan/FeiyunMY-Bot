# FeiyunMY-Bot

> 单人使用的本地 AI 伴侣 / 自主 Agent 框架。核心是**人格 + 长期记忆 + 主动推送**三件套。

不是又一个聊天框。目标是 Neuro-sama 那类"有人格连续性的角色"：它会记得你上周说过什么，会在没人找它的时候自己找个由头说话，而不是每轮都从零开始装熟。

![人格对话](screenshots/persona-dialogue.png)

---

## 为什么写这个

用久了会发现聊天机器人有三个绕不过去的问题：

| 问题 | 表现 | 这个项目的解法 |
|---|---|---|
| **人格不连续** | 换个会话就不认识你了 | 人格作为独立文档注入，多人格可切换，带静默覆盖检测 |
| **记不住事** | 上周定的方案，今天要重讲一遍 | 自研 Memoria 记忆后端：VAD 情感 + 重要度评分 + 遗忘曲线 |
| **不会主动** | 永远只能你先开口 | 主动引擎：按时间、情境、扰动决定要不要说话、说什么 |

前两个是"记忆"问题，第三个是"时机"问题——后者难得多，因为**沉默才是默认，说话需要理由**。

![记忆召回](screenshots/memory-recall.png)

上面这张是记忆召回的实际效果：它能把"你曾经说过最喜欢我"这条翻出来，并带着当时的情绪一起复述。

---

## 主要模块

```
persona/          人格系统：文档驱动，多份可切换，覆盖检测
memory/           长期记忆：Memoria 后端（向量 + VAD + 遗忘曲线）
                  + 简易后端（SQLite，无外部依赖）
active_engine/    主动推送：调度 / 情境判断 / 权重反馈 / 压缩
agent/            Agent 执行器：上下文构建、压缩、工具执行、流式
workspace/        多 Agent 工作区协同
provider/         模型 Provider 抽象（OpenAI 兼容）
tools/ · skills/ · mcp/   工具、技能、MCP 接入
api/              FastAPI 路由层（管理面板后端）
webui/            Vue 3 + Vite 管理面板
knowledge/        知识库（文档检索）
db/               SQLite 与迁移
```

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.13 · FastAPI · uvicorn · SQLModel / aiosqlite |
| 模型 | OpenAI 兼容协议 → DeepSeek |
| 记忆 | chromadb + sentence-transformers（本地 BGE）+ 情感分析 + 艾宾浩斯衰减 |
| 前端 | Vue 3 · Vite · Tailwind（构建产物挂载在 `/admin`） |
| 存储 | SQLite（会话/人格/配置）+ ChromaDB（向量） |

## 快速开始

```bat
:: 一条命令走完：环境自检 → 代码完整性 → 端口检查 → 前台启动 → 退出收尾
FeiyunMY-Bot.bat
```

启动后：

- 管理面板 <http://localhost:8765/admin>
- API 文档 <http://localhost:8765/docs>

脚本会自动：校验 Python 版本 → 创建 `.venv` 并装依赖 → 从模板生成 `config.yaml`/`.env` → `compileall` + `ruff` 静态检查 → 检测端口占用 → 启动 → 退出时清理残留进程。

### 配置与密钥

- `config.yaml` —— 主配置（**不入库**，模板见 `config.example.yaml`）
- `.env` —— 密钥与访问令牌（**不入库**，模板见 `.env.example`）

| 配置项 | 环境变量 |
|---|---|
| `provider.api_key` | `FEIYUN_API_KEY` |
| `web_search.api_key` | `TAVILY_API_KEY` |
| 访问令牌 | `FEIYUN_ACCESS_TOKEN` |

## 访问鉴权

服务监听 `0.0.0.0:8765`，局域网可访问，因此内置令牌鉴权：本机访问免令牌，局域网/移动端需 `Authorization: Bearer <token>`，或通过面板换取 HttpOnly Cookie。

## 现状与边界

**状态**：v1 已可用，处于「复盘完成、准备重启 V2」。

**已知短板**（写在最前面，不藏）：

- **没有量化指标** —— 目前无法用数据证明记忆召回、主动推送时机的好坏
- **没有自动化回归测试** —— 只有 `ruff` + `compileall` 两道静态关卡
- **单人本地** —— 多用户、并发、部署形态都没做
- **情感轴的有效性未验证** —— 情感参与排序和衰减，但没有对照实验

**已完成的重构**（2026-10）：

- `api/admin.py` 1125 行 → 门面 50 行 + 9 个子模块，53 个端点逐条比对一致
- `memory/backends/memoria/__init__.py` 700+ 行 → 108 行，拆为 store/cloud/emotion/retrieval/importance/ebbinghaus/emotion_fusion
- `agent/runner.py` 700+ → 402；`active_engine/scheduler.py` 700+ → 467
- 人格"静默覆盖"：覆盖预设时输出 WARNING，新增 `_origin` 记录数据来源

## 文档

设计文档、架构说明、交接记录都在 [`docs/`](docs/README.md)。建议从 [`docs/handover/V1复盘与评测指南.md`](docs/handover/) 和 [`docs/arch/ARCH_V2.md`](docs/arch/ARCH_V2.md) 开始。

## 开发

```bat
cd webui
npm install
npm run dev      :: 前端热更新，代理到 127.0.0.1:8765
npm run build    :: 构建到 webui/dist
```

## 许可

**未添加开源许可证。** 源码公开用于展示与交流，保留所有权利（All rights reserved）。

如需引用或复用，请先通过 Issue 联系。
