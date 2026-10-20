# FeiyunMY-Bot

单人使用的本地 AI 伴侣 / 自主 Agent 框架。核心是「人格 + 长期记忆 + 主动推送」三件套，外加多 Agent 工作空间协同。

目标形态参考 Neuro-sama 一类的自主 AI 主播/伴侣：不是被动应答的聊天框，而是会自己找时机说话、记得住事、有人格连续性的角色。

## 技术栈

| 层 | 内容 |
|---|---|
| 后端 | Python 3.13 · FastAPI · uvicorn · SQLModel/aiosqlite |
| 模型 | OpenAI 兼容协议 → DeepSeek |
| 记忆 | 自研 Memoria 后端：chromadb + sentence-transformers（本地 BGE 模型）+ 艾宾浩斯衰减 + 情感分析 |
| 前端 | Vue 3 · Vite · Tailwind（构建产物挂载在 `/admin`） |

## 快速开始

```bat
:: 1. 创建独立虚拟环境并安装依赖（只需一次，约 1.3 GB）
setup_venv.bat

:: 2. 填入密钥
copy .env.example .env
::    编辑 .env，填写 FEIYUN_API_KEY / TAVILY_API_KEY

:: 3. 启动
start.bat        :: 前台，显示日志
start_bg.bat     :: 后台静默
stop.bat         :: 停止服务
```

启动后：

- 管理面板 <http://localhost:8765/admin>
- API 文档 <http://localhost:8765/docs>

### 环境说明

项目使用**自带的独立虚拟环境** `.venv`（不依赖系统 Python，也不依赖其他项目）。

手动启动请用：

```powershell
.\.venv\Scripts\python.exe main.py
```

`start.bat` / `start_bg.bat` 会自动优先使用 `.venv`。

## 配置与密钥

- `config.yaml` —— 主配置（**不入库**，模板见 `config.example.yaml`）
- `.env` —— 密钥与访问令牌（**不入库**，模板见 `.env.example`）

敏感项从环境变量注入，`config.yaml` 中对应字段留空即可：

| 配置项 | 环境变量 |
|---|---|
| `provider.api_key` · `providers[].api_key` | `FEIYUN_API_KEY`（多 Provider 可用 `FEIYUN_API_KEY_<ID>`） |
| `web_search.api_key` | `TAVILY_API_KEY` |
| 访问令牌 | `FEIYUN_ACCESS_TOKEN` |

也支持 `${ENV_NAME}` 占位符写法。

## 访问鉴权

服务监听 `0.0.0.0:8765`，局域网内可访问，因此内置了令牌鉴权（`config.yaml → server.auth`）：

- **本机访问**（127.0.0.1 / ::1）默认免令牌，`local_bypass: true`
- **局域网 / 移动端**需要令牌，支持三种方式：
  - 请求头 `Authorization: Bearer <令牌>`
  - 请求头 `X-Access-Token: <令牌>`
  - 管理面板内输入令牌换取 HttpOnly Cookie（30 天）
- 令牌来源：`FEIYUN_ACCESS_TOKEN` > `data/access_token.txt`（不存在则自动生成）
- 管理面板 `/admin` 与 `/` 本身放行，令牌在页面内输入

## 目录结构

```
main.py               入口：初始化各模块 + 注册路由 + 鉴权中间件
config.yaml           主配置（不入库）
requirements.txt      依赖清单
requirements.lock.txt 精确版本锁定

api/                  FastAPI 路由层
agent/                Agent 执行器与上下文
active_engine/        主动推送引擎（调度 / 冷启动 / 压缩）
memory/               记忆系统，backends/{simple, memoria}
tools/                工具层（web / file_ops / execute / agent_tools …）
workspace/            多 Agent 工作空间
provider/             Provider 管理与 OpenAI 兼容实现
persona/              人格系统
knowledge/            知识库
skills/ · mcp/        技能与 MCP 接入
db/                   SQLite 与迁移
utils/                配置热加载、日志等

webui/                Vue3 前端（源码在 src/，构建产物在 dist/）
docs/                 设计文档（见 docs/README.md）
data/                 运行时数据（不入库）：数据库、向量库、BGE 模型、日志
.venv/                项目虚拟环境（不入库）
```

## 文档

设计文档、架构说明、交接记录都在 [`docs/`](docs/README.md)。建议从 `docs/handover/V1复盘与评测指南.md` 和 `docs/arch/ARCH_V2.md` 开始看。

## 当前状态

v1 已可用，处于「复盘完成、准备重启 V2」阶段。

已知待办：

- 指标体系缺失 —— 目前没有量化数据能证明记忆召回、主动推送时机的优劣
- 代码臃肿 —— `api/admin.py`、`memory/backends/memoria/__init__.py`、`agent/runner.py`、`active_engine/scheduler.py` 均超过 700 行，需拆分
- 未接线的死代码已清理（`engine/dispatcher.py`、`utils/exceptions.py`、`agent/message.py`）

## 开发

```bat
cd webui
npm install
npm run dev      :: 前端热更新，代理到 127.0.0.1:8765
npm run build    :: 构建到 webui/dist
```

## 许可

未指定。
