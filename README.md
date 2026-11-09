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
:: 双击即可，一条命令走完：环境自检 → 代码完整性 → 端口检查 → 前台启动 → 退出收尾
FeiyunMY-Bot.bat

:: 跳过 [2/5] 代码完整性检查，快速启动
FeiyunMY-Bot.bat --fast
```

脚本会自动完成这些事：

| 阶段 | 内容 |
|---|---|
| [1/5] 环境自检 | Python 版本校验（要求 3.10+）；无 `.venv` 则创建并装依赖；缺 `config.yaml` / `.env` 从模板生成 |
| [2/5] 代码完整性 | 关键文件与目录 → `compileall` 语法编译 → `ruff` 静态检查 |
| [3/5] 端口与残留 | 清理本项目的残留进程；检测 8765 占用并询问 |
| [4/5] 前台启动 | 日志直接输出到窗口 |
| [5/5] 收尾清理 | 服务退出后自动结束残留进程、释放端口 |

详见 [`docs/启动脚本说明.md`](docs/启动脚本说明.md)。

停止服务：本窗口按 `Ctrl+C`；若提示 `终止批处理操作吗(Y/N)?`，请选 **N**（这样才会执行 [5/5] 收尾）。

启动后：

- 管理面板 <http://localhost:8765/admin>
- API 文档 <http://localhost:8765/docs>

### 环境说明

项目使用**自带的独立虚拟环境** `.venv`（不依赖系统 Python，也不依赖其他项目）。

手动启动请用：

```powershell
.\.venv\Scripts\python.exe main.py
```

`FeiyunMY-Bot.bat` 会自动优先使用 `.venv`；旧的 `start.bat` 仅作排障参考保留。

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
FeiyunMY-Bot.bat      一体化启动脚本（自检 / 检查 / 启动 / 收尾）
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
- 缺少自动化回归测试 —— 目前只有 `ruff` + `compileall` 两道静态关卡
- 新的体积警戒点 —— `memory/backends/memoria/cloud.py`（571 行）、`tools/agent_tools.py`（472 行）

已完成：

- **代码臃肿（2026-10-26）**
  - `memory/backends/memoria/__init__.py` 700+ → 108，拆为 `store / cloud / emotion / retrieval / importance / ebbinghaus / emotion_fusion`
  - `agent/runner.py` 700+ → 402，上下文逻辑拆到 `context_builder / context_compressor / agent_runner`
  - `active_engine/scheduler.py` 700+ → 467，拆出 `push / situation / weights / push_exec / push_compressor / disturbance`
  - `api/admin.py` 1125 → 50，按领域拆为「门面 + 状态容器 + 9 个子模块」：

    | 文件 | 行数 | 职责 |
    |---|---:|---|
    | `admin.py` | 50 | 门面：聚合子路由 + 转发依赖注入 |
    | `admin_state.py` | 53 | `AdminDeps` 依赖容器（原先 9 个模块级全局变量收口于此） |
    | `admin_models.py` | 86 | 请求体模型 |
    | `admin_config.py` | 83 | 配置读写 / 热加载 |
    | `admin_provider.py` | 126 | Provider 切换 / 连通性测试 |
    | `admin_persona.py` | 79 | 人格 CRUD |
    | `admin_search.py` | 58 | 搜索引擎 |
    | `admin_capability.py` | 181 | MCP / Skills / Shell 白名单 |
    | `admin_memory.py` | 84 | 记忆管理 / 记忆与工具开关 |
    | `admin_session.py` | 199 | 会话 / 文件上传 |
    | `admin_system.py` | 86 | 统计 / 日志 / `/test` |

    迁移后 53 个端点的路径、方法与注册顺序逐条比对一致，`main.py` 零改动；`ruff check .` 全项目通过。
  - `api/admin.py` 内联的旧测试页（211 行 HTML）抽到 `api/test_page.py`，`/test` 改为按需导入
- **人格「静默覆盖」（2026-10-26）** —— `PersonaManager` 原先遇到 `data/personas/` 下与预设同名的文件时会无声覆盖预设版本，同时把面板标记误判为「预设」、且删除接口拒绝删除。现补齐三件事：覆盖时输出 WARNING（含字数与预设对话差异）、新增 `_origin` 记录数据真实来源（面板返回 `origin` / `overrides_preset`）、删除自定义覆盖时自动回退到预设内容
- **未接线的死代码**已清理（`engine/dispatcher.py`、`utils/exceptions.py`、`agent/message.py`）

## 开发

```bat
cd webui
npm install
npm run dev      :: 前端热更新，代理到 127.0.0.1:8765
npm run build    :: 构建到 webui/dist
```

## 许可

未指定。
