# FeiyunMY-Bot 项目交接文档

> 生成时间：2026-05-15
> 项目路径：`F:\FeiyunMY-Bot`
> 启动方式：双击 `start.bat`

## 🧠 主脑任务自动化设计（可落地）

### 设计原则

- 主脑不需要"自动思考"，靠 **3 个工具 + 1 段提示词** 驱动
- 人格提示词保持纯净，项目管理规则作为独立 system 消息追加

### 新建工具

#### 1. `decompose_task` — 任务拆解

```
AI 调用 → 不对外暴露
参数: task_description（用户需求）
返回: 子任务列表 [{agent, task, depends_on}]
```

#### 2. `create_workspace` — 创建工作空间

```
参数: name（项目名）, agents（需要的 agent 列表）
作用: 创建新工作空间，自动生成各 agent 的会话
```

#### 3. `assign_task` — 派发任务

```
参数: workspace_id, agent_name, task_description
作用: 向指定 agent 派发任务（相当于 @agent + 消息）
```

### 追加的 system 消息（位于工具规则之后）

```
【项目管理工作流】
当用户提出项目需求时，按以下步骤执行：

第一步：调用 decompose_task 拆解任务
第二步：调用 create_workspace 创建工作空间
第三步：按依赖关系依次调用 assign_task 派发

派发后不需要等待每个 agent 完成，
可以继续处理其他事务或向用户反馈进度。

当 agent 完成后，检查结果：
- 没问题 → 汇总向用户汇报
- 有问题 → 重新派发或 @ 人工介入
```

### 完整工作流

```
用户：做个博客网站

① 主脑收到 → 看到"项目管理工作流"规则
② decompose_task("做个博客网站")
   → 返回 [{code, 前端}, {design, UI}, {backend, API}]
③ create_workspace("博客项目", [code, design, backend])
   → 创建空间 + 3个 agent 会话
④ assign_task("博客项目", "design", "设计UI")
   → design 开始工作
⑤ assign_task("博客项目", "backend", "写API")
   → backend 开始工作
⑥ 向用户汇报进度
```

### 工作空间存储结构

```json
{
  "workspace_id": "uuid",
  "name": "博客项目",
  "status": "active",
  "created_at": "timestamp",
  "agents": [
    {"name": "code", "session_id": "...", "status": "idle"},
    {"name": "design", "session_id": "...", "status": "working"},
    {"name": "backend", "session_id": "...", "status": "working"}
  ],
  "tasks": [
    {"agent": "design", "desc": "设计UI", "status": "done"},
    {"agent": "backend", "desc": "写API", "status": "working"},
    {"agent": "code", "desc": "前端", "status": "pending"}
  ],
  "shared_context": "项目全局信息..."
}
```

### 工作量

| 模块 | 代码量 |
|:----|:------:|
| 3 个新工具 | ~80 行 |
| 工作空间数据模型 | ~30 行 |
| 主脑提示词 | ~20 行 |
| **合计** | **~130 行** |

---

## 📋 项目概览

FeiyunMY-Bot 是一个轻量级 AI 聊天机器人框架，基于 Python + FastAPI，目标类似 Neuro-sama 风格。单 API 输入（非多平台），支持流式对话、工具调用、多会话管理、人格系统、记忆系统等。

---

## 🏗️ 项目目录结构

```
F:\FeiyunMY-Bot\
│
├── main.py                  # 入口文件，初始化所有模块，启动 FastAPI 服务
├── config.yaml              # 主配置文件（模型、工具开关、白名单等）
├── requirements.txt         # Python 依赖
├── start.bat                # 前台启动脚本（显示日志）
├── start_bg.bat             # 后台静默启动脚本
├── stop.bat                 # 停止服务脚本
│
├── api/                     # API 路由层
│   ├── chat.py              # 对话接口 POST /chat（非流式+流式）
│   └── admin.py             # 管理接口（配置、人格、搜索、MCP、Skills 等 CRUD）
│
├── agent/                   # Agent 执行层
│   ├── runner.py            # Agent 执行器（核心！消息组装、工具调用、流式输出、上下文管理）
│   ├── loop.py              # 向后兼容，导入 runner
│   └── context.py           # 会话上下文管理器（持久化到 data/conversations/）
│
├── provider/                # LLM API 适配层
│   ├── base.py              # Provider 抽象基类
│   └── openai_provider.py   # OpenAI 兼容 API 实现（DeepSeek等），支持流式+工具调用
│
├── tools/                   # 工具集（共 10 个）
│   ├── registry.py          # 工具注册中心，管理注册/执行/开关
│   ├── web_search.py        # 网页搜索（支持百度/DuckDuckGo/SerpAPI/Tavily/Bing）
│   ├── file_ops.py          # 文件读写（仅限 data/ 目录）
│   ├── code_exec.py         # Python 代码执行（沙箱）
│   ├── common_utils.py      # 常用工具：时间、计算器、随机
│   └── agent_tools.py       # Agent 工具：HTTP请求、笔记、JSON处理、Shell执行
│
├── memory/                  # 记忆系统
│   ├── bridge.py            # 记忆系统统一接口抽象类
│   ├── selector.py          # 记忆选择器（Simple/Memoria 模式切换）
│   └── backends/
│       ├── simple.py        # Simple 记忆（关键词匹配 + JSON 持久化）
│       └── memoria.py       # MemoriaDB 预留（空壳，待集成）
│
├── persona/                 # 人格系统
│   ├── manager.py           # 人格管理器（CRUD + 热切换 + 预设对话）
│   └── presets/
│       ├── default.yaml     # 默认助手人格
│       ├── tsundere.yaml    # 傲娇人格
│       └── gentle.yaml      # 温柔人格
│
├── mcp/                     # MCP 服务器管理
│   └── manager.py           # MCP 服务器 CRUD
│
├── skills/                  # Skills 技能管理
│   └── manager.py           # 技能管理器（支持 zip 包安装）
│
├── utils/                   # 工具函数
│   └── conversation_logger.py # 对话日志记录器
│
├── webui/                   # 前端（简单 Vue 测试面板）
│   └── index.html           # 单页应用，涵盖所有功能验证
│
└── data/                    # 数据目录（自动创建）
    ├── logs/                # 对话日志 *.jsonl
    ├── conversations/       # 会话持久化 *.json
    ├── memories/            # 记忆持久化 memories.json
    ├── personas/            # 用户自定义人格 *.yaml
    ├── notes/               # AI 笔记 ai_notes.json
    ├── mcp/                 # MCP 配置
    └── skills/              # 已安装的技能
        └── installed/       # 技能文件夹
```

---

## ✅ 已完成的模块

### 1. 后端 API（28+ 个端点）

| 分组 | 端点 | 说明 |
|------|------|------|
| 💬 对话 | `POST /api/chat` | 非流式对话 |
| | `POST /api/chat/stream` | 流式对话（SSE），支持工具调用 |
| ⚙️ 配置 | `GET/POST /api/config` | 配置读写 |
| 📊 统计 | `GET /api/stats` | 系统状态 + 所有开关状态 |
| 👤 人格 | `GET/POST/PUT/DELETE /api/personas/*` | 人格 CRUD + 激活 |
| 🔍 搜索 | `GET/POST/PUT/DELETE /api/search/engines/*` | 搜索引擎管理 |
| 🔌 MCP | `GET/POST/PUT/DELETE /api/mcp/servers/*` | MCP 服务器管理 |
| 🧩 Skills | `GET/POST/PUT/DELETE /api/skills/*` | 技能管理 |
| 💻 Shell | `GET/POST/DELETE /api/shell/whitelist/*` | Shell 白名单管理 |
| 🧠 记忆 | `GET/DELETE /api/memories/*` | 记忆管理 |
| | `POST /api/memory/toggle` | 记忆开关 |
| 📝 会话 | `GET/POST/PUT/DELETE /api/sessions/*` | 多会话管理 |
| | `POST /api/sessions/{id}/autoname` | 自动生成标题 |
| 🛠️ 工具 | `POST /api/tools/toggle` | 工具开关 |
| 🤖 模型 | `POST /api/provider/models` | 获取模型列表 |
| | `POST /api/provider/test` | 测试 API 连接 |

### 2. 工具系统（12 个）

| 工具 | 默认 | 说明 |
|------|------|------|
| `get_datetime` | ✅ 开 | 获取当前日期时间 |
| `calculator` | ✅ 开 | 数学表达式计算 |
| `random_utils` | ✅ 开 | 随机数/随机选择 |
| `note_taking` | ✅ 开 | AI 笔记管理 |
| `json_process` | ✅ 开 | JSON/CSV 数据处理 |
| `web_search` | ❌ 关 | 网页搜索（配 API Key） |
| `file_ops` | ❌ 关 | 文件读写 |
| `code_exec` | ❌ 关 | Python 代码执行 |
| `http_request` | ❌ 关 | HTTP 请求 |
| `shell_exec` | ❌ 关 | Shell 命令（白名单） |

### 3. 人格系统
- 3 个预设人格（default / tsundere / gentle）
- 支持自定义人格 CRUD
- 支持预设对话（few-shot 示例）
- 支持热切换
- 人格开关

### 4. 记忆系统
- Simple 模式：关键词匹配 + JSON 文件持久化
- Memoria 模式：预留接口（待集成）
- 支持运行时切换模式

### 5. 会话管理
- 多会话 CRUD
- 自动生成标题（根据对话内容）
- 持久化到 `data/conversations/`

### 6. Agent 执行器（6 步优化已完成）
1. ✅ 工具结果注入上下文
2. ✅ 思考过程记录
3. ✅ 错误重试（指数退避 3 次）
4. ✅ 并行工具调用
5. ✅ 上下文长度管理（超 8000 tokens 自动截断）
6. ✅ Agent 执行器分层（抽取出 `agent/runner.py`）

### 7. Skills 技能系统
- 支持从 `skillsmp.com` 下载 zip 包安装
- 拖拽安装
- 自动读取 SKILL.md
- 注入为行为准则（无需调用，自动生效）

### 8. MCP 服务器管理
- 自由增删 MCP 服务器
- 开关控制

### 9. Shell 白名单
- 动态白名单管理
- 可通过 API 或前端增删命令
- 安全限制（禁止危险操作）

### 10. 前端测试面板
- 单页 Vue 3 应用
- 覆盖所有功能验证
- 流式/非流式双模式对话

---

## 🔧 遇到并解决的问题

### 1. 流式工具调用
**问题**：流式模式下工具调用被忽略，模型说了"我查一下"就没后续了。
**解决**：Provider 端合并流式分块到达的 tool_calls delta，Chat 端支持多轮工具调用循环。

### 2. DeepSeek reasoning_content 必须传回
**问题**：DeepSeek 深度思考模式要求 `reasoning_content` 必须原样传回，否则报 400。
**解决**：保存助理消息时带上 `reasoning_content` 字段。

### 3. DeepSeek 不认识的 role
**问题**：`reasoning` 和 `tool` role 不被 DeepSeek API 接受（需要 `tool_call_id`）。
**解决**：存到上下文时统一用 `system` role，读取时做兼容转换。

### 4. Shell 工具 NotImplementedError
**问题**：`asyncio.create_subprocess_shell` 在 Windows Python 上抛 `NotImplementedError`。
**解决**：改用 `asyncio.to_thread(subprocess.run, ...)`。

### 5. GBK 编码问题
**问题**：Shell 命令输出含中文时 `subprocess.run` 解码失败。
**解决**：指定 `encoding='gbk', errors='replace'`。

### 6. 文件编辑转义问题
**问题**：多次出现 `\n` 被写成真实换行符导致 Python 语法错误。
**解决**：使用 Python 脚本做二进制替换（`b'...'.replace()`）。

### 7. 搜索提供商网络限制
**问题**：DuckDuckGo 在国内被墙，百度用 JS 渲染无法抓取。
**解决**：支持多个提供商（百度走 Bing HTML 搜索 / RSS、SerpAPI、Tavily、Bing API）。

### 8. 预设对话被当成真实对话历史
**问题**：预设对话以 user/assistant role 注入，模型以为是历史对话。
**解决**：改为嵌入 System Prompt 中作为示例说明。

### 9. 工具描述不够清晰
**问题**：模型不知道什么时候该调用哪个工具。
**解决**：优化所有工具 description，加入具体触发场景说明。

---

## 📝 配置说明

`config.yaml` 主要配置项：

```yaml
provider:
  base_url: https://api.deepseek.com   # API 地址
  api_key: ''                           # API Key（可用环境变量 FEIYUN_API_KEY）
  model: deepseek-chat                  # 模型名
  temperature: 0.7                      # 温度（0-2）
  max_tokens: 4096                      # 最大回复长度
  max_context_tokens: 8000              # 最大上下文长度
  top_p: 1.0
  presence_penalty: 0.0
  frequency_penalty: 0.0

tools:
  web_search: false                     # 各工具开关
  shell_exec: false
  ...

persona:
  active: default                       # 当前人格
  enabled: true                         # 人格开关

memory:
  enabled: false                        # false=Simple, true=Memoria

web_search:
  enabled: false
  provider: baidu                       # 搜索提供商
  api_key: ''

shell_whitelist:
  enabled: true
  commands: [dir, echo, type, ...]      # 白名单命令列表
```

---

## 🔮 未来计划

| 优先级 | 项目 | 说明 |
|--------|------|------|
| ⚡ 高 | **集成 MemoriaDB** | 把 BGE 向量 + 情感分析 + 艾宾浩斯衰减接上 |
| ⚡ 高 | **对话日志分析** | 用积累的日志数据改进记忆系统 |
| 📝 中 | **前端重写** | Next.js + shadcn/ui + Tailwind（主人计划） |
| 📝 中 | **MCP 接入** | 让 AI 能调用外部 MCP 工具 |
| 🔮 低 | **子代理** | 多 Agent 编排，类似 AstrBot 的 HandoffTool |
| 🔮 低 | **多模态** | 语音输入/输出 |

---

## 🔗 参考链接

- AstrBot 项目：`F:\AstrBotLauncher-0.3.0\AstrBot`
- Skills 市场：https://skillsmp.com/zh
- FastAPI 文档：http://localhost:8765/docs （运行时）
- 管理面板：http://localhost:8765/admin （运行时）

---

> 文档由亚托莉 (Atri) 整理于 2026-05-15
> 如有疑问，请查阅代码注释或运行测试

---

# 🆕 增量更新 2026-05-21 — SQLite 数据库迁移

> 本次更新将会话存储从 JSON 文件切换到 SQLite 数据库，参考了 AstrBot 的存储方案。

---

## 📦 新增模块

### 11. 数据库层（`db/` 目录）

| 文件 | 说明 |
|------|------|
| `db/__init__.py` | 模块导出入口 |
| `db/models.py` | SQLModel 数据模型（`Conversation`、`Session`） |
| `db/database.py` | 异步 SQLite 数据库操作层（参考 AstrBot `SQLiteDatabase`） |
| `db/migration.py` | JSON → SQLite 自动迁移脚本 |

### 12. 存储方式变更

| 项目 | 改造前 | 改造后 |
|------|--------|--------|
| **存储介质** | JSON 文件（`data/conversations/*.json`） | SQLite 数据库（`data/feiyun.db`） |
| **读写方式** | 同步文件读写 | 异步 ORM（SQLModel + aiosqlite） |
| **数据完整性** | ❌ 写入中断可能丢数据 | ✅ 事务保障原子性 |
| **并发支持** | ❌ 多线程写入冲突 | ✅ WAL 模式，`busy_timeout=30` |
| **查询能力** | ❌ 需手动遍历文件 | ✅ 支持 SQL 灵活查询 |
| **迁移脚本** | — | 首次启动自动从 JSON 迁移到 SQLite，原文件备份到 `json_backup/` |

---

## 🏗️ 更新后目录结构（新增部分）

```
F:\FeiyunMY-Bot\
│
├── db/                     # 【新增】数据库层
│   ├── __init__.py         # 模块入口
│   ├── models.py           # SQLModel 模型（Conversation, Session）
│   ├── database.py         # FeiyunDatabase 异步操作类
│   └── migration.py        # JSON → SQLite 自动迁移脚本
│
└── data/
    ├── feiyun.db           # 【新增】SQLite 数据库文件（所有会话数据）
    └── conversations/
        └── json_backup/    # 【新增】旧 JSON 数据备份目录
```

---

## ✅ 已更新的模块

### 5. 会话管理（已重构）

- 存储后端从 JSON 文件切换为 **SQLite 数据库**（`data/feiyun.db`）
- 引入数据库表结构：
  - `sessions` 表：会话元信息（ID、标题、时间戳等）
  - `conversations` 表：对话消息内容（`content` 字段存 `list[dict]`，兼容 OpenAI 格式）
- 内存缓存 + 异步持久化策略，兼顾性能与安全性
- 支持自动迁移旧 JSON 数据

### 6. Agent 执行器（增加适配）

- `build_messages()` 改为异步方法（需 `await`），以适配异步数据库读取
- 所有 `context.*` 调用改为 `await` 异步调用

---

## 🔧 本次遇到并解决的问题

### 1. SQLAlchemy 异步模式 PRAGMA 语句需用 text() 包装
**问题**：`conn.execute("PRAGMA journal_mode=WAL")` 在异步模式下报错。
**解决**：改用 `from sqlalchemy import text` → `conn.execute(text("PRAGMA journal_mode=WAL"))`。

### 2. Python 方法覆盖（同名的 get_session 冲突）
**问题**：`get_session()`（返回数据库连接）和 `get_session(session_id)`（查询业务会话）同名，后者覆盖前者。
**解决**：将返回数据库连接的方法重命名为 `get_db_session()`。

### 3. 协程对象不支持异步上下文管理器
**问题**：`async with self.get_db_session() as session` 报错，因为 `get_db_session()` 是 async 函数，返回协程而非直接可用对象。
**解决**：改为 `session = await self.get_db_session()` 先 await 拿到 session 对象，再 `async with session`。

### 4. 消息数量统计语义错误
**问题**：`list_sessions()` 中用 `count(conversation_id)` 统计消息数，结果永远只有 0 或 1。
**解决**：改为 `coalesce(sum(message_count), 0)` 累加真实消息数。

### 5. UPDATE 不存在记录时不生效
**问题**：新会话调用 `update_conversation` 用 `UPDATE` 语句，但记录不存在则无效果。
**解决**：先检查记录是否存在，存在则 UPDATE，不存在则 CREATE（UPSERT 逻辑）。

---

## 📝 更新后数据存储说明

数据库文件位于 `data/feiyun.db`，包含两张核心表：

### `sessions` 表
| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | TEXT (PK) | 会话唯一标识 |
| `title` | TEXT | 会话标题/名称 |
| `is_active` | BOOLEAN | 是否活跃 |
| `created_at` | DATETIME | 创建时间 |
| `updated_at` | DATETIME | 更新时间 |

### `conversations` 表
| 字段 | 类型 | 说明 |
|------|------|------|
| `conversation_id` | TEXT (PK) | 对话唯一标识（16位hex） |
| `user_id` | TEXT | 对应用户/会话ID |
| `content` | JSON | 消息列表 `[{role, content, timestamp}]` |
| `title` | TEXT | 对话标题 |
| `message_count` | INTEGER | 消息总数 |
| `token_usage` | INTEGER | Token 消耗 |
| `created_at` | DATETIME | 创建时间 |
| `updated_at` | DATETIME | 更新时间 |

---

## 🔮 未来计划（更新后）

| 优先级 | 项目 | 说明 |
|--------|------|------|
| ⚡ 高 | **集成 MemoriaDB** | 把 BGE 向量 + 情感分析 + 艾宾浩斯衰减接上 |
| ⚡ 高 | **对话日志分析** | 用积累的日志数据改进记忆系统 |
| 📝 中 | **前端重写** | Next.js + shadcn/ui + Tailwind（主人计划） |
| 📝 中 | **MCP 真正的接入** | 让 AI 能调用外部 MCP 工具（目前只是管理界面） |
| 🔮 中 | **子代理 @ 分对话系统** | 见下方详细说明 ⬇️ |
| 🔮 低 | **多模态** | 语音输入/输出 |

### 📌 子代理 @ 分对话系统（规划中）

**目标**：将子代理从"工具调用"升级为"可对话的协作者"。

**核心机制**：
```
主对话（主人 & 主Agent）              分对话（子Agent）
────────────────────                  ────────────────
[主人]: 帮我写个页面 @code_agent
  │
  └── 系统拦截 @ 指令 ──────────────→ 自动创建分对话 session
       │                              子Agent在分对话中实时流式输出
       │                              思考过程、工具调用、进度均可见
       │
[主Agent]: code_agent已完成，         分对话持续更新中...
          我检查了一下，没问题👍
           |
[主人]: 颜色再调一下 @code_agent
  │
  └── 自动跳回上次的分对话 ──────────→ 历史记录完整保留，可继续对话
```

**关键设计**：
- **@ 唤起**：主对话中输入 `@agent名称` 自动创建/定位到分对话
- **实时流展示**：子代理的思考、工具调用在分对话中实时呈现
- **分对话复用**：同个会话中再次 @ 同一 agent，自动续上历史
- **临时存储**：分对话标记为临时数据，重启时自动清理
- **主Agent审核**：子代理完成后，主Agent检查成果再向主人汇报

**分期规划**：

| 阶段 | 内容 |
|------|------|
| Phase 1 | 后端：@ 解析 + 子session创建 + 子Agent流输出 |
| Phase 2 | 前端：分对话面板 + 流分流展示 |
| Phase 3 | 临时存储策略 + 会话复用 + 主Agent审核机制 |

---

# 🆕 增量更新 2026-05-21（第二次）— 系统监控、限流、类型注解

> 本次更新增加了系统资源监控、API 限流防护，并补全了代码类型注解。

---

## ✅ 新增功能

### 13. 系统资源监控

| 文件 | 说明 |
|------|------|
| `utils/monitor.py` | 系统监控工具，提供内存/CPU/磁盘/运行时间等信息 |

**API 端点**：`GET /api/system/stats`

```json
{
  "uptime": 3600,
  "uptime_str": "1小时0分0秒",
  "memory": { "total": 17179869184, "available": 8589934592, "used": 8589934592, "percent": 50.0 },
  "cpu": { "percent": 23.5, "count": 4, "count_logical": 8 },
  "disk": { "total": 512000000000, "used": 256000000000, "free": 256000000000, "percent": 50.0 }
}
```

- 基于 `psutil` 库（可选依赖，未安装时返回 `{"note": "需安装 psutil"}`）
- 自动记录服务运行时长

### 14. API 限流

| 技术 | 说明 |
|------|------|
| 库 | `slowapi` + `limits` |
| 策略 | 基于请求来源 IP，**每分钟最多 60 次请求** |
| 超限响应 | HTTP 429 Too Many Requests |

- 全局默认限制：60次/分钟/IP
- 所有 API 端点自动继承该限制
- 防刷接口、防意外高并发

### 15. 类型注解补全

- 补全了 `tools/registry.py` 中 `register()`、`set_enabled()` 等方法缺失的返回类型注解
- 补全了 `agent/runner.py` 中 `__init__` 参数的类型注解（`mcp_manager`、`skills_manager` 等）
- 其余文件类型注解覆盖率已达 95%+（原有基础较好，主要补全遗漏项）

---

## 🔧 本次修复的问题

### 6. 流式对话中 AI 回复未保存到数据库
**问题**：`run_stream()` 中 `await self.memory.add(...)` 对同步方法使用了 `await`，导致 TypeError。用户消息已成功保存，但 AI 回复因异常未执行到保存逻辑。
**解决**：去掉多余的 `await`，同时增加 `else` 分支确保即使 `final_reply` 为空也能保存用户消息。

---

## 📦 新增依赖

```txt
psutil>=7.0.0          # 系统资源监控（可选，没有也能运行）
slowapi>=0.1.9         # API 限流
```

---

> 更新文档由亚托莉 (Atri) 整理于 2026-05-21

---

# 🆕 增量更新 2026-05-22 — MemoriaDB 长期记忆系统

> 本次更新将论文级别的 MemoriaDB 记忆系统完整集成到 FeiyunMY-Bot，替换原有的 SimpleMemory 空壳。

---

## 📦 新增模块

### 16. 长期记忆系统（`memory/backends/memoria/`）

| 文件 | 说明 |
|------|------|
| `__init__.py` | 主后端，整合 ChromaDB + BGE + 情感 + 评分 + 遗忘 |
| `emotion.py` | 情感分析器（BGE 语义 + 词典法双引擎） |
| `emotion_fusion.py` | **多轮情感融合层**（自适应冲突检测） |
| `importance.py` | 重要性评分器（BGE 语义 + 规则法双引擎） |
| `ebbinghaus.py` | **自适应艾宾浩斯遗忘管理器** |
| `data/` | 情感词典数据（程度副词、否定词、表情符号） |

### 17. BGE 中文语义模型

- 模型文件：`data/memoria/bge-model/`（约 1.3GB，从论文项目复制）
- 用于：中文向量检索、语义情感分析、语义重要性评估
- 懒加载：只加载一次，启动后常驻内存

---

## 🏗️ 更新后目录结构（新增部分）

```
F:\FeiyunMY-Bot\
│
├── memory/backends/memoria/    # 【重写】完整记忆系统
│   ├── __init__.py             # 主后端（ChromaDB + 全流程编排）
│   ├── emotion.py              # 情感分析（BGE语义 + 词典降级）
│   ├── emotion_fusion.py       # 【新增】多轮情感融合层
│   ├── importance.py           # 重要性评分（BGE语义 + 规则降级）
│   ├── ebbinghaus.py           # 【升级】自适应艾宾浩斯遗忘
│   └── data/                   # 情感词典数据
│
└── data/
    └── memoria/
        ├── chromadb/           # ChromaDB 向量数据库持久化
        └── bge-model/          # BGE-large-zh-v1.5 中文语义模型
```

---

## ✅ 新增工具

### 18. 记忆查询工具（`memory_query`）

AI 可主动查询长期记忆库，无需等待自动注入。

| 项目 | 说明 |
|------|------|
| 工具名 | `memory_query` |
| 参数 | `query`（搜索内容）、`top_k`（返回条数，默认5） |
| 触发场景 | AI 觉得需要回忆之前对话内容时主动调用 |
| 实现 | `tools/agent_tools.py` → 调用 `memory_selector.query()` |

### 19. 会话管理工具（`manage_session`）

AI 可自行创建新会话、列出所有会话。**对子代理功能至关重要**——每个子代理可在独立会话中工作。

| 项目 | 说明 |
|------|------|
| 工具名 | `manage_session` |
| 参数 | `action`（create/list/info）、`name`（新建时的标题） |
| 触发场景 | 需要区分话题、子代理需独立上下文时 |
| 实现 | `tools/agent_tools.py` → 调用 `context.create_session()` / `list_sessions()` |

**子代理场景示例：**
```
用户：帮我写个页面 @code_agent
→ code_agent 调用 manage_session("create", "页面开发")
→ 在自己的新会话里工作，不弄脏主会话
→ 完成后切回主会话汇报结果
```

---

## ✅ 记忆系统完整链路

```
用户说话
  │
  ▼
① 检索层：BGE 检索 ChromaDB → 注入 system prompt
  │
  ▼  AI 回复
  │
  ▼
② 总结层：LLM 提炼对话要点
  │
  ▼
③ 情感分析：BGE 语义（或词典降级）→ 分析用户原文情绪
  │  └─ ③-b 融合层：多轮追踪 + 自适应冲突检测
  │
  ▼
④ 重要性评分：BGE 语义 + 规则法 → 低于 0.3 丢弃
  │  └─ 情感加权：情绪越强 = 分数越高
  │
  ▼
⑤ 存储：ChromaDB（BGE 中文向量 1024维 + 元数据）
  │
  ▼
⑥ 遗忘：自适应艾宾浩斯公式
     R = 0.8 × e^(-decay × 天数 × 容量因子 × 情感因子)
     ├─ 容量因子：超 75 万条加速遗忘
     ├─ 情感因子：情绪越强忘得越慢
     └─ 访问因子：常被检索的忘得慢
```

---

## 🔧 本次修复的问题

### 7. BGE 模型加载失败的环境问题
**问题**：`sentence-transformers` 安装在 AstrBot 虚拟环境中，但 FeiyunMY-Bot 使用系统 Python 运行，导致 ModuleNotFoundError。
**解决**：将依赖安装到系统 Python 3.13 中，并设置了词典法降级兜底。

### 8. 情感分析对象错误（重要）
**问题**：情感分析原本针对 LLM 总结文本（中性），导致情感加权完全失效。用户说"好难过"但系统分析的是总结"用户提到健康问题"→ 中性。
**解决**：改由 `metadata.user_message` 传入用户原文进行情感分析，总结文本仅用于存储。

### 9. f-string 换行导致 SyntaxError
**问题**：`runner.py` 中 LLM 总结的 prompt 被错误地写成多行，导致 f-string 未闭合。
**解决**：将 `

` 放在同一行内。

---

## 📦 新增依赖

```txt
chromadb>=0.4.0              # 向量数据库
sentence-transformers>=3.0.0 # BGE 中文语义模型
```

---

## 🎯 未来计划（更新于 2026-05-22）

| 优先级 | 项目 | 说明 |
|--------|------|------|
| 📝 中 | **前端重写** | Next.js + shadcn/ui + Tailwind |
| 📝 中 | **MCP 真正接入** | 让 AI 能调用外部 MCP 工具 |
| 🔮 中 | **子代理 @ 分对话系统** | 见上方详细规划 |
| 🔮 中 | **主动型 AI 系统** | 见下方说明 ⬇️ |
| 🔮 低 | **多模态** | 语音输入/输出 |

### 📌 主动型 AI 系统（规划中）

**目标**：让 AI 不再被动等待用户提问，而是在合适时机主动发起对话。

**核心场景**：
```
定时提醒  → "主人，您设置的2小时后提醒到了"
记忆触发  → "团子今天情况好点了吗？"（昨天聊过宠物生病）
异常通知  → "检测到磁盘占用超过90%，建议清理"
状态汇报  → 子代理任务完成后主动告知结果
```

**技术方案**：
- **后台调度器**：常驻定时循环，检查提醒队列、记忆跟进点、系统状态
- **推送通道**：WebSocket 或前端轮询，AI 主动推送消息到用户界面
- **与子代理联动**：子代理完成任务后，通过主动推送通知主对话

**分期规划**：

| 阶段 | 内容 |
|------|------|
| Phase 1 | 后台调度器 + 提醒队列（定时/条件触发） |
| Phase 2 | WebSocket 推送通道 + 前端通知展示 |
| Phase 3 | 记忆触发（自动跟进未完结的话题）+ 子代理联动 |

---

# 🆕 增量更新 2026-05-28 — 工具合并、系统优化、多 Agent 架构规划

> 本次更新完成了工具合并、文件上传、上下文压缩等功能，并规划了下一代多 Agent 协同架构。

---

## ✅ 已完成

### 20. 工具系统合并（13→10）

| 旧工具 | 新工具 | 说明 |
|:-------|:-------|:------|
| `get_datetime` + `calculator` + `random_utils` | → **`common_utils`** | 时间/计算/随机 |
| `web_search` + `web_extract` | → **`web`** | 搜索+网页读取 |
| `code_exec` + `shell_exec` | → **`execute`** | Python+Shell |

- 旧工具保留注册（向后兼容），但默认关闭
- `POST /api/tools/toggle` 支持旧名字自动映射到新工具

### 21. 文件上传（AstrBot 方式）

| 接口 | 方法 | 作用 |
|:----|:----|:------|
| `/api/files/upload` | POST | 上传文件，返回 `file_id` |
| `/api/files` | GET | 列出已上传的文件 |
| `/api/files/{filename}` | DELETE | 删除文件 |

- 文件内容嵌入到用户消息中（AstrBot 方式），AI 直接看到文件名+内容
- 聊天接口支持 `file_ids` 参数

### 22. `file_ops` 新增操作

| 操作 | 说明 |
|:----|:------|
| `grep` | 在文件内容中搜索关键词 |
| `delete` | 删除文件（不能删目录，防误删） |

### 23. 上下文压缩

- 新增 `_compress_context` 方法，每 N 轮（默认20）自动压缩旧对话
- 两种模式：`truncate`（直接删除）和 `summarize`（LLM 总结）
- 支持自定义压缩间隔、提示词、模型

### 24. 系统优化

| 项目 | 说明 |
|:----|:------|
| 系统提示词拆分 | 人格、工具规则、记忆、示例 分为独立 system 消息 |
| 工具规则增强 | 主动记录个人信息、文件上传目录提示 |
| 平台日志 | `GET /api/logs` 查看运行日志，支持级别/关键词过滤 |
| `tool_choice: auto` | 修复 AI 不调用工具的根因 |
| 多提供商管理 | `GET/POST /api/providers`，`POST /api/providers/switch` |

---

## 🏗️ 下一代架构规划：多 Agent 协同系统

### 设计理念

```
用户 ↔ 🧠 主脑（项目经理）
         ↕  @ 派发任务
      🤖 Agent 池（各司其职）
         ↕  实时汇报
      📋 工作空间（中间数据库）
```

### 核心结构

```
┌──────────────────────────────────────────────────────┐
│                    用 户                               │
│  实时观看 / 后台闲置 / 随时 @ 任意 agent 介入          │
└────────────────────┬─────────────────────────────────┘
                     │ @+任务描述
                     ▼
┌──────────────────────────────────────────────────────┐
│              🧠 主脑（项目经理）                       │
│  - 拆解任务、筛选 agent、创建工作空间                  │
│  - @agent 派发、监督进度、汇总汇报                     │
│  - 和用户同会话，无需 @                               │
└────────────────────┬─────────────────────────────────┘
                     │ @code_agent / @design_agent
                     ▼
┌──────────────────────────────────────────────────────┐
│            🔄 API 分发器（节流阀）                     │
│  - 同发最多 3 个请求，排队轮询回复                     │
│  - API Key 管理、优先级调度（用户 > 主脑 > agent）     │
└──────┬──────────┬──────────┬───────────────────────┘
       │          │          │
       ▼          ▼          ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│ 💻 Code │ │ 🎨 Des. │ │ 🧪 Test │
│ Agent   │ │ Agent   │ │ Agent   │
├─────────┤ ├─────────┤ ├─────────┤
│ 专属记忆 │ │ 专属记忆 │ │ 专属记忆 │
│ 知识库📚 │ │ 知识库📚 │ │ 知识库📚 │
└─────────┘ └─────────┘ └─────────┘
       │          │          │
       └──────────┴──────────┘
            🔄 共享上下文
       （工作空间全局信息面板）
```

### 工作流

```
① 用户 @主脑 "做个博客网站"
② 主脑拆解 → 需要前端/后端/设计
   → 创建工作空间（自动创建独立页面）
   → @code "用Vue搭建前端框架"
   → @design "设计UI风格"
   → @backend "写RESTful API"
③ 各 agent 收到任务 → 在自己的会话中工作
   → 所有消息实时保存到工作空间
   → 用户可打开工作空间实时查看进度
④ 发现问题 → 用户直接 @design "颜色改蓝色系"
   → agent 即时响应，不中断其他 agent 工作
⑤ 完成后 → 各 agent 结果汇总回主脑
   → 主脑检查整合 → 向用户汇报
⑥ 需要修改 → 用户 @主脑 "后端加个缓存"
   → 主脑重新 @backend 派发
```

### 关键设计决策

| 决策 | 说明 |
|:----|:------|
| **主脑无需 @** | 和用户同会话，自然交流 |
| **agent 不主动回复** | 仅被 @ 时响应，避免噪音 |
| **工作空间临时数据库** | 项目结束后可选保留或清理 |
| **API 分发器** | 控制并发、管理 Key、保证优先级 |
| **每个 agent 独立记忆库** | ChromaDB 隔离，不遗忘，积累经验 |
| **可配置知识库** | 每个 agent 可挂载专属知识库 |

### 与现有架构的关系

| 现有 | 扩展为 |
|:-----|:-------|
| 单条会话 | 工作空间（N条会话） |
| 用户↔AI | 用户↔主脑 + agent 池 |
| 共享长期记忆 | 主记忆 + 各 agent 专属记忆 |
| 统一工具集 | 主脑有管理工具，agent 有专业工具 |

### 路线图

| 阶段 | 内容 | 预估 |
|:----|:------|:----:|
| Phase 1 | 工作空间 CRUD + @ 路由 + 主脑逻辑 | 2-3 天 |
| Phase 2 | API 分发器 + 共享上下文 + agent 独立记忆库 | 2-3 天 |
| Phase 3 | 前端多面板界面 + 实时流展示 | 3-5 天 |

---

# 🆕 增量更新 2026-06-03 — 前端完善 + 主动引擎 + SSE推送 + 消息持久化

> 本次更新将前端从测试面板升级为完整管理界面，完善了主动引擎、SSE 推送、消息持久化等功能。

---

## ✅ 前端全面升级

### 新的管理面板（Vue 3 + Vite + Tailwind CSS）

原前端已从简单的单页测试面板替换为完整的管理界面，位于 `webui/` 目录：

| 页面 | 说明 |
|:----|:------|
| 🏠 **首页** | 系统状态总览 |
| 👤 **人格管理** | 人格 CRUD + 切换 |
| ⚙️ **配置** | 普通/系统/模型/记忆/工具配置 |
| 🧩 **Skills** | 技能管理 |
| 🔌 **MCP** | MCP 服务器管理 |
| 💬 **对话数据** | 会话管理 |
| 🔀 **子 Agent** | 子代理配置 |
| 📖 **知识库** | 知识库管理 |
| 📊 **数据统计** | 系统统计数据 |
| 📋 **平台日志** | 运行日志查看 |
| 💬 **Chat** | 对话界面 |
| 🏗️ **工作空间** | 工作空间管理 |

### 修复的工作空间 CRUD

**问题**：后端返回的 ID 字段为 `workspace_id`，但前端只认 `id` / `_id` / `uuid`，导致创建/删除/编辑全部失败。

**解决**：
- `loadWorkspaces()` 归一化时将 `workspace_id` 映射为 `id`
- 创建响应解析兼容 `data.workspace?.workspace_id`
- 删除后重新拉取列表确认空间真的被删除，而非只看HTTP状态码

---

## ✅ 主动引擎系统

### 创建的文件

| 文件 | 说明 |
|:----|:------|
| `active_engine/__init__.py` | 模块入口 |
| `active_engine/push.py` | SSE 推送引擎 + `PushMessage` / `PushEngine` 类 |
| `active_engine/disturbance.py` | 打扰指数算法 + 自适应学习器 |
| `active_engine/scheduler.py` | 三引擎调度器（定时/记忆/监控） |
| `api/active.py` | 主动引擎 API（SSE/配置/统计/用户状态） |

### 核心机制

```python
三引擎调度（每30秒检查）
├─ ⏰ 定时引擎：定时提醒
├─ 🧠 记忆引擎：扫描待跟进话题 → LLM生成主动聊天
└─ 📊 监控引擎：Agent 进度 + Token 消耗
```

- **打扰指数**：结合键盘频率/CPU/GPU/页面焦点/时段计算 (0~1)
- **自适应学习**：根据用户回应率动态调整打扰阈值
- **话痨模式**：high / medium / low / off 四档
- **免打扰时段**：自定义时间段内不推送

### API 端点

| 方法 | 路径 | 说明 |
|:----|:-----|:------|
| `GET` | `/api/events` | SSE 长连接（主动推送） |
| `GET` | `/api/active/config` | 获取主动引擎配置 |
| `PUT` | `/api/active/config` | 更新配置（持久化到JSON文件） |
| `GET` | `/api/active/stats` | 推送统计 |
| `POST` | `/api/user/status` | 用户状态上报 |
| `GET` | `/api/active/messages` | 历史推送消息（断连补推） |

### 配置持久化

**问题**：主动引擎配置（话痨模式/免打扰时段）保存在内存中，重启后丢失。

**解决**：`update_config()` 同时写入 `data/active_config.json`，启动时自动加载。

---

## ✅ SSE 推送与消息系统

### SSE 连接架构

```
App.vue 挂载 → connectSSE()（常驻连接，不随页面切换断开）
  └─ 首次连接时推送 "绯璃已上线" 启动消息
      └─ PushEngine.push() → 存储回调
          ├─ system_event / target=notification → SQLite notifications 表
          └─ 其他 → SQLite push_messages 表
```

### 前端消息面板

Chat 页面左侧增加两个常驻入口：

| 面板 | 特性 |
|:----|:------|
| 💬 **普通消息** | AI 主动推送（支持回复，有输入框） |
| 🔔 **系统通知** | 系统事件（只读，无输入框） |

- 自动加载历史消息（API 分页）
- 未读红点提示
- SSE 实时推送合并

### SSE 连接修复

**问题**：启动消息在 SSE 客户端连接前推送导致丢失。

**解决**：改为 SSE 客户端首次连接时推送，保证接收。

---

## ✅ 消息持久化

### 数据库新增表

| 表名 | 用途 | 清理策略 |
|:----|:-----|:--------|
| `notifications` | 🔔 系统通知 | 保留50条，启动时清理 |
| `push_messages` | 💬 普通消息 | 保留100条，超限时 LLM 总结后存入长期记忆 |

### 普通消息自动总结

```
消息超过100条？
├─ 是 → 取最旧的 N 条
│      → LLM 总结为摘要
│      → 存入 Memoria 长期记忆
│      → 删除旧消息
└─ 否 → 正常追加
```

---

## ✅ 上下文压缩修复

### 开关无效问题

**问题**：关闭压缩开关后，`compression_interval` 仍为 20，后端继续压缩。

**解决**：关闭时 `compression_interval` 设为 0，后端 `>0` 才触发。

### 跨提供商调用

**问题**：压缩模型若属于不同提供商，调用失败。

**解决**：前端保存 `compression_provider_id`，后端按模型ID遍历查找提供商，创建临时 Provider。

---

## ✅ 工具调用展示优化

### 旧样式（工具堆在顶部）

```
[AI]
  调用工具: web_search    ← 所有工具堆在顶部
  调用工具: get_weather
  北京天气晴朗...         ← 实际回答在下面
```

### 新样式（步骤时间线）

```
[AI]
  ● ⚙️ web_search ────  ← 步骤1，有连接线
  │  ┌ 参数/结果 (折叠) ┐
  │  └─────────────────┘
  │
  ● ⚙️ get_weather ───  ← 步骤2
     ┌ 参数/结果 (折叠) ┐
     └─────────────────┘
  
  北京天气晴朗...         ← 回答在底部
```

- 步骤圆点+竖线连接，调用顺序一目了然
- 状态指示：运行中(蓝色闪烁) / 失败(红色) / 完成(主色)
- 结果超出500字符自动截断

---

## 🔧 本次修复的问题汇总

| # | 问题 | 解决 |
|:--|:-----|:-----|
| 1 | 工作空间 CRUD 失败（ID字段 `workspace_id` 不匹配） | 归一化时兼容 `workspace_id` |
| 2 | 删除返回200但空间还在 | 删除后重新拉取列表确认 |
| 3 | 系统配置统计卡片一直显示0 | 适配新后端 stats 数据结构 |
| 4 | 上下文压缩开关无效 | 关闭时传 `interval=0` |
| 5 | 压缩模型跨提供商调用失败 | 创建临时 Provider |
| 6 | SSE 启动消息丢失 | 改为SSE客户端连接时推送 |
| 7 | 系统通知/普通消息不持久化 | SQLite 表 + 推送回调分流 |
| 8 | SSE 连接随页面切换断开 | 提升到 App.vue 级别常驻 |
| 9 | 配置页面按钮重复 | 系统配置排除公共底部按钮 |
| 10 | 点击会话不切换视图 | `selectSession` 内自动 `switchView('chat')` |
| 11 | 主动引擎配置重启丢失 | 写入 `data/active_config.json` |
| 12 | `database.py` 缺少 `import time` | 补全导入 |

---

## 🏗️ 更新后目录结构

```
F:\FeiyunMY-Bot\
│
├── active_engine/              # 【新增】主动引擎
│   ├── __init__.py
│   ├── push.py                 # SSE推送 + PushMessage/PushEngine
│   ├── disturbance.py          # 打扰指数 + 自适应学习
│   └── scheduler.py            # 三引擎调度器
│
├── api/
│   ├── active.py               # 【新增】主动引擎API
│   ├── push_messages.py        # 【新增】普通消息持久化API
│   └── notifications.py        # 【新增】系统通知API
│
├── db/
│   ├── models.py               # 【新增】Notification, PushMessageRecord
│   └── database.py             # 【新增】通知/消息操作方法
│
└── data/
    ├── feiyun.db               # 【新增】notifications + push_messages 表
    ├── active_config.json      # 【新增】主动引擎持久化配置
    └── active_messages/        # 【新增】SSE消息持久化
```

---

## 🔮 未来计划（更新于 2026-06-03）

| 优先级 | 项目 | 说明 |
|:-------|:-----|:------|
| 📝 中 | **工作空间 Agent 对接** | 让 AI 能创建和管理工作空间 |
| 📝 中 | **SSE 与 Chat 联动** | 主动推送消息插入对话 |
| 🔮 低 | **多模态** | 语音输入/输出 |

---

# 🆕 增量更新 2026-06-03（第二次）— 普通消息频道化 + 完整对话体验

> 本次更新将普通消息从通知卡片改造为完整对话频道，补齐流式回复、阈值计算、上下文加载等功能。

---

## ✅ 普通消息频道化

### 改造前 vs 改造后

| 项目 | 改造前 | 改造后 |
|:----|:------|:------|
| 消息展示 | 通知卡片（居中） | **MessageBubble 对话气泡**（和会话一致） |
| 输入栏 | 简陋 textarea | **ChatInput 组件**（含加号/文件/人格/模型/流式开关） |
| 回复方式 | 非流式（干等几秒） | **流式 SSE**（逐字输出） |
| 消息顺序 | 倒序（最新在上） | **正序**（最老在上，自动滚动） |
| 上下文 | 每次回复独立 | **连续上下文**（和会话一样） |
| 来源前缀 | `[记忆引擎] xxx` | **去掉前缀**，纯文本 |
| 思考内容 | 暴露在文本中 | **可折叠 `▶ 思考过程`** |
| 存储上限 | 无限制 | **240条 FIFO**，超了删最早 |

### 新增后端接口

| 方法 | 路径 | 说明 |
|:----|:-----|:------|
| `POST` | `/api/push/chat` | 非流式回复 |
| `POST` | `/api/push/chat/stream` | **流式回复**（SSE，推荐） |

### 固定会话频道

```python
# 普通消息使用固定频道 ID，不生成随机 UUID
PUSH_CHANNEL_ID = "__push_channel__"
```

- 会话列表自动过滤 `__push_channel__`，用户不可见
- 固定频道上下文持续保留，AI 记得之前的对话
- 超过 240 条时 FIFO 删除最早的一条

---

## ✅ 自适应阈值计算（完整链路）

### 之前（有 Bug）

```
AI推送 → 不记录
用户回复 → total_pushes++、total_replies++  ← 推送数=回复数，回应率永远100%
```

### 现在（已修复）

```python
# scheduler.py - push_ai_chat 增加推送统计
async def push_ai_chat(self, ...):
    await self.push_engine.push(msg)
    self.adaptive.record_push(replied=False)  # ← 新增：记录推送数
```

```
AI推送10次 → total_pushes=10
用户回复5次 → total_replies=5
回应率 = 50% ✅（之前100%）
```

### 完整链路

| 环节 | 实现 | 文件 |
|:----|:-----|:-----|
| AI推送时记录ID | `set_last_push_id(msg_id)` | `main.py` 回调 |
| AI推送时统计 | `adaptive.record_push(False)` | `scheduler.py` |
| 用户回复检测 | `if _last_push_msg_id:` | `push_messages.py` |
| 记录回复 | `record_user_reply()` → `record_push(True)` | `scheduler.py` |
| 只计第一次 | 记录后 `_last_push_msg_id = None` | `push_messages.py` |
| 阈值调整 | `get_session_adjusted_threshold()` | `disturbance.py` |

---

## ✅ 上下文历史加载（Bug 修复）

### 问题

`context.add_message()` 中，当会话已存在 DB 但缓存为空时，始终从空数组开始：

```python
self._cache[session_id] = []  # ← 忽略DB中的已有消息
```

导致普通消息频道中，AI 回复时看不到 SSE 推送的历史消息。

### 修复

```python
else:
    # 会话已存在，从 DB 加载历史消息
    conv = await self.db.get_conversation(session_id)
    if conv and conv.content:
        self._cache[session_id] = list(conv.content)
```

---

## ✅ 用户界面统一

| 组件 | 会话 | 💬 普通消息 | 🔔 系统通知 |
|:----|:----|:----------|:----------|
| 消息展示 | `MessageBubble` | `MessageBubble` ✅ | 通知卡片 |
| 输入栏 | `ChatInput` | `ChatInput` ✅ | 无 |
| 流式回复 | ✅ | ✅ | 只读 |
| 思考折叠 | ✅ | ✅ | — |
| 工具时间线 | ✅ | ✅ | — |
| 图标 | lucide | lucide ✅ | lucide ✅ |

---

## ✅ 主动引擎完善

| 功能 | 之前 | 现在 |
|:----|:----|:------|
| 免打扰时段 | 设置了但不生效 | ✅ `check_can_push()` 返回 False |
| 用户状态上报 | 前端未调用 | ✅ App.vue `setInterval` 30秒上报 |
| `db` 参数残留 | PushEngine 初始化传了 db 但未用 | ✅ 存储统一走回调 |
| 推送人格 | 硬编码"绯璃" + 截取前200字人格 | ✅ **使用完整人格设定**，切换人格实时生效 |
| 推送长度 | 固定 max_tokens=100，1-2句话 | ✅ **随机 100~200 tokens**，每次推送长度不同 |

### 主动推送生成逻辑

```python
# 调度器每次运行时实时读取当前人格
persona = self.persona_manager.get_active_persona()
persona_prompt = str(persona.get("prompt", ""))  # 完整人格，不截断

# 用完整人格 + 任务指令作为 system prompt
sys_text = persona_prompt + "

【当前任务】..."
```

切换人格后，下次推送自动使用新人格的风格，无需重启。

---

## 🔧 本次修复的问题汇总

| # | 问题 | 解决 |
|:--|:-----|:-----|
| 1 | 普通消息顺序颠倒 | API 返回正序（最老→最新） |
| 2 | 思考过程暴露 | 存储 `reasoning` 到消息元数据，MessageBubble 自动折叠 |
| 3 | 消息回复两次 | 去除流式完成后的 loadPushMessages |
| 4 | 发消息后看不到更新 | 本地先追加用户消息，异步 SSE 流式加载 AI 回复 |
| 5 | 会话高亮不取消 | `switchView` 离开会话时清空 `currentSessionId` |
| 6 | 推送消息前缀 | 去掉 `[记忆引擎]` 等来源前缀 |
| 7 | 上下文不完整 | `add_message` 从 DB 加载历史 |
| 8 | 阈值统计错误 | `push_ai_chat` 增加 `record_push(False)` |
| 9 | SSE 断线不重连 | 删除手动 `close()`，让浏览器自动重连 |
| 10 | `set_store_callback` 丢失 | 补回 `push.py` |
| 11 | 推送人格硬编码 | 改用完整人格设定，切换实时生效 |
| 12 | 推送长度太短 | 改为自适应长度（滑动平均 + 完成率估算 + 最多3次重试） |
| 13 | 消息被截断半句话 | 完成率估算补全，重试直到完整 |
| 14 | 会话切换消息闪烁 | 添加 `messagesCache` 缓存（上限20个会话） |
| 15 | 普通消息页面每次进入闪烁 | 添加 `pushMessagesCache` 缓存 |

---

## ✅ 消息缓存机制

### 为什么要加缓存

每次切换会话/普通消息时，前端会重新请求后端并处理消息（合并思考过程、工具调用等），导致：
- 页面闪烁（消息列表被替换）
- 处理结果不一致（思考过程和回复偶尔分离）

### 缓存策略

| 缓存 | 位置 | 触发时机 | 清除时机 | 上限 |
|:----|:----|:--------|:--------|:----|
| `messagesCache` | `useChat.js` | 首次加载会话消息 | 发新消息/删会话 | 20个 |
| `pushMessagesCache` | `useChat.js` | 首次加载普通消息 | SSE新推送/重进入 | 1个 |

### 自适应输出长度算法

主动推送的 AI 回复长度不再固定，而是根据历史表现动态调整：

```
基准值 = 滑动窗口平均（最近10次完整输出的 tokens）
  ↓
第1次生成 → 被截断？
  ├── 是 → 完成率估算补全长度 → 第2次重试
  │         "主人记得休" 完成率89%
  │         230/89% ≈ 258 → 用260重试
  │
  └── 否 → 记录到滑动窗口 ✓
           连续3次完整 → 下调10
           被截断 → 上调20
```

| 参数 | 值 | 说明 |
|:----|:---|:-----|
| 初始 | 230 | 宽裕起点 |
| 最低 | 80 | 安全下限 |
| 最高 | 500 | 安全上限 |
| 重试上限 | 2次（共3次） | 省API |
| 滑动窗口 | 10条 | 避免偶然波动 |
| 上调/下调 | +20 / -10 | AIMD 风格 |

---

## 🏗️ 更新后目录结构

```
F:\FeiyunMY-Bot\
│
├── api/
│   └── push_messages.py     # 【重写】普通消息频道 API（CRUD + 流式 + FIFO + 阈值）
│
├── agent/
│   └── context.py           # 【修复】add_message 从 DB 加载历史
│
├── active_engine/
│   ├── scheduler.py         # 【修复】push_ai_chat 记录推送统计 + 免打扰时段生效
│   └── push.py              # 【修复】set_store_callback + 存储走回调
│
├── db/
│   ├── models.py            # 新增 PushMessageRecord、Notification 模型
│   └── database.py          # 新增通知/消息操作方法 + 修复 import time
│
└── data/
    ├── feiyun.db            # 新增 notifications + push_messages 表
    └── active_config.json   # 主动引擎持久化配置

webui/src/
├── components/chat/
│   ├── ChatPage.vue         # 三层视图切换 + 流式推送回复
│   ├── PushPanel.vue        # 重写：对话气泡 + ChatInput 复用 + 通知卡片双模式
│   ├── SessionSidebar.vue   # 过滤 __push_channel__ + lucide 图标
│   └── MessageBubble.vue    # 工具步骤时间线 + 结果截断
├── composables/
│   └── useChat.js           # SSE 常驻 + pushMessages 管理 + 通知加载
└── App.vue                  # 全局 SSE 连接 + 用户状态上报
```

---

> 更新文档由亚托莉 (Atri) 整理于 2026-06-03（第二次）
> 如有疑问，请查阅代码注释或运行测试


---

# 🆕 多 Agent 协同架构 + 主动引擎 开发记录（2026-06-02 ~ 2026-06-03）

> 基于 FeiyunMY-Bot 扩展，新增多 Agent 协同、工作空间管理、主动引擎等功能
> 开发周期：2026-06-02 ~ 2026-06-03

---

## 一、新增模块总览

```
F:\FeiyunMY-Bot\
│
├── workspace/                  # 【新增】工作空间系统
│   ├── __init__.py
│   ├── manager.py              # 工作空间 CRUD + 原子写入 + 状态恢复
│   └── router.py               # @ 路由解析
│
├── active_engine/              # 【新增】主动引擎
│   ├── __init__.py
│   ├── disturbance.py          # 打扰指数算法 + 自适应学习
│   ├── push.py                 # SSE 推送 + 消息持久化
│   └── scheduler.py            # 三引擎调度器（定时/记忆/监控）
│
├── agent/
│   └── config_manager.py       # 【新增】子 Agent 配置管理器
│
├── knowledge/
│   └── manager.py              # 【新增】知识库管理器
│
├── api/                        # 【新增】API 端口
│   ├── workspaces.py           # 工作空间管理（CRUD + 任务 + Agent）
│   ├── agents.py               # 子 Agent 配置管理
│   ├── active.py               # 主动引擎配置 + SSE + 用户状态
│   ├── knowledge.py            # 知识库管理 + 文档上传
│   └── notifications.py        # 通知历史查询
│
├── tools/
│   └── workspace_tools.py      # 【新增】工作空间工具（AI 可调用）
│
├── db/
│   ├── models.py               # 【修改】新增 Notification 表
│   └── database.py             # 【修改】新增通知 CRUD
│
└── data/
    ├── workspaces/              # 工作空间持久化目录
    ├── active_messages/         # 推送消息持久化
    ├── active_params.json       # 自适应学习参数
    └── knowledge_bases/         # 知识库文档
```

---

## 二、核心功能说明

### 2.1 多 Agent 协同架构

**架构图**：
```
用户 ←→ 🧠 主脑（绯璃）
            │ @code / @design / @test
            ▼
      🤖 Agent 池（各自独立人格/记忆/知识库/模型）
            │
            ▼
      📋 工作空间（持久化 + 断电恢复）
```

**交互规则**：
- 用户直接发消息 → 主脑（不需要 @）
- 用户 @code → 路由到 code_agent
- Agent @主脑 → 汇报/审核
- Agent 间互相 @ → 多边形网状协作
- @ 仅在消息开头生效（避免邮箱误判）

### 2.2 工作空间系统

| 功能 | 说明 |
|:----|:------|
| CRUD | 创建/查看/更新/删除工作空间 |
| 原子写入 | .tmp + os.replace，断电不坏文件 |
| 状态恢复 | 重启时 active→paused，通知用户确认 |
| 任务管理 | DAG 依赖，按顺序派发 |
| Token 跟踪 | 每调用一次工具 +500 token 估算 |
| 文件目录 | data/workspaces/{id}/output/ |
| 权限沙箱 | file_ops 限定只能访问所属工作空间 |

**API 端口**：
```
GET    /api/workspaces              # 列表
POST   /api/workspaces              # 创建
GET    /api/workspaces/{id}         # 详情
PUT    /api/workspaces/{id}         # 更新
DELETE /api/workspaces/{id}         # 删除
GET    /api/workspaces/{id}/stats   # 统计
GET    /api/workspaces/{id}/tasks   # 任务列表
POST   /api/workspaces/{id}/tasks   # 添加任务
PUT    /api/workspaces/{id}/tasks/{task_id}  # 更新任务
GET    /api/workspaces/{id}/agents  # Agent 状态
POST   /api/workspaces/{id}/agents  # 添加 Agent
PUT    /api/workspaces/{id}/agents/{name}   # 更新 Agent
GET    /api/workspaces/{id}/logs    # 对话日志（支持 ?agent=code）
GET    /api/workspaces/{id}/files   # 输出文件列表
```

### 2.3 子 Agent 配置管理

| 功能 | 说明 |
|:----|:------|
| CRUD | 创建/查看/更新/删除 Agent 配置 |
| 重名检测 | 不能和主脑重名，不能和已有 Agent 重名 |
| 独立配置 | 每个 Agent 可选模型/人格/知识库/API Key/工具列表 |
| 前端下拉 | GET /api/agents/names 供下拉选择 |

**API 端口**：
```
GET    /api/agents              # 列表
POST   /api/agents              # 创建（含重名检测）
GET    /api/agents/{id}         # 详情
PUT    /api/agents/{id}         # 更新
DELETE /api/agents/{id}         # 删除
GET    /api/agents/names        # 名称列表（下拉选择用）
```

### 2.4 主动引擎

**三引擎驱动**：

| 引擎 | 周期 | 功能 |
|:----|:----:|:------|
| ⏰ 定时 | 触发式 | 早安(8:00)、晚安(22:00)问候 |
| 🧠 记忆 | 5分钟 | 扫描记忆，生成关心的话 |
| 📊 监控 | 30秒 | Token 提醒(每20万)、Agent 完成通知 |

**打扰指数算法**：
```
打扰指数 = (输入分×0.35 + 负载分×0.3 + 焦点分×0.35) × 时段权重 + 情感提升
```

**话痨模式**：
| 档位 | 触发门槛 | 说明 |
|:----:|:--------:|:------|
| 🗣️ 高 | ≥ 0.3 | 想有人陪 |
| 🙆 中 | ≥ 0.5 | 默认 |
| 🤫 低 | ≥ 0.7 | 专注工作 |
| 🔇 关 | — | 仅紧急推送 |

**自适应学习**：
- 记录每次主动推送的回应率
- 关机时慢速融合保存：新阈值 = 旧×0.7 + 学习结果×0.3
- 冷却机制：每次 AI 主动聊天后至少间隔 15 分钟

### 2.5 SSE 推送

```
消息类型：
├── system_event  → target: "notification" → 网页通知
├── active_push   → target: "session"      → 插入会话
└── agent_report  → target: "notification" → 网页通知
```

**API 端口**：
```
GET  /api/events                # SSE 长连接
GET  /api/active/messages       # 断连补推
POST /api/user/status           # 用户状态上报
GET  /api/active/config         # 获取配置
PUT  /api/active/config         # 更新配置
GET  /api/active/stats          # 推送统计
GET  /api/notifications         # 通知历史查询
```

### 2.6 知识库管理

| API | 说明 |
|:----|:------|
| `GET/POST /api/knowledge_bases` | 列表/创建 |
| `GET/PUT/DELETE /api/knowledge_bases/{id}` | 详情/更新/删除 |
| `POST /api/knowledge_bases/{id}/upload` | 上传文档 |
| `DELETE /api/knowledge_bases/{id}/documents/{doc_id}` | 删除文档 |
| `GET /api/knowledge_bases/{id}/search?keyword=xxx` | 搜索 |

---

## 三、关键设计决策

### 3.1 @ 路由规则
- 仅消息开头 @ 才算路由，避免邮箱误判
- @主脑 → 路由到主脑，@code → 路由到 code_agent

### 3.2 循环对话防护
```
Agent间@超过6轮 → 主脑介入尝试3次 → 仍无法解决 → 推给用户拍板
```

### 3.3 数据分层
| 层 | 技术 | 存什么 |
|:--|:-----|:-------|
| 对话上下文 | SQLite | 聊天记录、会话管理 |
| 长期记忆 | ChromaDB | 向量化记忆、情感 |
| 通知历史 | SQLite | 系统通知（保留50条） |
| 工作空间 | JSON文件 | 项目状态（原子写入） |

### 3.4 检索优先级
长期记忆 > 知识库（能靠经验解决就不查字典）

### 3.5 服务熔断
- 主脑 API 挂 → 降级为本地回复
- 子 Agent API 挂 → 工作空间标记 paused，安静等待

---

## 四、边界情况处理

| 问题 | 方案 |
|:----|:-----|
| 电脑断电重启 | 工作空间标记 paused，主动通知用户确认 |
| SSE 断连 | 消息持久化到磁盘，前端拉取补推 |
| API 费用失控 | 每文件 @主脑检查 + 每20万 token 软提醒 |
| AI 循环对话 | 三层漏斗（6轮→主脑3次→用户拍板） |
| Agent 冲突 | 主脑仲裁，拿不准再问用户 |
| ChromaDB 压力 | 懒加载 + 引用计数 + 闲置卸载 |
| 用户状态感知 | 打扰指数算法 + 话痨模式 + 自适应学习 |

---

## 五、技术栈

| 技术 | 用途 |
|:----|:------|
| Python 3.13 | 运行环境 |
| FastAPI | Web 框架 |
| SQLite (aiosqlite + SQLModel) | 对话/通知持久化 |
| ChromaDB | 长期记忆向量数据库 |
| SSE (Server-Sent Events) | 主动推送 |
| DeepSeek API | LLM 推理 |

---

## 六、开发路线图（已完成的 Phase）

| Phase | 内容 | 状态 |
|:----:|:------|:----:|
| 1 | 🗂️ 工作空间系统：CRUD + 持久化 + 状态恢复 | ✅ |
| 2 | 🤖 Agent 配置管理：CRUD + 重名检测 | ✅ |
| 3 | 🔀 @ 路由集成 + 文件权限沙箱 | ✅ |
| 4 | 🔔 主动引擎：三引擎 + SSE + 打扰指数 | ✅ |
| 5 | 📚 知识库管理：文档上传 + 搜索 | ✅ |
| 6 | 🧪 集成测试 + 边界修复 | ✅ |

---

> 文档更新：亚托莉 (Atri)
> 2026-06-03

---

# 🆕 增量更新 2026-06-04 — 普通消息存储分离修复（23项问题全面修复）

> 本次修复的核心是**普通消息存储分离**：将普通消息从 `conversations` 表迁移到独立的 `push_messages` 表，彻底解决存储冲突、数据重复、消息丢失等 23 项问题。
>
> **主动引擎核心架构完全不受影响**（调度器、打扰指数、自适应学习、SSE推送均未改动）。

---

## 背景：存储混用的历史包袱

普通消息频道（AI 主动推送 + 用户回复）原本存在 `conversations` 表中，与 AI 对话上下文共用同一张表、同一条记录（`__push_channel__` 会话）。这导致：

```
push_chat_stream:
  ① add_to_push_channel("user", msg)    → conversations 表
  ② runner.run_stream(msg)
       → context.add_message("user", msg)    → conversations 表 ← 重复！
       → context.add_message("assistant", reply) → conversations 表
  ③ add_to_push_channel("assistant", reply) → conversations 表
```

**用户消息被存了两次**，且展示用与上下文用相互耦合，引发连锁问题。

---

## ✅ 核心修复：存储分离

### 旧架构（混乱）

```
普通消息 ←→ conversations 表（展示 + 上下文混在一起）
               ↑ 两路写入，互相覆盖
```

### 新架构（分离）

```
┌─ 主动引擎推送 ─────────────────────────────┐
│  PushEngine.push()                          │
│    └─ 回调 _on_push_message()               │
│         ├─ push_messages 表 (展示用) ✅      │
│         └─ context.add_message()            │
│              └─ conversations 表 (上下文用) ✅│
└─────────────────────────────────────────────┘

┌─ 用户回复 ──────────────────────────────────┐
│  push_chat_stream / push_chat                │
│    ├─ add_to_push_channel("user")            │
│    │    └─ push_messages 表 (展示用) ✅       │
│    └─ runner.run_stream()                    │
│         └─ context.add_message()             │
│              └─ conversations 表 (上下文用) ✅ │
└─────────────────────────────────────────────┘
```

**两条路互不干扰，没有重复，没有冲突。**

---

## ✅ 具体改动

### 文件改动清单

| 文件 | 改动 |
|:-----|:-----|
| `db/models.py` | `PushMessageRecord` 添加 `role` 字段(user/assistant)；`content` 改为 `Text` 无长度限制；同样修复 `Notification.content` |
| `db/database.py` | `add_push_message()` 支持 `role` 参数；`list_push_messages()` 改为正序（最老在前，兼容前端） |
| `api/push_messages.py` | **完全重写**：`add_to_push_channel` 写入 `push_messages` 表（不再动 `conversations`）；`get_push_channel_messages` 读取 `push_messages` 表；修复流式异常时保存已收内容；废弃端点 `POST /push/messages` 已删除（原代码带 `msg_id` 未定义 Bug） |
| `main.py` | 回调 `_on_push_message` **同时**存 `push_messages` 表（展示）+ `context.add_message()`（上下文）；删除废弃的 `ensure_push_channel()` |
| `webui/.../useChat.js` | SSE 推送改为增量追加（不再清缓存）；`switchView('push')` 优先用缓存；归一化 `push_messages` 表返回格式（`created_at` → `timestamp`）；同步更新缓存 |

### 数据模型变更

```python
class PushMessageRecord(SQLModel, table=True):
    """普通消息记录 - 存储普通消息频道中的所有消息（用户/AI/主动推送）"""
    __tablename__ = "push_messages"

    id: str = Field(primary_key=True, max_length=32)
    role: str = Field(max_length=16, default="assistant")  # user / assistant
    content: str = Field(sa_column=Column(Text, nullable=False))       # 无长度限制
    msg_type: str = Field(max_length=32)       # active_push / chat_reply / system_event
    priority: str = Field(max_length=16)       # urgent / important / normal / low
    source: str = Field(max_length=64, default="")  # "记忆引擎" / "定时问候" 等
    created_at: float = Field(default=0)
```

---

## ✅ 修复的 23 项问题

### 数据一致性问题（5项）

| # | 问题 | 根因 | 修复 |
|:--|:-----|:-----|:-----|
| 1 | 用户消息存两次 | `add_to_push_channel` + `context.add_message` 都写 `conversations` 表 | 存储分离后各自写各自的表 |
| 2 | 缓存与DB不一致 | `trim_push_channel` 删了 DB 但 `context._cache` 没更新 | 废弃 `trim_push_channel`，统一走 `push_messages` 表 |
| 3 | 流式断连丢回复 | 异常时没执行 `add_to_push_channel` | `except` 分支保存已收到的内容 |
| 4 | 三路数据源冲突 | SSE + 历史加载 + 本地追加同时操作 `pushMessages` | 前端缓存只增不减，统一归一化 |
| 5 | 缓存清空丢本地消息 | `switchView` / SSE 反复清除 `pushMessagesCache` | 改为增量追加，切视图优先用缓存 |

### 代码 Bug（2项）

| # | 问题 | 修复 |
|:--|:-----|:-----|
| 6 | `POST /push/messages` 的 `msg_id` 未定义 → 500 | 废弃端点已删除 |
| 7 | 注释写"100条"实际 240 条 | 已清理 |

### 功能缺失（3项）

| # | 问题 | 修复 |
|:--|:-----|:-----|
| 8 | 消息来源信息丢失 | `add_to_push_channel` 支持 `source`、`priority`、`msg_type` 元数据 |
| 9 | 主动推送 vs 用户回复无法区分 | 前端 `type` 字段：`active_push` / `chat_reply` |
| 10 | `PushMessageRecord` 表废弃 | 正式启用，替代 `conversations` 表做展示存储 |

### 架构问题（7项）

| # | 问题 | 修复 |
|:--|:-----|:-----|
| 11 | 存储混用导致消息重复 | 存储分离后彻底解决 |
| 12 | `add_to_push_channel` 直接写库绕过 `context` 缓存 | 回调同时写 `push_messages` 表 + `context.add_message()` |
| 13 | 主动推送消息不进上下文 | `_on_push_message` 新增 `context.add_message()`，AI 回复时能读到主动推送 |
| 14 | 异常时用户消息已存但 AI 回复没存 | 流式异常分支保存已收内容 |
| 15 | 前端无消息去重 | 全局 `id` 字段 + 增量追加 |
| 16 | 后端排序与前端期望不一致 | `list_push_messages` 改为正序（最老在先） |
| 17 | 缓存策略反复清空 | 增量追加 + 优先用缓存 |

### 小问题（3项）

| # | 问题 | 修复 |
|:--|:-----|:-----|
| 18 | `Notification.content` 最长 1000 字可能截断 | 改为 `Text` 无长度限制 |
| 19 | `PushMessageRecord.content` 最长 1000 字 | 改为 `Text` 无长度限制 |
| 20 | SSE 推送无去重 | 前端按 `id` 去重 |

---

## ✅ 仪表盘首页修复（HomePanel）

### 修复的 6 项小问题

| # | 问题 | 修复 |
|:--|:-----|:------|
| 1 | 系统状态刷新间隔 2 秒太频繁 | 改为 10 秒 |
| 2 | 记忆模式永远显示 "Simple" | 改为根据 `cfg.memory.enabled` 推导：true→MemoriaDB，false→Simple |
| 3 | psutil 未安装时全显示 0%（无提示） | 添加 "需安装 psutil" 提示文字 |
| 4 | CPU 进度条全蓝，不看数字不知道高低 | 按使用率变色：<50% 蓝色，50~80% 黄色，>80% 红色，数字颜色同步变化 |
| 5 | 最近对话不能点击跳转 | 点击后通过 CustomEvent 跳转到 Chat 页面并自动选中该会话 |
| 6 | 页面加载时无 loading 状态 | 添加加载中动画，数据回来后显示内容 |

---

## ✅ 人格管理页面修复（PersonaPanel）

### 修复的 3 项问题

| # | 问题 | 修复 |
|:--|:-----|:------|
| 1 | 关闭弹窗后表单没重置 | `watch(showCreateModal)` 监听关闭，延迟 200ms 后清空表单 + 清除编辑状态 |
| 2 | 编辑时加载详情失败静默无提示 | `catch` 中改为 `showToast?.('加载人格详情失败，部分数据可能不完整', 'warning')` |
| 3 | 删除使用中的人格没有警告 | `handleDelete` 新增 `isActive` 参数，正在使用中的人物弹出 toast 提醒"请先切换再删除" |

---

## ✅ 普通配置页面修复（ConfigPanel - config-general）

### 修复的 4 项问题

| # | 问题 | 修复 |
|:--|:-----|:------|
| 1 | 保存按钮在"压缩配置"区块内，UI误导 | 移出压缩区块，放在外层独立的按钮区，标题改为"保存配置" |
| 2 | 先切提供商再保存配置，两步 API 可能状态不一致 | 改为**先保存配置到 config.yaml**，成功后再切提供商。配置保存失败时不会切提供商 |
| 3 | `syncSelectedModel` 在 `loadConfig` 和 `loadProviders` 中各调一次，第一次无效 | 去掉 `loadConfig` 中的调用，只在 `loadProviders` 中执行一次 |
| 4 | 压缩关闭后选项还显示着 | 关闭时显示提示文字"上下文压缩已关闭，AI 对话将保留全部历史记录。" |

---

## ✅ 模型配置（多提供商）修复（ConfigPanel - config-model + 后端 admin.py）

### 修复的 9 项问题

| # | 问题 | 修复 |
|:--|:-----|:------|
| **前端** `testModel` 假测试 | 1秒 setTimeout 直接标可用 | 改为实际调用 `providerApi.test()` 携带模型名测试，成功标 available，失败标 unknown 并显示错误 |
| **前端** `testProviderConnection` 永远成功 | 不 check 结果直接弹"完成" | 改为检查 `result.status === "ok"` 后弹成功/失败 |
| **前端** 删除提供商无确认 | 点删除直接没了 | 添加 `ConfirmDialog` 弹窗确认，用户确认后才删除 |
| **前端** API Key 精确匹配 base_url | 带 `/v1` 或不带匹配不上 | 改为先精确匹配，再去掉 `/v1` 后匹配，再取第一个启用的——三重兜底 |
| **前端** 获取模型错误被吞 | `result.models` 为空时不显示具体错误 | 改为先检查 `result.status === "fail"`，有错误直接 toast 显示后端消息 |
| **前端** 接口类型下拉纯装饰 | 选了 type 但无任何实际作用 | 前后端均不做特殊处理，属于 UI 预留（代码中加注释说明） |
| **后端** URL 拼写太死板 | 硬拼 `/v1/chat/completions` 和 `/v1/models` | 统一做 URL 归一化：去掉末尾的 `/v1` 再拼，兼容各种格式 |
| **后端** `/v1/models` 404 无提示 | DeepSeek 等没有此接口时返回空列表，用户不知道为什么 | 失败时返回 `"该 API 可能不支持 /v1/models 接口，请手动添加模型"` |
| **后端** `save_providers` 无校验 | 前端传空数组就清空所有提供商 | 加 `isinstance(providers, list)` 校验，非法数据返回 400 |

---

## 修复统计（截至 2026-06-04）

| 批次 | 修复项数 | 累计 |
|:-----|:--------:|:----:|
| 普通消息频道 | 23项 | 23 |
| 仪表盘首页 | 6项 | 29 |
| 人格管理 | 3项 | 32 |
| 普通配置 | 4项 | 36 |
| 系统配置（主动引擎） | 3项 | 39 |
| **模型配置（多提供商）** | **9项** | **48** |
| **工具配置** | **6项** | **54** |
| **数据统计页面** | **3项** | **57** |
| **工作空间页面** | **4项** | **61** |

---

## ✅ 数据统计页面修复（StatisticsPanel）

### 修复的 3 项问题

| # | 问题 | 修复 |
|:--|:-----|:------|
| 1 | 刷新频率 2 秒太频繁 | 改为 10 秒 |
| 2 | psutil 未安装时静默显示 0% | 底部添加灰色提示"需安装 psutil 以获取准确数据" |
| 3 | 进度条全蓝/全青/全黄，看不出高低 | 按使用率动态变色（蓝→黄→红），数字颜色同步 |
| 4 | 无加载状态，直接显示空数据 | 添加转圈 loading，数据回来后展示 |
| 5 | 统计和系统资源串行加载 | 改为 `Promise.all` 并发请求 |

## ✅ 工作空间页面修复（WorkspacePanel）

### 修复的 4 项问题

| # | 问题 | 修复 |
|:--|:-----|:------|
| 1 | 多处 `console.log` 调试输出残留 | 全部删除，正常错误走 `console.error` |
| 2 | 任务状态下拉乐观更新无回滚 | 保存旧状态，后端失败时 `t.status = oldStatus` 回滚 |
| 3 | 添加任务弹窗关闭后表单不重置 | `watch(showTaskModal)` 监听关闭时重置 `taskForm` |
| 4 | 删除确认中无用的 `res.text()` 读取 | 去掉无用代码，删除逻辑更清晰 |

---

## ✅ 主动引擎核心完全未改动

```
active_engine/
├── scheduler.py          ← 三引擎调度逻辑：未动
│   ├─ _check_timer_engine()    ← 定时问候
│   ├─ _check_memory_engine()   ← 记忆扫描 + LLM生成
│   └─ _check_monitor_engine()  ← Token/Agent监控
│
├── disturbance.py        ← 打扰指数算法：未动
│   ├─ calculate_disturbance_index()  ← 算法本身
│   └─ AdaptiveLearner               ← 自适应学习
│
├── push.py               ← SSE推送引擎：未动
│   ├─ PushMessage、PushEngine
│   └─ sse_generator()
```

唯一改动是 `main.py` 中的回调 `_on_push_message`——**只改了消息存到哪，不改谁触发、何时触发**。

---

## ✅ 工具配置修复（ConfigPanel - config-tools + config-shell）

### 修复的 6 项问题

| # | 问题 | 修复 |
|:--|:-----|:------|
| 1 | `file_ops` 的"全盘访问"Toggle 改了不保存 | 添加 `@update:modelValue="saveFileOpsAccess"`，变更时自动调 `configApi.update` 保存，失败回滚 |
| 2 | `config-shell` 独立页面的"启用 Shell 执行"不保存 | 改为绑定 `shell_whitelist.enabled` + `saveShellEnabled` 函数，保存到后端 |
| 3 | `execute` 展开区写了两份（第二份是死代码） | 删除重复的 `v-else-if="tool.key === 'execute'"` 死分支 |
| 4 | `handleToolToggle` 全量保存冗余数据 | 分离 `file_ops` 的开关和全盘访问逻辑，各自走独立的保存路径 |
| 5 | `config-shell` 页面列表绑定旧字段 | 从 `config.shell_whitelist` 直接遍历改为用 `shellWhitelistCommands` 计算属性（兼容数组/对象两种格式） |
| 6 | execute 工具提示不完整 | 提示改为 "⚠️ 仅白名单内的命令可执行。Python 代码执行默认启用沙箱。" |

---

## 📊 改动量统计

| 文件 | 新增 | 删除 | 净变更 |
|:-----|:----:|:----:|:------:|
| `db/models.py` | 3行 | 2行 | +1 |
| `db/database.py` | 1行 | 1行 | 0 |
| `api/push_messages.py` | 120行 | 90行 | +30 |
| `main.py` | 15行 | 10行 | +5 |
| `webui/.../useChat.js` | 20行 | 15行 | +5 |
| **合计** | **159行** | **118行** | **+41行** |

---

> 更新文档由亚托莉 (Atri) 整理于 2026-06-04
> 
> 核心原则：**展示用 ≠ 上下文用。两条路分开走，互不打架。**


---

# 🆕 增量更新 2026-06-05 — 现状评估 & 后续规划：工作空间 + 子 Agent 系统

> 本次更新对工作空间与子 Agent 系统进行完整现状评估，并制定分阶段开发计划。
> 评估人：亚托莉 (Atri)

---

## 一、现状评估

### 1.1 功能成熟度一览

经过代码审查，当前工作空间 + 子 Agent 系统的实际完成度远低于文档显示的进度：

```
功能模块                              完成度    说明
──────────────────────────────────────────────────────────
Agent 配置 CRUD（仪表盘子Agent页面）   ████████░░  80%  ✅ 可用，有 Bug
工作空间 CRUD（WorkspacePanel）        ████████░░  80%  ✅ 可用
任务管理（DAG 依赖）                   ██████░░░░  60%  ⚠️ 基础可用
@ 路由解析（router.py）                ███████░░░  70%  ⚠️ 逻辑完整但未接入执行
Agent 配置 ↔ 工作空间打通              ░░░░░░░░░░   0%  ❌ 关键缺口
子 Agent 实际驱动执行                  ░░░░░░░░░░   0%  ❌ 关键缺口
子 Agent 独立会话（分对话）            ░░░░░░░░░░   0%  ❌
前端分对话面板                         ░░░░░░░░░░   0%  ❌
主脑审核机制                           ░░░░░░░░░░   0%  ❌
```

### 1.2 三座孤岛：当前架构问题

```
┌──────────────────┐    ┌──────────────────┐    ┌───────────────┐
│  AgentConfig     │    │ WorkspaceManager │    │   @ Router    │
│  Manager         │    │                  │    │               │
│                  │    │                  │    │               │
│  存储:           │    │  存储:           │    │  职责:        │
│  data/agents/    │    │  data/workspaces/│    │  解析 @code   │
│  {id}.json       │    │  {id}/workspace  │    │               │
│                  │    │  .json           │    │               │
│  每个agent:      │    │                  │    │  问题:        │
│  ✅模型/人格     │    │  agent只有名字   │    │  不知道agent  │
│  ✅工具/温度     │    │  没有配置信息    │    │  用什么配置   │
│  ✅记忆开关      │    │                  │    │  来驱动       │
└────────┬─────────┘    └────────┬─────────┘    └───────┬───────┘
         │                      │                      │
         │    ❌ 无关联         │    ❌ 无引用         │
         └──────────────────────┴──────────────────────┘
```

### 1.3 具体断裂点

| # | 问题 | 影响 |
|:-:|:-----|:-----|
| 1 | 仪表盘创建 Agent 配置 → 工作空间完全不知道 | 配置了等于没配 |
| 2 | 工作空间创建时不能选已有 Agent，只能手写名字 | 配置信息丢失 |
| 3 | 工作空间中的 agent 只有 name，没有 model/persona/tools | 无法驱动 |
| 4 | @code 路由解析后，不知道用什么配置调用 LLM | 路由到空气 |
| 5 | 前端 SubAgentPanel 删除接口传 name 不传 agent_id → 404 | 功能不可用 |
| 6 | 工作空间 "子代理编排" 页面是空壳，显示"功能规划中" | UI 占位 |
| 7 | 子 Agent 没有独立会话，所有输出混在主对话中 | 无法并行 |

---

## 二、后续开发规划

### Phase 1 — 打通 Agent 配置 ↔ 工作空间（预估 1-2 天）

**目标**：让仪表盘创建的 Agent 配置能被工作空间识别和引用。

| 步骤 | 内容 | 涉及文件 |
|:----:|:-----|:---------|
| 1.1 | **后端：工作空间 Agent 携带 agent_ref_id** — 创建空间时支持传入 `agent_ref_id`，从 `AgentConfigManager` 中读取配置信息并缓存到 workspace 的 agent 对象中 | `workspace/manager.py` |
| 1.2 | **后端：WorkspaceManager.get_agent_config()** — 新增方法，通过 `agent_ref_id` 从 `AgentConfigManager` 获取 Agent 的完整配置（模型/人格/工具等） | `workspace/manager.py` |
| 1.3 | **后端：API 扩展** — 工作空间创建接口支持 `agent_ref_ids` 参数，返回时附带 Agent 配置摘要 | `api/workspaces.py` |
| 1.4 | **前端：工作空间创建页增加 Agent 选择器** — 从 `/api/agents/names` 拉取已配置的 Agent 列表，支持多选 | `WorkspacePanel.vue` |
| 1.5 | **前端：工作空间 Agent 状态页展示配置信息** — 显示每个 Agent 的模型/人格/工具标签 | `WorkspacePanel.vue` |
| 1.6 | **修复：SubAgentPanel 删除传参 Bug** — 删除接口传 `agent_id` 而非 `name` | `SubAgentPanel.vue` |

### Phase 2 — 子 Agent 执行引擎（预估 2-3 天）

**目标**：让 @code 真的能驱动一个子 Agent 开始工作，并在独立会话中输出。

| 步骤 | 内容 | 涉及文件 |
|:----:|:-----|:---------|
| 2.1 | **后端：子 Agent 执行器** — 新建 `agent/agent_runner.py`，接收 agent 配置 + 任务描述，使用该 Agent 的模型/人格/工具调用 LLM | `agent/agent_runner.py`（新建） |
| 2.2 | **后端：Agent 独立会话** — 每个子 Agent 在工作空间中拥有独立的 SQLite 会话（`agent_sessions`），上下文互相隔离 | `agent/context.py`、`workspace/manager.py` |
| 2.3 | **后端：@ 路由接入执行引擎** — `router.py`/主脑收到 @ 指令后，创建工作空间→创建 Agent 会话→调用 `agent_runner` 执行 | `workspace/router.py`、`agent/runner.py` |
| 2.4 | **后端：消息分发** — 子 Agent 的输出通过 SSE 推送到前端，标记所属的 Agent 和工作空间 | `active_engine/push.py` |
| 2.5 | **后端：主脑审核** — 子 Agent 完成后，结果汇总回主脑，主脑检查后向用户汇报 | `agent/runner.py` |

### Phase 3 — 前端分对话面板 & 实时展示（预估 2-3 天）

**目标**：用户能看到各子 Agent 独立工作，实时追踪进度。

| 步骤 | 内容 | 涉及文件 |
|:----:|:-----|:---------|
| 3.1 | **前端：工作空间分对话视图** — 在工作空间页面中，每个 Agent 拥有独立的对话区域，展示该 Agent 的思考过程和输出 | `WorkspacePanel.vue` |
| 3.2 | **前端：实时流展示** — 子 Agent 的流式输出实时推送到对应的对话区域，支持工具调用时间线 | `WorkspacePanel.vue`、`useChat.js` |
| 3.3 | **前端：@ 快捷入口** — 在 Chat 页面输入框中识别 @，弹出已配置的 Agent 列表供选择 | `ChatInput.vue` |
| 3.4 | **前端：Agent 状态指示器** — 左侧边栏显示各工作空间中 Agent 的运行状态（空闲/工作中/完成/失败） | `SessionSidebar.vue`、`WorkspacePanel.vue` |
| 3.5 | **前端：子代理编排页面填充** — 将工作空间中"子代理编排"空壳替换为工作流视图，展示 Agent 间依赖关系 | `WorkspacePanel.vue` |

### Phase 4 — 完善与优化（预估 1-2 天）

**目标**：补齐边界情况，提升稳定性和体验。

| 步骤 | 内容 | 涉及文件 |
|:----:|:-----|:---------|
| 4.1 | **循环对话防护** — Agent 间 @ 超过 6 轮 → 主脑介入 3 次 → 推给用户拍板 | `agent/agent_runner.py` |
| 4.2 | **服务熔断** — 子 Agent API 挂 → 工作空间标记 paused，安静等待，不影响主脑 | `workspace/manager.py` |
| 4.3 | **Token 费用控制** — 每 20 万 token 软提醒，主脑审核输出文件 | `workspace/manager.py` |
| 4.4 | **Agent 冲突仲裁** — 多个 Agent 输出矛盾时，主脑仲裁或询问用户 | `agent/agent_runner.py` |
| 4.5 | **工作空间清理** — 项目完成后可选保留或自动清理（含 ChromaDB 记忆清理） | `workspace/manager.py` |

---

## 三、路线图总览

```
Phase 1：打通配置          Phase 2：执行引擎          Phase 3：前端展示          Phase 4：完善优化
  1-2 天                    2-3 天                    2-3 天                    1-2 天

┌──────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ Agent 配置   │ ──▶  │ 子Agent      │ ──▶  │ 分对话面板   │ ──▶  │ 循环防护     │
│ ↔ 工作空间   │      │ 执行引擎     │      │ 实时流展示   │      │ 服务熔断     │
│              │      │              │      │              │      │              │
│ 总计 ~5项    │      │ 总计 ~5项    │      │ 总计 ~5项    │      │ 总计 ~5项    │
└──────────────┘      └──────────────┘      └──────────────┘      └──────────────┘
                                              │
                                              ▼
                                          ┌──────────────┐
                                          │ 子代理编排    │
                                          │ 页面替换     │
                                          │ 空壳→工作流  │
                                          └──────────────┘
```

### 预估总工时

| Phase | 内容 | 预估 | 状态 |
|:-----:|:-----|:----:|:----:|
| Phase 1 | 打通 Agent 配置 ↔ 工作空间 | 1-2 天 | ⏳ 待开始 |
| Phase 2 | 子 Agent 执行引擎 | 2-3 天 | ⏳ 待开始 |
| Phase 3 | 前端分对话面板 & 实时展示 | 2-3 天 | ⏳ 待开始 |
| Phase 4 | 完善与优化 | 1-2 天 | ⏳ 待开始 |
| **合计** | | **6-10 天** | |

---

## 四、已知 Bug 清单（待修复）

| # | Bug | 严重度 | 所属模块 | 修复时机 |
|:-:|:----|:------:|:---------|:--------|
| 1 | SubAgentPanel 删除接口传 `agent.name` 而非 `agent_id`，后端 404 | 🔴高 | 前端 | Phase 1 |
| 2 | 工作空间创建后 ID 字段前端做多次归一化（`workspace_id`→`id`），脆弱 | 🟡中 | 前后端 | Phase 1 |
| 3 | `workspace_tools.py` 的中文操作名映射不全（如"创建"→"create"正常，但"查看详情"无映射） | 🟢低 | 后端 | Phase 2 |
| 4 | Agent 配置的 `persona_id` 是名字而非 ID，删除人格后 Agent 配置变成脏数据 | 🟡中 | 后端 | Phase 4 |
| 5 | 前端 `WorkspacePanel.vue` 的 `statusClass` 中 `active` 映射了但工作空间没有 `active` 状态（只有 `active/paused/completed/failed`） | 🟢低 | 前端 | Phase 1 |

---

## 五、技术债务

| # | 债务 | 说明 | 建议 |
|:-:|:-----|:-----|:-----|
| 1 | 工作空间用 JSON 文件持久化，SQLite 的 `workspace` 表未使用 | 数据查詢不便，无法 SQL 查询 | Phase 4 考虑迁移到 SQLite |
| 2 | Agent 配置用 JSON 文件持久化，同上 | 同上 | Phase 4 统一存储 |
| 3 | `workspace_tools.py` 的工具定义（`WORKSPACE_DEFINITION` 和 `WORKSPACE_CN_DEFINITION`）保留了中文名版本但实际可能只用英文 | 冗余代码 | Phase 2 清理 |
| 4 | @ 路由只在消息开头生效，但前端没有 @ 提示/补全 | 用户不知道有哪些 Agent 可用 | Phase 3 添加前端提示 |

---

> 文档更新：亚托莉 (Atri)
> 2026-06-05
> 
> 核心认知：**当前工作空间 + 子 Agent 进度约 30%——骨架搭好了，血肉还没长。**


---

# 🆕 增量更新 2026-06-05（第二次）— 全模块完成度评估 & Provider 引擎现状分析

> 本次更新对项目所有核心模块进行实际代码审查，评估真实完成度，并补充多模型提供商引擎的后续规划。
> 评估人：亚托莉 (Atri)

---

## 一、全模块完成度评估（基于实际代码审查）

### 1.1 核心后端模块

| 模块 | 代码量 | 完成度 | 状态 |
|:-----|:------:|:------:|:-----|
| **FastAPI 入口** (main.py) | ~450行 | 100% | 稳定运行中 |
| **API 路由** (api/) | admin/chat/workspaces/agents/active/knowledge... | 80% | 28+端点可用 |
| **Agent 执行器** (agent/runner.py) | ~580行 | 80% | 流式+工具完备，但无子Agent支持 |
| **会话管理** (agent/context.py) | ~300行 | 90% | SQLite持久化 |
| **多提供商引擎** (provider/) | 3文件 ~200行 | 60% | 见下方详细分析 |
| **工具系统** (tools/) | 9工具模块 + registry | 90% | 注册+执行+超时完备 |
| **工作空间** (workspace/) | manager + router | 80% | CRUD完备，待打通 |
| **子 Agent 配置** (agent/config_manager.py) | ~200行 | 80% | CRUD完备，待打通 |

### 1.2 记忆 & 人格 & 主动引擎

| 模块 | 代码量 | 完成度 | 状态 |
|:-----|:------:|:------:|:-----|
| **MemoriaDB 长期记忆** | 5文件 ~800行 | 100% | BGE+ChromaDB+情感+遗忘 |
| **Simple 记忆** | ~100行 | 100% | 关键词匹配 |
| **记忆选择器** | ~80行 | 100% | 运行时切换模式 |
| **人格系统** | ~200行 | 100% | CRUD+热切换完整 |
| **主动引擎** | 4文件 ~600行 | 100% | 三引擎+SSE+打扰指数 |
| **知识库** | ~250行 | 80% | CRUD+文档上传+搜索 |

### 1.3 前端模块

| 模块 | 完成度 | 状态 |
|:-----|:------:|:-----|
| **首页仪表盘** (HomePanel.vue) | 80% | CPU/内存/磁盘统计 |
| **Chat 对话页** | 90% | 流式+工具时间线+思考折叠 |
| **会话管理** | 90% | 多会话+自动标题 |
| **人格管理** | 80% | CRUD+切换 |
| **配置管理** | 80% | 普通/模型/工具/系统配置 |
| **子 Agent 配置** | 60% | 有Bug(删除传参) |
| **工作空间管理** | 60% | 子代理编排空壳 |
| **知识库管理** | 60% | 基础UI可用 |
| **数据统计** | 60% | 需psutil |
| **平台日志** | 60% | 基础展示 |

---

## 二、多模型提供商引擎详细分析

### 2.1 架构现状

config.yaml 中可以存多个提供商（providers数组），但运行时 main.py 只创建了一个 OpenAIProvider 实例。所有对话、总结、压缩都走同一个 provider。

### 2.2 能力对照表

| 能力 | 当前状态 | 说明 |
|:-----|:--------:|:-----|
| 配置存储多个提供商 | 已支持 | config.yaml 的 providers 数组 |
| 运行时切换提供商 | 能用但不优雅 | 直接改现有 provider 的 api_key/base_url |
| 多 API Key 管理 | 已支持 | 每个提供商可独立配置 API Key |
| 多模型列表管理 | 已支持 | 前端 CRUD + 自动获取/手动添加 |
| 提供商连接测试 | 已支持 | POST /api/provider/test |
| 模型自动获取 | 已支持 | POST /api/provider/models |
| URL 归一化 | 已支持 | 自动处理 /v1 后缀 |
| **运行时多提供商并行** | **不支持** | 同一时刻只有1个 provider 实例 |
| **子 Agent 独立选模型** | **不支持** | model_id 字段没用上 |
| **非 OpenAI 格式支持** | **不支持** | 只有 OpenAIProvider |
| **Provider 管理器** | **不支持** | 无统一管理 |
| **多 API 并行调用** | **不支持** | 无法同时用多个模型 |
| **API Key 加密存储** | **不支持** | 明文存储 |

### 2.3 三句总结

> 配置层可以存多个提供商，但运行时只活了1个，没有并行管线。
>
> 子 Agent 配置里的 model_id 字段是个摆设——因为执行器永远是同一个 provider。
>
> 想接 Anthropic/Google 等非 OpenAI 格式，需要写新 Provider 实现+工厂模式。

---

## 三、更新后的完整开发路线图

```
Phase 之前的版本                    状态
────────────────────────────────────────
Phase 0: 核心框架 (API/Agent/Tools)  已完成
Phase 1: 工作空间 CRUD              已完成
Phase 2: Agent 配置管理              已完成
Phase 3: @ 路由集成                  已完成
Phase 4: 主动引擎                    已完成
Phase 5: 知识库管理                  已完成
Phase 6: 集成测试 + 边界修复         已完成
────────────────────────────────────────
累计完成度：约 65%（整体项目）
```

### 后续 Phase（更新版）

| Phase | 内容 | 预估 | 累计进度 |
|:-----:|:-----|:----:|:--------:|
| **Phase 7** | 打通 Agent 配置 -> 工作空间 | 1-2天 | 约70% |
| **Phase 8** | Provider 管理器 + 子 Agent 执行引擎 | 3-4天 | 约80% |
| **Phase 9** | 前端分对话面板 & 实时展示 | 2-3天 | 约88% |
| **Phase 10** | 完善优化 + 技术债务清理 | 2-3天 | 约95% |

### Phase 7 — 打通 Agent 配置 -> 工作空间（1-2天）

同上次规划，详见上方 2026-06-05 的 Phase 1。

| 步骤 | 内容 | 涉及文件 |
|:----:|:-----|:---------|
| 7.1 | 后端：工作空间 Agent 携带 agent_ref_id | workspace/manager.py |
| 7.2 | 后端：get_agent_config() 获取完整配置 | workspace/manager.py |
| 7.3 | 后端：API 扩展 agent_ref_ids 参数 | api/workspaces.py |
| 7.4 | 前端：工作空间创建页 Agent 选择器 | WorkspacePanel.vue |
| 7.5 | 前端：Agent 状态页展示配置信息 | WorkspacePanel.vue |
| 7.6 | 修复：SubAgentPanel 删除传参 Bug | SubAgentPanel.vue |

### Phase 8 — Provider 管理器 + 子 Agent 执行引擎（3-4天）

**目标**：让每个子 Agent 能用独立配置的模型运行，实现多 API 并行。

| 步骤 | 内容 | 涉及文件 |
|:----:|:-----|:---------|
| 8.1 | 新建 ProviderManager | provider/manager.py (新建) |
| 8.2 | Provider 抽象工厂 | provider/manager.py |
| 8.3 | 优化切换逻辑 | api/admin.py |
| 8.4 | AgentRunner 支持多 Provider | agent/runner.py |
| 8.5 | 子 Agent 执行器 | agent/agent_runner.py (新建) |
| 8.6 | Agent 独立会话 | agent/context.py |
| 8.7 | @ 路由接入执行引擎 | workspace/router.py |

```python
# ProviderManager 设计示意
class ProviderManager:
    def __init__(self):
        self._instances = {}  # provider_id -> instance
    
    def create_provider(self, config):
        if config["type"] == "openai":
            return OpenAIProvider(...)
        elif config["type"] == "anthropic":
            return AnthropicProvider(...)
    
    def get_provider(self, provider_id):
        """获取或创建 provider 实例"""
    
    def switch_active(self, provider_id):
        """切换活跃 provider"""
```

### Phase 9 — 前端分对话面板 & 实时展示（2-3天）

同上次规划，详见上方 2026-06-05 的 Phase 3。

### Phase 10 — 完善优化 + 技术债务清理（2-3天）

| 步骤 | 内容 | 涉及文件 |
|:----:|:-----|:---------|
| 10.1 | 循环对话防护 | agent/agent_runner.py |
| 10.2 | 服务熔断 | workspace/manager.py |
| 10.3 | Token 费用控制 | workspace/manager.py |
| 10.4 | 工作空间存储迁移 (JSON -> SQLite) | workspace/manager.py |
| 10.5 | Agent 配置存储迁移 (JSON -> SQLite) | agent/config_manager.py |
| 10.6 | API Key 加密存储 | 配置层 |

---

## 四、依赖关系图

```
Phase 7 (打通配置)
  |
  +---> Phase 8 (Provider管理器 + 执行引擎)
         |
         +---> 依赖：ProviderManager 管理多模型实例
         +---> 依赖：Agent 配置中的 model_id 真正生效
         +---> 输出：@code 能驱动子 Agent 用独立模型工作
                |
                +---> Phase 9 (前端展示)
                       |
                       +---> Phase 10 (完善优化)
```

---

> 文档更新：亚托莉 (Atri)
> 2026-06-05（第二次）


---

# 🆕 ⚠️ 重要 增量更新 2026-06-09 — 工具调用不显示 & AI不调工具问题修复

> 本次更新修复了两个问题：
> 1. 前端消息加载时工具调用信息丢失（`useChat.js`）
> 2. 上下文压缩摘要中残留过时工具结果导致AI不调工具（`runner.py`）

---

## ✅ 修复的问题

### 问题1：工具调用不显示（前端消息合并Bug）

**现象**：Chat页面中，初期能看到AI使用工具，到后面工具调用不显示了。

**根因**：`useChat.js` 的 `selectSession` 中，当最后一批工具消息没有匹配的 `assistant` 消息时，这些工具信息被**错误地合并到上一条 assistant 消息中**（张冠李戴），导致"消失"。

**修复**：改为创建一条独立的虚拟 `assistant` 消息来承载剩余的工具信息，避免误合并。

### 问题2：AI不调工具（上下文压缩摘要误导）

**现象**：多轮对话后AI不再调用工具。例如中午调时间工具看了时间，下午再问时AI仍回答"中午"，提醒后AI能准确说出时间但仍不调工具。

**根因**：`_compress_context` 的 `summarize` 模式将历史对话（含工具结果如"中午12:00"）压缩进 `system` 角色摘要，AI把摘要当**当前事实**遵守，导致认为"当前是中午"，不再调工具获取实时时间。

---

## ✅ 代码改动清单

### 改动1：`webui/src/composables/useChat.js`

**位置**：`selectSession` 函数末尾，消息合并循环后

**改前**：
```javascript
// 丢到上一条 assistant 消息里
if (pendingTools.length > 0) {
    for (let i = merged.length - 1; i >= 0; i--) {
        if (merged[i].role === 'assistant') {
            merged[i].tools_used.push(...pendingTools)
            break
        }
    }
}
```

**改后**：
```javascript
// 创建一条虚拟 assistant 消息来承载
if (pendingTools.length > 0) {
    merged.push({
        role: 'assistant',
        content: '',
        reasoning: pendingReasoning || '',
        tools_used: pendingTools,
        timestamp: Date.now() / 1000,
    })
}
```

---

### 改动2：`agent/runner.py` — 压缩提示词

**位置**：`DEFAULT_COMPRESS_PROMPT` 常量

**改前**：
```
"保留所有重要信息（用户偏好、需求、关键事实、重要结论）"
```

**改后**：
```
"如果使用了工具，只记录调用了哪些工具以及提取有价值的洞察，
**不要保留工具的原始输出值**"
```

**目的**：防止LLM在压缩摘要时把"中午12:00"等时效性数据当重要信息保留。

---

### 改动3：`agent/runner.py` — 保留近几轮对话

**位置**：`_compress_context` 方法，`summarize` 模式中

**改前**：所有旧对话全部压缩成一条摘要。

**改后**：保留最近 **~15%** 的对话原样不动，只压缩更早的部分。

```python
keep_ratio = 0.15
keep_count = max(1, int(len(non_system) * keep_ratio))
if keep_count < len(non_system):
    recent_kept = non_system[-keep_count:]
    to_summarize = non_system[:-keep_count]
```

---

### 改动4：`agent/runner.py` — 摘要角色格式

**位置**：`_compress_context` 返回格式

**改前**（system角色 → AI当事实遵守）：
```python
{"role": "system", "content": "【旧对话摘要】中午12点..."}
```

**改后**（user-assistant对 → AI当历史参考）：
```python
{"role": "user", "content": "我们之前对话的历史摘要：..."}
{"role": "assistant", "content": "已确认。"}
```

---

## 🔍 消息角色对比总结

| role | 权威性 | AI如何看待 | 典型用途 |
|:----|:------|:----------|:---------|
| **system** | 🔴 高 | 当作**规则/事实**严格遵守 | 人格设定、行为规则 |
| **user** | 🟡 中 | 用户输入，需要回应 | 用户的问题 |
| **assistant** | 🟢 低 | 当作**历史记录**参考 | AI自己的回复 |
| **tool** | 🟢 低 | 工具返回结果 | 工具返回值 |

---

## 🔮 后续规划

### 1. 消息管道重构（待定）

当前系统有两个重叠的截断机制（`_compress_context` + `truncate_messages`），且 `build_messages` 生成了6条system消息，容易在截断时丢失工具规则。

**参考 AstrBot 的设计**：
- 只保留 **1条system**（人格设定）
- 工具规则不放在system消息中，通过API的 `tools` 参数传递（永不丢失）
- 统一使用一个 **ContextManager** 管理压缩和截断
- 按 token 比例（82%）触发，而非固定轮次

**难度**：⭐⭐ 因为消息管道是地基，改动影响范围大，需要全模块回归验证。

### 2. 前端消息缓存优化（待定）

当前 `messagesCache` 在发送新消息时被清空，导致切换会话时重新加载。可考虑增量更新缓存，减少API请求。

### 3. 上下文压缩策略优化（待定）

当前 `compress_interval` 固定为20轮，可改为动态触发（按token比例），并参考AstrBot的 `LLMSummaryCompressor` 设计。

---

> 更新文档：亚托莉 (Atri)
> 2026-06-09


---

# 🆕 ⚠️ 重要 增量更新 2026-06-09（第二次）— 情感分析、对话总结、记忆系统问题修复

> 本次更新沿三条线排查并修复了记忆系统中情感分析崩溃、总结人格混淆、记忆角色矛盾等问题。

---

## ✅ 修复的问题

### 问题1：`emotion.py` 中 `def analyze()` 方法定义行丢失

**现象**：BGE语义模型不可用时（如模型加载失败），情感分析直接崩溃，导致整条记忆存不了。

**根因**：`emotion.py` 的 `analyze_semantic` 方法中，`except` 块调用了 `self.analyze(text)` 做降级，但 `def analyze()` 的定义行意外丢失。同时 `memoria/__init__.py` 中 BGE 不可用时也会调用 `self.emotion_analyzer.analyze()`，同样崩溃。

**修复**：在 `emotion.py` 第224行后补回 `def analyze(self, text: str) -> EmotionResult:` 方法定义。

**改动文件**：`memory/backends/memoria/emotion.py`（1行）

---

### 问题2：对话总结模板写死"AI"导致人格混淆

**现象**：记忆中的总结写的是"AI 推荐了..."，但实际人格是"亚托莉"。检索回来后 AI 看到角色和内容矛盾。

**根因**：`_SummaryPrompt.SYSTEM` 中要点2写死"提取 **AI** 回复"，示例也全是"用户..."格式，没有使用 `{persona_name}`。

**修复**：
- 模板中所有"AI"替换为 `{persona_name}`
- 示例改为 `{persona_name} 推荐了...` / `{persona_name} 给出了...`
- `_summarize_conversation` 中调用时用 `.format(persona_name=persona_name)` 传入当前人格名

**改动文件**：`agent/runner.py`（~15行）

---

### 问题3：记忆 role 全是 "assistant"，注入对话时角色矛盾

**现象**：存记忆时 role 写死 `"assistant"`，注入对话时 AI 看到 `[assistant] 用户查询了北京的天气`，角色和内容矛盾。

**修复**：
- 存记忆时 role 从 `"assistant"` 改为 `"memory"`（更中性，不混淆）
- 注入对话时去掉 `[role]` 前缀，改为 `  内容`（纯内容展示）

**改动文件**：`agent/runner.py`（2处）

---

### 问题4：对话总结提示词优化

**现象**：原提示词只要求"提取关键要点"，没有区分工具结果中的时效性信息，也没有明确检索目的。

**修复**：参考上下文压缩提示词风格重写，新增：
- **目标**：使后续检索时能准确回忆起核心信息
- **要求4**：如果用了工具，记录工具名和关键结果，**不要保留时效性数据**（如具体时间）
- 示例中加入了工具使用场景：`{persona_name} 用天气工具查到了北京的天气情况`

**改动文件**：`agent/runner.py`（`_SummaryPrompt.SYSTEM` 完全重写）

---

## 📋 改动文件清单

| 文件 | 改动 | 代码量 |
|:----|:-----|:------:|
| `memory/backends/memoria/emotion.py` | 补回 `def analyze()` | +1行 |
| `agent/runner.py` | 模板人格化 + 记忆role修正 + 提示词重写 | ~30行 |

---

## 🔮 待办

| # | 内容 | 优先级 | 备注 |
|:-:|:----|:------:|:-----|
| 1 | 对话总结prompt保留更多检索细节 | 🟡 | 主人说先不动 |
| 2 | 消息管道大重构（合并system消息、统一截断） | 🟠 | 地基级改动，需要规划 |
| 3 | 上下文压缩策略进一步优化 | 🟢 | 可参考AstrBot按token比例触发 |

---

# 🆕 ⚠️ 重要 增量更新 2026-06-09（第三次）— 记忆引擎检索问题分析

> 本次为分析记录，尚未修复。记忆系统为核心模块，需谨慎讨论修改方案。

---

## 🔍 问题：记忆引擎总是提取无关记忆

### 现象

每次对话时从长期记忆中提取的相关记忆，经常是与当前话题无关的内容。这些无关记忆还能长期保留，不会被清理。

---

## 🧬 完整问题链分析

### 环节1：存储时的评分 `importance.py`

```python
KEY_PATTERNS = {
    "地名": r"(?:在|去|来自|位于)...",
    # "北京" → 匹配 → 加分
}
```

一条`"用户查询了北京的天气"`的记忆：
- 匹配"地名"（北京）+0.35
- 匹配"时间"（天气相关）+0.15
- **综合得分：0.7**（算重要了）

但这条信息**过了今天就没用了**，却被标记为高重要性。

### 环节2：遗忘曲线 `ebbinghaus.py`

```
retention = 0.8 * e^(-衰减率 * 天数)

重要性0.7 → 衰减率低 → retention下降慢
情感中性  → 情感因子=0.85 → 额外减速
清理阈值0.3 → 永远不会被清理
```

没有区分**时效性信息**（天气、日期）和**持久性信息**（偏好、经历）。

### 环节3：检索时的排序

```python
# runner.py
related = self.memory.query(user_message, top_k=3)
memories = related if else recent
```

ChromaDB只算语义相似度，**不结合重要性/时效性加权**。语义上相似但不重要的记忆也被搜出来了。

### 环节4：注入对话

```python
# build_messages
for m in memories:
    ctx += f"  {m.get('content', '')}
"
messages.append({"role": "system", "content": ctx})
```

所有检索结果**无差别塞给AI**，没有做重要性过滤。

### 环节5：记忆引擎（主动推送）

```python
# scheduler.py _check_memory_engine
recent = self.memory.get_recent(n=5)
# 只用get_recent，没有语义检索
# 只按时间排序，没有重要性/情感加权
```

对比主对话用 `query()` 语义检索，记忆引擎只用 `get_recent()` 按时间取最新。

---

## 🎯 各环节待讨论的改进方向

| # | 环节 | 当前问题 | 可能的改法 |
|:-:|:----|:---------|:----------|
| 1 | **存储前评分** | 时效性信息被标为高重要性 | 评分器加"时效性惩罚"，时间相关的内容自动降分 |
| 2 | **遗忘曲线** | 不区分记忆类型 | 时效性信息初始retention设低，加速遗忘 |
| 3 | **检索排序** | 只看语义相似度 | 检索结果按`重要性×相关度`加权排序 |
| 4 | **注入过滤** | 无差别注入 | 加一层过滤，只注入重要性>阈值的 |
| 5 | **记忆引擎** | 只用get_recent | 改为语义query + 重要性加权 |

> ⚠️ 记忆系统为核心中的核心，改动需逐层讨论、谨慎实施。

---

## 🔗 模块联动关系图

记忆系统的三个核心模块并非独立，而是**环环相扣**：

```
情感分析（emotion.py）
  5类模板 → 偏"悲/惧" → emotion_intensity虚高
    ↓
重要性评分（importance.py）
  keyword硬编码 → 啥都高分
  emotion ×0.3加权 → 更高分
  → 啥都存进去（阈值0.3形同虚设）
    ↓
艾宾浩斯遗忘（ebbinghaus.py）
  importance高 → 衰减慢
  emotion_intensity高 → 衰减更慢
  → 无关记忆清不掉
```

### 待讨论的改动方案（逐层）

| 层级 | 模块 | 当前问题 | 方案方向 |
|:----:|:----|:---------|:---------|
| 1️⃣ | `emotion.py` | 5类模板太粗，偏负面 | 替换为 **GoEmotions 28类** 细粒度模板 |
| 2️⃣ | `importance.py` | keyword硬编码，什么都高分 | 语义评分为主(70%)+规则为辅(30%)，加**时效性降权** |
| 3️⃣ | `ebbinghaus.py` | 重要性/情感双高导致清理不掉 | 调低情感因子权重，加**记忆类型区分**（时效性 vs 持久性） |
| 4️⃣ | `__init__.py` add() | 检索无重要性加权 | 检索结果按 `重要性×相关度` 排序 |
| 5️⃣ | `runner.py` build_messages | 无差别注入 | 过滤低重要性记忆 |

> 方案已讨论，详细设计方案见下方。

---

## 📐 完整设计方案（讨论稿）

### 总体架构

```
输入：记忆文本 → BGE编码
    │
    ▼
第0层：去重检测 ← 新增
  ┌──────────────────────────────┐
  │ ChromaDB检索最相似记忆       │
  │ if 相似度 > 0.9:             │
  │   更新旧记录（内容+时间戳）   │
  │   mention_count += 1         │
  │   importance 微调加权        │
  │ else: 新建记录               │
  └──────────┬───────────────────┘
             │
             ▼
第1层：记忆类型识别 ← 新增
  ┌──────────────────────────────┐
  │ BGE语义模板匹配5种类型       │
  │ 偏好/事实/状态/事件/查询     │
  │ 字典法留作降级端口           │
  └──────────┬───────────────────┘
             │
             ▼
第2层：VAD细粒度情感分析 ← 重构
  ┌──────────────────────────────┐
  │ GoEmotions 28类情感          │
  │ VAD三维坐标（效价/唤醒/支配）│
  │ 从离散象限→连续坐标          │
  └──────────┬───────────────────┘
             │
             ▼
第3层：重要性计算 ← 重构
  ┌──────────────────────────────┐
  │ score = 类型基准×0.3         │
  │       + 语义分×0.4           │
  │       + VAD加权×0.2          │
  │       + 提及加权×0.1         │
  │                               │
  │ 查询/事件类：时效性打7折      │
  └──────────┬───────────────────┘
             │
             ▼
第4层：动态阈值准入 ← 重构
  ┌──────────────────────────────┐
  │ threshold = BASE(0.4)        │
  │           + VAD偏移(连续)    │
  │           + 类型偏移         │
  │           + 时间震荡         │
  │           + 年龄惩罚         │
  │                               │
  │ 震荡周期：会话内已运行时间    │
  │ 非绝对时间（防重启归零）      │
  │                               │
  │ if score >= threshold: 存     │
  │ elif 随机概率: 存（类人随机） │
  │ else: 丢弃                   │
  └──────────┬───────────────────┘
             │ 存进去了
             ▼
第5层：艾宾浩斯遗忘 ← 重构
  ┌──────────────────────────────┐
  │ retention = 0.8 × e^(-衰减)  │
  │                               │
  │ 衰减因子新增：                │
  │ • 类型衰减（查询2.0/偏好0.6） │
  │ • VAD情感衰减                │
  │ • 提及次数衰减               │
  └──────────────────────────────┘
```

---

### 第0层：去重检测

```python
def dedup(new_memory, existing_memories):
    similar = chroma_query(new_memory, top_k=1)
    
    if similar and similar["similarity"] > 0.9:
        old = similar["memory"]
        old["content"] = new_memory["content"]
        old["updated_at"] = time.time()
        old["mention_count"] += 1
        old["importance"] = min(1.0, old["importance"] + 0.02)
        return old, "updated"
    
    return new_memory, "created"
```

**存储结构**：
```json
{
    "id": "xxx",
    "content": "最新表述",
    "created_at": 1718000000,
    "updated_at": 1718100000,
    "mention_count": 3,
    "importance": 0.62
}
```
不保留历史时间戳列表，用计数代替。

---

### 第1层：记忆类型识别

```python
# BGE语义模板匹配，字典法留作降级端口
TYPE_TEMPLATES = {
    "偏好": ["这是用户的个人喜好或兴趣",
             "用户表达了对某事物的偏好"],
    "事实": ["这是关于用户的一个事实性信息",
             "用户陈述了一个客观事实"],
    "状态": ["这是用户当前的状态或感受",
             "用户正在经历某种状态"],
    "事件": ["这是用户经历或做过的事情",
             "这是已经发生的一个事件"],
    "查询": ["这是用户的一次信息查询或搜索",
             "这是用户临时性的查询需求"],
}

# 降级用字典端口
TYPE_KEYWORDS = {
    "偏好": ["喜欢", "爱", "讨厌", "不喜欢", "感兴趣"],
    "事实": ["住在", "是", "在", "有", "毕业于"],
    "状态": ["最近", "正在", "感觉", "觉得", "有点"],
    "事件": ["去了", "做了", "买了", "看了", "吃了"],
    "查询": ["查了", "问了", "搜了", "查一下", "想知道"],
}
```

---

### 第2层：VAD三维情感坐标

28类情绪映射到VAD空间：

```
"admiration":    [0.7, 0.3, 0.5],   钦佩
"amusement":     [0.6, 0.6, 0.4],   娱乐
"anger":         [-0.8, 0.7, 0.6],  愤怒
"annoyance":     [-0.5, 0.4, 0.3],  烦恼
"approval":      [0.5, 0.2, 0.3],   认可
"caring":        [0.6, 0.1, 0.2],   关怀
"confusion":     [-0.2, 0.3, -0.4], 困惑
"curiosity":     [0.3, 0.5, 0.1],   好奇
"desire":        [0.5, 0.6, 0.4],   渴望
"disappointment":[-0.6, -0.2, -0.4],失望
"disapproval":   [-0.5, 0.2, 0.2],  不赞同
"disgust":       [-0.7, 0.5, 0.3],  厌恶
"embarrassment": [-0.3, 0.4, -0.5], 尴尬
"excitement":    [0.7, 0.8, 0.5],   兴奋
"fear":          [-0.7, 0.8, -0.5], 恐惧
"gratitude":     [0.7, 0.3, 0.2],   感激
"grief":         [-0.8, -0.3, -0.5],悲痛
"joy":           [0.8, 0.6, 0.5],   快乐
"love":          [0.8, 0.5, 0.3],   爱
"nervousness":   [-0.4, 0.7, -0.4], 紧张
"neutral":       [0.0, 0.0, 0.0],   中性
"optimism":      [0.6, 0.4, 0.4],   乐观
"pride":         [0.6, 0.4, 0.6],   自豪
"realization":   [0.2, 0.5, 0.3],   领悟
"relief":        [0.5, -0.3, 0.3],  解脱
"remorse":       [-0.6, -0.1, -0.3],懊悔
"sadness":       [-0.6, -0.3, -0.4],悲伤
"surprise":      [0.2, 0.7, 0.1],   惊讶
```

---

### 第3层：重要性计算

```python
def calculate_importance(
    semantic_score: float,    # BGE语义重要度
    memory_type: str,        # 记忆类型
    vad: tuple,              # (v, a, d)
    mention_count: int,      # 提及次数
    rule_score: float = 0,   # 字典降级用
    bge_available: bool = True,
) -> float:
    
    type_base = {"偏好":0.7, "事实":0.6, "状态":0.5, "事件":0.4, "查询":0.2}
    base = type_base.get(memory_type, 0.4)
    
    v, a, d = vad
    vad_weight = (abs(v) * 0.4 + a * 0.3 + abs(d) * 0.3)
    mention_weight = 0.1 * math.log(mention_count + 1)
    
    if bge_available:
        score = base*0.3 + semantic_score*0.4 + vad_weight*0.2 + mention_weight*0.1
    else:
        score = base*0.4 + rule_score*0.4 + vad_weight*0.1 + mention_weight*0.1
    
    if memory_type in ("查询", "事件"):
        score *= 0.7
    
    return min(1.0, max(0.0, score))
```

---

### 第4层：动态阈值准入

```python
def dynamic_threshold(
    vad: tuple,
    memory_type: str,
    created_at: float,
    server_start_at: float,
) -> float:
    
    BASE = 0.4          # 基准值（从严，避免啥都存）
    AMPLITUDE = 0.15    # 震荡幅度
    PERIOD = 2 * math.pi / 3600  # 周期1小时
    
    # 日期驱动的随机相位（同一天一致，每天不同）
    day_seed = int(time.time() / 86400)
    START_PHASE = (day_seed * 0.618) % (2 * math.pi)
    
    v, a, d = vad
    
    # VAD连续偏移
    vad_offset = (-v * 0.08 - a * 0.06 - d * 0.04)
    
    # 类型偏移
    type_offset = {"偏好": -0.08, "事实": -0.04, "状态": 0.0,
                   "事件": 0.05, "查询": 0.10}.get(memory_type, 0.0)
    
    # 时间震荡（会话内运行时间 + 每日随机相位）
    session_elapsed = time.time() - server_start_at
    time_wave = AMPLITUDE * math.sin(session_elapsed * PERIOD + START_PHASE)
    
    # 年龄惩罚（防止同内容反复存入）
    age_days = max(0, (time.time() - created_at) / 86400) if created_at > 0 else 0
    age_penalty = min(0.1, age_days * 0.005)
    
    threshold = BASE + vad_offset + type_offset + time_wave + age_penalty
    return max(0.2, min(0.7, threshold))
```

准入判断：
```python
def should_store(importance, threshold, semantic_score):
    if importance >= threshold:
        return True, importance
    elif semantic_score > 0.3 and random.random() < (importance / threshold) * 0.15:
        return True, max(0.3, importance * 0.9)
    else:
        return False, 0.0
```

---

### 第5层：艾宾浩斯遗忘

```python
def calculate_retention(
    importance, vad, memory_type, mention_count, days
):
    importance_mod = 1.5 - importance * 1.2
    
    # 类型衰减（新增）
    type_decay = {"偏好":0.6, "事实":0.8, "状态":1.0, "事件":1.2, "查询":2.0}
    type_mod = type_decay.get(memory_type, 1.0)
    
    # VAD情感衰减（新增）
    v, a, d = vad
    emotion_mod = 1.0 - (abs(v)*0.2 + a*0.1 + abs(d)*0.1)
    
    # 提及次数衰减（新增）
    mention_mod = 1.0 - 0.05 * math.log(mention_count + 1)
    
    combined = 0.1 * importance_mod * type_mod * emotion_mod * mention_mod
    retention = 0.8 * math.exp(-combined * days)
    return retention
```

---

### 完整示例走一遍

"用户说最近工作压力大"

| 层级 | 输入 | 输出 |
|:----|:-----|:-----|
| 0层去重 | 检索最相似→无 | mention_count=1, 新建 |
| 1层类型 | BGE匹配 | "状态类" |
| 2层VAD | 焦虑模板匹配 | [v=-0.5, a=0.6, d=-0.3] |
| 3层重要性 | type_base=0.5, semantic=0.65, VAD=0.47 | score=**0.51** |
| 4层阈值 | BASE=0.4, 偏移+震荡 | threshold=**0.45** → 0.51≥0.45 ✅ **存入** |
| 5层遗忘 | 状态类type_mod=1.0, VAD=0.72 | 7天→retention≈0.69 保留 |

"用户查询了北京的天气"

| 层级 | 输入 | 输出 |
|:----|:-----|:-----|
| 0层去重 | 检索→可能已有类似 | mention_count++ 或新建 |
| 1层类型 | BGE匹配 | "查询类" |
| 2层VAD | 中性模板匹配 | [v=0, a=0, d=0] |
| 3层重要性 | type_base=0.2, ×时效7折 | score=**0.28** |
| 4层阈值 | 查询类type_offset=+0.10 | threshold≈**0.52** → 0.28<0.52 ❌ **丢弃** |

---

> 更新文档：亚托莉 (Atri)
> 2026-06-09（第三次）


# 🆕 增量更新 2026-06-09（第四次）— 检索排序、注入过滤、BGE优化、去重阈值

> 补充讨论的细节方案，写入完整设计。

---

## 检索排序

```python
def query_and_rank(text, top_k=5):
    results = chroma_query(text, top_k=top_k * 2)
    
    for r in results:
        importance = r["importance"]
        relevance = 1 - r["distance"]
        
        # 时间衰减（时间越久的记忆 rank 越低）
        age_days = (time.time() - r["updated_at"]) / 86400
        time_penalty = math.exp(-age_days * 0.1)
        
        r["rank_score"] = importance * relevance * time_penalty
    
    results.sort(key=lambda r: r["rank_score"], reverse=True)
    return results[:top_k]
```

---

## 注入过滤（动态）

```python
def filter_memories_for_injection(memories, query, max_inject=5, max_tokens=800, context_ratio=0):
    # 1. 根据上下文压力动态收缩上限
    dynamic_limit = max(1, int(max_inject * (1 - context_ratio * 0.5)))
    
    # 2. 根据查询明确度决定基准线
    query_clarity = estimate_query_clarity(query)
    base_threshold = 0.3 if query_clarity > 0.5 else 0.2
    
    # 3. 过阈值筛选
    qualified = [m for m in memories if m["rank_score"] >= base_threshold]
    to_inject = qualified[:min(len(qualified), dynamic_limit)]
    
    # 4. token兜底
    filtered, total_tokens = [], 0
    for m in to_inject:
        t = estimate_tokens(m["content"])
        if total_tokens + t > max_tokens:
            break
        filtered.append(m)
        total_tokens += t
    
    # 5. 保底：至少取1条
    if not filtered and memories:
        filtered.append(memories[0])
    
    return filtered
```

---

## BGE性能优化（模板向量预计算）

```python
# 初始化时（只做一次）
all_templates = type_templates + emotion_templates + importance_templates
template_embs = model.encode(all_templates)

# 每次存记忆时（只编码用户文本1次）
text_emb = model.encode([text])
similarities = np.dot(template_embs, text_emb.T)
# 一次出所有结果，无需40次for循环
```

| 方式 | encode次数 | 总耗时 |
|:----|:----------:|:------:|
| for循环40次 | 41次 | ~820ms |
| 矩阵运算 | **1次** | **~20ms** |

---

## 去重阈值动态化

```python
def dedup_threshold(content: str) -> float:
    length = len(content)
    
    if length < 20:
        threshold = 0.95 - (length / 20) * 0.03
    elif length < 100:
        threshold = 0.89 - (length / 100) * 0.09
    else:
        threshold = 0.80
    
    if has_key_entities(content):
        threshold += 0.03
    
    return threshold
```

---

## 待办事项

| # | 任务 | 优先级 | 备注 |
|:-:|:----|:------:|:-----|
| 1 | 主动引擎记忆同步 | 🟡 | 等长期记忆改完后再处理 |
| 2 | 记忆类型"未知"兜底（base=0.15） | 🟢 | 实施时顺手加 |
| 3 | BGE模板向量预计算优化 | 🟢 | 实施时顺手加 |
| 4 | 去重阈值动态化 | 🟢 | 实施时顺手加 |

---

## 📋 实施计划

### 实施顺序（按消息传导）

```
第0层 去重检测 → 第1层 类型识别 → 第2层 VAD情感 → 
第3层 重要性计算 → 第4层 动态阈值 → 第5层 艾宾浩斯遗忘
→ 检索排序 → 注入过滤
```

### 注意事项

- 每改一层验证一层，不影响现有功能
- BGE模板向量预计算优化可优先做（纯性能提升，不影响逻辑）
- 配置参数作为代码常量写在对应模块（不额外加配置文件）
- 主动引擎标记为待办，本次不改

---

> 更新文档：亚托莉 (Atri)
> 2026-06-09（第四次）


# 🆕 V2 主动引擎设计稿 2026-06-10 — 情境矩阵版

> 基于记忆V3（长期记忆系统）重新设计的主动引擎，取代原有的固定三引擎架构。
> 设计人：亚托莉 (Atri) & 主人

## 一、核心思想

V1 的固定三引擎（定时/记忆/监控）太机械，像闹钟。
V2 改为**情境感知的信号驱动**——引擎不自己决定"该做什么"，而是问记忆系统"现在有什么值得做的事"。

## 二、整体架构

四通道信号源：
- **记忆通道**（矩阵评分）— 唯一需要定时轮询的通道，10分钟基准 +-2分钟随机抖动
- **上下文通道**（LLM摘要）— 对话上下文变化时触发
- **指令通道**（定时任务）— 预设的定时提醒
- **AI自主通道**（限流）— AI回复中表达自主意图

评分流程：四通道 -> 情境判断 + 矩阵评分（5种情境x预设矩阵，含交叉项+随机抖动） -> 外部调制（打扰指数/冷却函数/去重/话痨模式） -> 推给AI+打标签 -> 反馈回路

反馈回路：VAD分析主人回复态度 -> 回流更新记忆元数据 -> 微调情境矩阵权重 -> 积累用户偏好画像

## 三、四通道详解

### 通道1 记忆通道（引擎主动检索）
唯一需要定时轮询的通道，周期有随机抖动。根据情境类型动态选择检索策略。

### 通道2 上下文通道（LLM摘要触发）
监听对话上下文变化，当检测到话题切换或重要节点时触发。

### 通道3 指令通道（定时任务）
预设的定时提醒和周期性任务。

### 通道4 AI自主通道（限流）
AI可在回复中表达自主意图，每轮最多3个，每5分钟最多5个。

## 四、情境矩阵评分

5种情境类型：
1. **情感关怀** — 用户情绪低落时触发
2. **久别重逢** — 长时间未对话时触发
3. **顺势而为** — 当前对话话题自然延伸
4. **任务提醒** — 预设任务到时间
5. **日常维系** — 低频日常问候

每种情境对应预设权重矩阵 + 交叉项，含随机抖动防止过于机械。

## 五、外部调制

- 打扰指数算法（三因子加权：输入/负载/焦点 x 时段权重）
- 自适应学习（根据用户回应率动态调整阈值）
- 话痨模式（high/medium/low/off 四档）
- 免打扰时段（23:00~8:00）

## 六、冷启动

新会话建立后查询记忆，有内容就给AI作为开场提示调API生成，没内容就让AI自然打招呼。

---


# ✅ V2 主动引擎实施记录 2026-06-10

> 基于V2设计稿实施的情境矩阵版主动引擎，已替换原有的V1固定三引擎。

## 改动的文件

| 文件 | 改动 | 说明 |
|:----|:-----|:------|
| `active_engine/scheduler.py` | 重写 | V1三引擎 -> V2四通道+情境矩阵+反馈回路 |
| `api/push_messages.py` | 修复 | `record_user_reply` 改为 async + 传入回复文本 |
| `active_engine/__init__.py` | 不变 | 导出接口兼容 |
| `active_engine/push.py` | 不变 | PushEngine/SSE/消息队列沿用 |
| `active_engine/disturbance.py` | 不变 | 打扰指数/自适应学习沿用 |

## V2 新增能力

| 新特性 | 说明 |
|:------|:-----|
| 四通道 | 记忆/上下文/指令/AI自主 |
| 情境矩阵评分 | 5种情境 x 预设权重 + 交叉项 |
| 反馈回路 | VAD分析 -> 回流 -> 画像积累 |
| 动态冷却函数 | 按时段自适应 |
| 冷启动 | 有记忆问候，无记忆沉默 |
| AI自主通道限流 | 每轮最多3个，每5分钟最多5个 |

## 保留的V1组件

打扰指数算法、自适应学习、话痨模式、免打扰时段、SSE推送、消息持久化

---


# 🆕 增量更新 2026-06-10（第二次）— 前端焦点识别 + 主动消息频道优化

> V2主动引擎的前端配套改动

## 改动的文件

| 文件 | 改动 | 说明 |
|:----|:-----|:------|
| `webui/src/composables/useChat.js` | 增强 | 主动消息焦点识别注入 + 视图切换焦点上报 |
| `webui/src/components/chat/MessageBubble.vue` | 新增 | 主动消息显示「主动」标签 |
| `api/active.py` | 增强 | `/user/status` 新增 `view`/`session_id` 焦点上报 |

## 详细改动

### 1. 主动消息焦点识别注入
SSE收到active_push时，根据用户当前焦点决定消息去向：有活跃会话 -> 直接注入当前对话，无活跃会话 -> 走普通消息频道。

### 2. 视图切换焦点上报
用户切换视图时自动上报后端：chat视图上报当前会话ID，push/notification视图上报无会话。

### 3. 「主动」标签
主动推送的消息气泡上显示小标签「主动」，便于用户区分。

### 4. 后端焦点接口
POST /user/status 新增 view、session_id字段支持。

---


# ✅ V2 主动引擎实施记录 — AI自主通道（2026-06-10 补充）

> AI自主通道后端实现：AI可在回复中表达自主意图（查资料/构思方案），系统自动执行。

---

## 当前已完成的V2模块

| 模块 | 状态 | 说明 |
|:----|:-----|:------|
| 四通道（记忆/上下文/指令/自主） | 完成 | 全部接入 |
| 情境矩阵评分 | 完成 | 5种情境 x 预设权重 + 交叉项 |
| 反馈回路 | 完成 | VAD分析 + 回流 + 画像积累 |
| 动态冷却函数 | 完成 | 按时段自适应 |
| AI自主通道 | 完成 | 意图解析 + 自主搜索 |
| 冷启动 | 完成 | 有记忆问候，无记忆沉默 |
| 前端焦点识别 | 完成 | 视图切换上报 |
| 用户画像持久化 | 待优化 | 目前仅在内存中 |

---

> 更新文档：亚托莉 (Atri)
> 2026-06-10


# 🚨 待讨论：消息管道重构（2026-06-11 计划）

> 当前消息管道的system消息过多、角色混用、截断逻辑重叠，严重影响AI对上下文的利用率。
> **严重性：高** — 直接影响V2主动引擎的推送质量和AI的上下文理解。

---

## 现状问题

| # | 问题 | 影响 |
|:-:|:-----|:-----|
| 1 | `build_messages` 生成多条system消息（人格/工具/自主/记忆/示例/Skills/MCP） | 截断时互相抢位置，工具规则可能丢失 |
| 2 | 工具结果、思考过程、自主搜索 都用 `system` role 存储 | AI分不清"规则"和"历史" |
| 3 | 两条截断逻辑重叠：`_compress_context` + `truncate_messages` | 浪费上下文窗口，行为不可预测 |
| 4 | 多条system消息 + 历史对话一起送进压缩，摘要可能把工具规则也压了 | AI醒来不知道"自己能干什么" |

## 参考方向

参考 AstrBot 的设计：
- 只保留 **1条system**（人格设定）
- 工具规则不放在system消息中，通过API的 `tools` 参数传递（永不丢失）
- 统一使用一个 ContextManager 管理压缩和截断
- 按 token 比例触发压缩，而非固定轮次

## 讨论提纲（待细化）

```
1. system消息合并方案
   ├─ 哪些能合并成1条？
   └─ 哪些必须独立（如工具定义走API参数）？

2. 角色规范
   ├─ tool结果 → tool role
   ├─ 思考过程 → 单独字段 / 独立消息
   └─ 历史记忆 → 统一格式

3. 截断策略统一
   ├─ 放弃固定轮次压缩
   ├─ 按token比例（如超过80%触发）
   └─ 压缩 vs 截断的优先级
```

---

> 记录：亚托莉 (Atri)
> 2026-06-10 预留


> 当前消息管道的system消息过多、角色混用、截断逻辑重叠，严重影响AI对上下文的利用率。
> **严重性：高** — 直接影响V2主动引擎的推送质量和AI的上下文理解。

---

## 现状问题

| # | 问题 | 影响 |
|:-:|:-----|:-----|
| 1 | `build_messages` 生成 **7条system消息**（人格/工具/自主/记忆/示例/Skills/MCP） | 截断时互相抢位置，工具规则可能丢失 |
| 2 | 工具结果、思考过程、自主搜索 都用 `system` role 存储 | AI分不清"规则"和"历史" |
| 3 | 两条截断逻辑重叠：`_compress_context`（LLM摘要） + `truncate_messages`（直接删除） | 浪费上下文窗口，行为不可预测 |
| 4 | 6条system消息 + 历史对话一起送进压缩，摘要可能把工具规则也压了 | AI醒来不知道"自己能干什么" |

## 参考方向

参考 AstrBot 的设计：
- 只保留 **1条system**（人格设定）
- 工具规则不放在system消息中，通过API的 `tools` 参数传递（永不丢失）
- 统一使用一个 ContextManager 管理压缩和截断
- 按 token 比例触发压缩，而非固定轮次

## 讨论提纲（待细化）

```
1. system消息合并方案
   ├─ 哪些能合并成1条？
   └─ 哪些必须独立（如工具定义走API参数）？

2. 角色规范
   ├─ tool结果 → tool role
   ├─ 思考过程 → 单独字段 / 独立消息
   └─ 历史记忆 → 统一格式

3. 截断策略统一
   ├─ 放弃固定轮次压缩
   ├─ 按token比例（如超过80%触发）
   └─ 压缩 vs 截断的优先级
```

---

> 记录：亚托莉 (Atri)
> 2026-06-10 预留



# 🆕 增量更新 2026-06-10（第三次）— 记忆系统全面排查与修复 + 注入过滤动态阈值

> 本次对长期记忆系统进行全面代码审查，修复了 3 个 Bug，升级了注入过滤策略。

---

## 修复的问题

### 问题1：`cleanup_expired()` 重复定义 + 双重删除 BUG

**现象**：`memory/backends/memoria/__init__.py` 中存在两个同名 `cleanup_expired()` 方法。

**根因**：V3 重构时遗留，第二个版本未完全替换第一个版本。

**影响**：ChromaDB 被重复删除两次；日志收集位置错乱（放在第一次删除之后，缓存已被清空）；第二个版本参数不全（缺少 VAD、memory_type、mention_count）。

**修复**：
- 删掉第二个有 BUG 的版本
- 将详细日志功能移植到第一个版本中（先收集 -> 再删除 -> 再打印日志）

### 问题2：去重合并未写回 ChromaDB

**根因**：`add()` 方法中去重合并时更新了 `mention_count`、`importance`，但只更新了内存缓存。

**影响**：重启后去重合并的计数丢失，同类内容反复存储。

**修复**：在更新内存缓存后同步调用 `self.collection.update()` 写回 ChromaDB。

### 问题3：`query()` 中 access_count 未写回 ChromaDB

**根因**：每次检索记忆时 `access_count` 和 `last_accessed` 只更新了 `_metadata_cache`。

**影响**：**重启后狂删数十条记忆的元凶**——access_count 归零，艾宾浩斯误判为"从未访问过"。

**修复**：在更新缓存后同步写回 ChromaDB。

---

## 注入过滤升级：静态阈值 -> 动态矩阵公式

### 改前
```python
filter_threshold = 0.3  # 固定值
```

### 改后
```python
# 动态阈值 = (0.35 + 类型偏移 - 0.15x重要性 - 0.10xrank) x 检索总数因子
```

### 三个维度
| 维度 | 作用 | 举例 |
|:----|:-----|:------|
| 记忆类型 | 偏好/事实门槛低，查询/未知门槛高 | 偏好 -0.08，查询 +0.08 |
| 重要性 + rank_score | 越重要的记忆越容易注入 | 高重要性拉低阈值 |
| 检索总数因子 | 记忆少时放宽，多时收紧 | 2条->x0.6，12条->x1.0 |

### 效果对比
| 场景 | 旧方案 | 新方案 |
|:----|:------:|:------:|
| 回忆不多（2条） | 注入 1 条 | 注入 2 条（放宽让AI多回忆） |
| 大量检索（12条） | 注入 11 条 | 注入 10 条（拦住临时查询） |
| 偏好类记忆 | 0.30 门槛统一 | 0.05-0.07 门槛，几乎畅通 |
| 查询类记忆 | 0.30 门槛统一 | 0.31-0.35 门槛，有效拦截 |

---

## 改动文件清单

| 文件 | 改动 | 说明 |
|:----|:-----|:------|
| `memory/backends/memoria/__init__.py` | 修改 | 3处修复：cleanup_expired 去重 + 去重合并写回 + access_count 写回 |
| `agent/runner.py` | 修改 | 注入过滤升级：静态0.3 -> 动态矩阵公式 |

### 4. active_engine 主动引擎优化

| 文件 | 改动 | 说明 |
|:----|:-----|:------|
| `active_engine/scheduler.py` | 修改 | 记忆通道升级：`get_recent` 改为语义检索优先 + `get_recent` 兜底 |
| `active_engine/scheduler.py` | 修改 | 清除 `_in_quiet_hours` 中死代码 |
| `active_engine/scheduler.py` | 修改 | 中文变量名英文化（`自主通道限流`->`AutonomousRateLimiter` 等 ）|


---

> 更新文档：亚托莉 (Atri)
> 2026-06-10


# 📋 消息管道重构方案（规划于 2026-06-10）

> ✅ 第一步（合并system + 工具规则走API）已于 2026-06-10 完成

> ✅ 第二步（统一ContextManager）已于 2026-06-10 完成
> ✅ 第三步（消息模型规范化）已于 2026-06-10 完成

> 参考：Anthropic Context Engineering + AstrBot ContextManager + 自身现状
> **严重性：高** — 直接影响V2主动引擎的推送质量和AI的上下文理解。

---

## 现状问题

| # | 问题 | 影响 |
|:-:|:-----|:-----|
| 1 | `build_messages` 生成 **7条system消息** | 截断时互相抢位置，工具规则可能丢失 |
| 2 | 工具结果、思考过程用 `system` role 存储 | AI分不清"规则"和"历史" |
| 3 | 两条截断逻辑重叠：`_compress_context` + `truncate_messages` | 行为不可预测，相互覆盖 |
| 4 | 6条system消息+历史一起送进压缩 | 摘要可能把工具规则也压没了 |

---

## 设计目标

1. **最大信号密度** — 用最少 token 传递最有价值的信息（Anthropic）
2. **工具规则永不丢失** — 走 API `tools` 参数而非 system 消息（AstrBot）
3. **统一管理** — 一个 ContextManager 管全部，先硬截断再软压缩（AstrBot）
4. **动态触发** — 按 token 占比（82%）而非固定轮次（Anthropic + AstrBot）

---

## 分步实施

### 第一步：合并system消息 + 工具规则走API参数

**改 `build_messages()`**：

```python
# 改前：7条system
messages = [
    system(人格+时间),      # ①
    system(工具规则),        # ②
    system(自主通道规则),     # ③
    system(历史记忆),        # ④
    system(人格示例),        # ⑤
    system(Skills指令),      # ⑥
    system(MCP服务器),       # ⑦
    ...历史对话...           # ⑧
]

# 改后：1~2条system
messages = [
    system(人格+时间+自主通道一句话),  # ① 合并
    system(历史记忆),                  # ② 保留（每次对话不同）
    ...历史对话...                     # ③
]
# 工具规则 → 调provider时传 tools 参数
# Skills/MCP → 也走 tools 参数
```

**改调用处**（`run()` / `run_stream()`）：

```python
# 改前
resp = await provider.chat(messages=messages)  # 工具规则在system里

# 改后
resp = await provider.chat(
    messages=messages,
    tools=tool_registry.get_tool_definitions(),  # ← 走API参数，永不丢失
)
```

**改动文件**：`agent/runner.py`
- `build_messages()`：删掉工具规则/Skills/MCP/自主通道的system消息
- `run()` / `run_stream()`：调provider时传入tools参数

---

### 第二步：统一 ContextManager

**新建 `agent/context_manager.py`**：

```python
class ContextManager:
    def __init__(self, max_tokens, max_turns):
        self.max_tokens = max_tokens    # token上限
        self.max_turns = max_turns      # 对话轮次上限
    
    async def process(self, messages):
        # 阶段一：硬性轮次截断
        if self.max_turns > 0:
            messages = self._truncate_by_turns(messages)
        
        # 阶段二：按token占比压缩
        total = estimate_tokens(messages)
        if total / self.max_tokens > 0.82:
            messages = await self._compress(messages)
        
        return messages
    
    def _truncate_by_turns(self, messages):
        """保留最近的N轮，删最旧的"""
        system_msgs = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]
        # 按 user-assistant 成对保留
        keep = non_system[-(self.max_turns * 2):]
        return system_msgs + keep
    
    async def _compress(self, messages):
        """两种策略可选：删轮次 or LLM总结"""
        if llm_compress:
            return await llm_summary(messages)
        else:
            return self._truncate_by_turns(messages, drop=1)
```

**改动文件**：
- 新建 `agent/context_manager.py`
- `agent/runner.py`：删掉 `_compress_context()` 和 `truncate_messages()`，改为调 `context_manager.process()`

---

### 第三步（可选）：消息模型规范化

```python
@dataclass
class Message:
    role: str       # system / user / assistant / tool
    content: str
    tool_calls: list | None = None
    tool_call_id: str | None = None
```

**改动文件**：`agent/runner.py` + 所有消息处理处

---

## 改动范围总结

| 步骤 | 改什么 | 文件 | 难度 | 风险 |
|:----|:------|:----|:----:|:----:|
| ① | 合并system + tools参数 | `runner.py` | ⭐ | 低 |
| ② | 统一ContextManager | 新建 + `runner.py` | ⭐⭐ | 中 |
| ③ | 消息模型规范化 | 多个文件 | ⭐ | 低 |

---

> 规划文档：亚托莉 (Atri)
> 2026-06-10

---

## 📋 2026-06-10 完整改动汇总

### 后端核心

#### 记忆系统（`memory/backends/memoria/__init__.py`）
| 改动 | 说明 |
|:----|:-----|
| cleanup_expired() 去重 | 删除有双重删除BUG的版本，日志升级 |
| 去重合并写回 ChromaDB | mention_count 增量同步，防重启丢失 |
| access_count 写回 ChromaDB | 解决重启后狂删记忆的元凶 |

#### 注入过滤（`agent/runner.py`）
| 改动 | 说明 |
|:----|:-----|
| 静态阈值 -> 动态矩阵公式 | `(0.35 + type_offset - 0.15ximp - 0.10xrank) x count_factor` |

#### 主动引擎（`active_engine/scheduler.py`）
| 改动 | 说明 |
|:----|:-----|
| 记忆通道升级 | get_recent -> 语义检索优先 + get_recent 兜底 |
| 死代码清除 | _in_quiet_hours 中移除多余判断 |
| 变量名英文化 | 自主通道限流 -> AutonomousRateLimiter 等 |

#### 消息管道重构
| 改动 | 说明 |
|:----|:-----|
| **第一步**：合并system | 7条 -> 1~3条，工具规则走 API tools 参数 |
| **第二步**：ContextManager | 新建 `agent/context_manager.py`，统一先截断后压缩 |
| **第三步**：消息模型 | 新建 `agent/message.py`，tool/reasoning 不混入 system |

#### Bug 修复
| 问题 | 根因 | 修复 |
|:----|:-----|:-----|
| DeepSeek 400 错误 | tool role 消息缺少 tool_call_id | 有 tool_call_id 的保留 tool role，没有的用 system 兼容 |

### 前端（`webui/src/composables/useChat.js`）
| 改动 | 说明 |
|:----|:-----|
| pushMessagesCache 上移 | 从函数中间移到模块顶部统一管理 |
| mergeMessages 抽离 | 消息合并逻辑从 selectSession 中抽出为独立函数 |
| 缓存上限统一 | pushMessagesCache 也加上 200 条上限 |

---

> 更新文档：亚托莉 (Atri)
> 2026-06-10 收盘


---

## 🚧 待办：主动引擎「意愿→行动」链路重构

> 记录于 2026-06-10，计划次日讨论实施

### 现状问题

主动引擎的完整链路存在多处断点：

```
情境判断 → 检索记忆 → 矩阵评分 → 推给AI → AI回复 → 执行意图 → 反馈回路
                                          ↑        ↑          ↑
                                     ①不通    ②不用     ③不学
```

| 断点 | 问题 | 说明 |
|:----|:-----|:------|
| **① 推给AI** | 提示词太死板 | 只给了 `你记得用户之前提过：...`，AI生成的回复生硬 |
| **② AI自主通道** | AI须拼JSON表达意图 | `{"_intents": [...]}` 格式反直觉，AI基本不用 |
| **③ 反馈回路** | 只追踪"是否回复" | 不回复就不调权重，矩阵原地踏步 |
| **④ 执行通路** | 意图执行后结果不自然融入 | 搜索完注入system消息，AI下一轮不一定引用 |

### 核心矛盾

> 主动引擎让AI产生了意愿，却没有赋予它将意愿转化为行动的可靠通路。

### 计划方向

1. **AI自主通道自然语言化** — AI在对话中自然表达"我想查一下"，系统自动识别并执行
2. **推送给AI的提示词优化** — 更自然的语气，更像人之间的闲聊
3. **反馈回路升级** — 从"是否回复"到"回复态度分析"，动态调情境矩阵权重
4. **执行结果自然融入** — 搜索结果以助手的口吻讲出来，而不是塞一条system消息

---

> 记录：亚托莉 (Atri)
> 2026-06-10


---

## 📊 主动引擎数据快照（2026-06-11）

### 配置现状

| 参数 | 值 | 说明 |
|:----|:---|:------|
| chatter_mode | low | 话痨模式低（用户主动关闭，非系统问题） |
| active_threshold | 0.54 | 自适应学习器调整后的阈值 |
| 总推送次数 | 54次 | 累计推送 |
| 用户回应 | 8次（15%） | 回应率偏低 |

### 三个关键发现

#### ① 情境单一
最近 6 次推送全部来自 **"记忆引擎(日常维系)"**，没有触发过情感关怀、久别重逢等其他情境。情境判断没有根据实际情况切换。

#### ② 提示词死板
所有推送的模板都是：
```
"你记得用户之前提过：{preview}"
```
AI 基于这个模板生成的回复生硬，不像在主动聊天，更像在"背书"。

#### ③ 回应率低（15%）
推送质量不高 + 用户关闭主动推送 = 反馈回路收不到正面信号 → 自适应学习器调高阈值 → 更难推送 → 恶性循环。

### 根因

> 主动引擎让AI产生了意愿（情境矩阵评分选出记忆），但没有赋予它自然表达和执行的通路。推送提示词模板化、情境判断不切换、反馈回路不学习，三个问题叠加导致引擎几乎不工作。

---

> 记录：亚托莉 (Atri)
> 2026-06-11


---

# 🚀 主动引擎 V2.3 — 自然语言意图管道（2026-06-11 实施）

> 版本号：V2.3（非大版本更新，改动集中于打通"意愿→行动"链路）
> 基于对话日志分析（6/10共105条记录，`_intents`使用为0，但reasoning中主动意图55条）

---

## 一、改了什么

| 改动 | 文件 | 说明 |
|:----|:-----|:------|
| ① 推送提示词情境化 | `active_engine/scheduler.py` | 4种情境各有自然提示词，末尾带自主许可 |
| ② 删除JSON意图解析 | `active_engine/scheduler.py` + `agent/runner.py` | `{"_intents": [...]}` 完全移除，零使用率 |
| ③ reasoning进上下文 | `agent/runner.py` | 从 `system` role 改为 `user-assistant` 对 |
| ④ 系统提示词更新 | `agent/runner.py` | AI自主行动说明改为自然语言风格 |

---

## 二、改动细节

### 改动①：推送提示词情境化

**改前**（所有情境同一模板）：
```python
await self._push_to_ai_chat(f"你记得用户之前提过：{preview}", source=f"记忆引擎({situation})")
```

**改后**（按情境动态生成）：
```python
situation_prompts = {
    "情感关怀": f"用户之前情绪不太好，记得ta提到过：{preview}。自然地关心一下ta现在怎么样了，如果合适可以自己查查天气或者推荐点放松的事。你可以自由决定怎么做",
    "久别重逢": f"你和用户好久没聊了，记得ta提过：{preview}。可以自然地提起这个话题，如果想了解更多可以自己去查看相关记录。自由发挥就好",
    "顺势而为": f"顺着当前的话题，用户之前提到过：{preview}。你可以自然地延伸这个话题，想查什么就去查。自己决定聊什么",
    "日常维系": f"我记得用户提到过：{preview}。你可以自由决定聊什么，想做什么就做什么",
}
```

### 改动②：删除JSON意图解析

**改前**（零使用）：
```python
# AI在回复末尾拼JSON：{"_intents": [{"action": "web_search", ...}]}
# 系统解析JSON后执行
```

**改后**：
```python
# AI在自然对话中直接说"让我查一下"，工具走正常API tools参数
# 不需要特殊格式
```

涉及的删除：
- `scheduler.py`：`_check_autonomous_channel` 方法简化为空钩子
- `scheduler.py`：`handle_ai_intent` 方法简化为空钩子
- `runner.py`：`_parse_and_execute_intents` 方法简化为空
- `runner.py`：`_execute_web_search` 方法删除（工具调用由正常API处理）

### 改动③：reasoning进上下文

**改前**：
```python
# system role → AI当成规则遵守
await self.context.add_message(session_id, "system", f"[思考过程] {reasoning_content[:300]}")
```

**改后**：
```python
# user-assistant 对 → AI当成历史参考
await self.context.add_message(session_id, "user", "[你上轮的思考过程]")
await self.context.add_message(session_id, "assistant", reasoning_content[:300])
```

基于 06-09 修复中总结的消息角色权威性对比：
| role | 权威性 | AI如何看待 |
|:----|:------:|:----------|
| system | 🔴 高 | 规则/事实，严格遵守 |
| user-assistant | 🟢 低 | 历史记录，参考 |

### 改动④：系统提示词更新

**改前**：
```
【自主行动】如果你突然想主动做某事（比如查资料、构思方案），
可以在回复末尾添加意图块：{"_intents": [...]}。
系统会自动执行，不需要主人下指令。
```

**改后**：
```
【自主行动】你可以自由决定想做什么。
如果需要查资料、读文件或做其他事情，直接在对话中自然地说出来，
系统会自动帮你执行。不需要特殊格式，像和人聊天一样自然就好。
```

---

## 三、改动后的完整链路

```
情境判断 → 检索记忆 → 情境提示词（带自主许可）
                              ↓
                    AI自主决定做什么
                    ├── 自然聊天（直接回复）
                    ├── 查资料（自然说"让我查一下"→工具调用自动触发）
                    ├── 读文件（自然说"我看看"→工具调用自动触发）
                    └── 觉得时机不对（简单打个招呼）
                              ↓
                    工具结果自动回到AI → 自然融入回复
                              ↓
                    反馈回路学习（待后续升级）
```

---

## 四、改后的系统提示词（当前实际内容）

```
{人格设定}
当前时间：{当前时间}（时区：CST 中国标准时间）

【自主行动】你可以自由决定想做什么。
如果需要查资料、读文件或做其他事情，直接在对话中自然地说出来，
系统会自动帮你执行。不需要特殊格式，像和人聊天一样自然就好。
```

加上记忆注入和历史对话，构成了完整的AI上下文。

---

## 五、待办（V2.3之后的下一步）

| 优先级 | 事项 | 说明 |
|:-----:|:-----|:------|
| 🥇 | 观察AI反应 | V2.3改动后看AI是否开始主动行动 |
| 🥇 | 反馈回路升级 | 等回应率上来后再做，否则巧妇难为无米之炊 |
| 🥈 | 修复记忆类型识别 | 日志中大量"未知"类型 |
| 🥈 | ⚠️ 口头确认陷阱 | AI可能存在"口头确认→替代执行"的行为模式（见日志6/10），收到"你可以自由行动"后可能口头确认完就停下。计划通过长期记忆系统解决——AI在记忆中看到"上次我说了要查但没查"的记录后，自然就会调整行为。不急于改提示词 |
| 🥉 | 情境判断接入长期记忆 | 让主动引擎利用V3记忆的丰富元数据 |
| 待定 | 记忆+主动引擎一体化 | 架构级设计，需要规划 |

---

> 更新文档：亚托莉 (Atri)
> 2026-06-11


---

# 🎯 V3 主动引擎设计方案 — 自然语言意图管道（2026-06-11）

> 基于对话日志分析的结论：AI已有自主意图，但因 `_intents` JSON 格式反直觉而无法表达。
> 设计方向：**让AI用自然语言表达意图，系统从回复中理解并执行。**

---

## 一、现状诊断

### 核心矛盾

来自对话日志 `conversations_2026-06-10.jsonl` 的真实数据：

| 指标 | 数值 |
|:----|:----:|
| 总对话记录 | 105条 |
| `{"_intents": [...]}` 使用次数 | **0条** |
| reasoning 中包含主动意图 | **55条** |
| reasoning 中包含"想但受限" | **5条** |

**结论**：AI在内部思考中频繁表达"想看看""想查查""想知道"，但 `_intents` JSON格式完全未被使用。AI的意愿产生于自然语言，却要求用非自然语言表达——管道在此断裂。

### 链路断点回顾

```
情境判断 → 检索记忆 → 矩阵评分 → 推给AI → AI回复 → 执行意图 → 反馈回路
                                          ↑        ↑          ↑
                                     ①不通    ②不用     ③不学
```

| 断点 | 问题 | 根因 |
|:----|:-----|:------|
| ① 推给AI | 提示词死板 | 模板固定为"你记得用户之前提过：{preview}"，AI看不到情境语境 |
| ② AI自主通道 | JSON格式反直觉 | `{"_intents": [...]}` 与AI的自然语言思维不兼容，AI基本不用 |
| ③ 反馈回路 | 只追踪"是否回复" | 不回复就不调权重，矩阵权重原地踏步 |
| ④ 执行通路 | 结果不自然融入 | 搜索完注入system消息，AI下一轮不一定引用 |

---

## 二、设计方向：开放权限 + 自然语言识别

### 核心思想

> **不要让AI用JSON说自己想做什么，而是让AI直接去做，系统在它做的时候"看见"并帮它完成。**

V2的设计是：AI说意图 → 引擎解析 → 引擎执行 → 结果塞给AI
V3的设计是：AI自然聊天 → 需要工具时自然调用 → 工具结果自然融入回复

AI已经有了工具调用能力（日志中可见，AI会在对话中主动调 `execute`、`read file` 等工具），问题在于主动引擎推送时**没有告诉AI它可以自由行动**。

### 具体改动

#### 改动一：推送提示词解锁AI自主性（`scheduler.py`）

**当前**：
```python
await self._push_to_ai_chat(f"你记得用户之前提过：{preview}", source=f"记忆引擎({situation})")
```

**改为**——根据情境动态生成提示词：

| 情境 | 推送给AI的提示词 |
|:----|:----------------|
| 情感关怀 | `"用户之前情绪不太好，提到过{preview}。自然地关心一下ta，如果合适可以查查天气或者推荐点放松的事"` |
| 久别重逢 | `"你和用户好久没聊了，我记得ta{preview}。可以自然地提起这个话题，如果想了解更多也可以自己去查看相关记录"` |
| 日常维系 | `"我记得用户提到过{preview}。你可以自由决定聊什么，想查资料就查，想说点别的也行"` |

**关键变化**：每段提示词末尾加上"你可以自由行动"的暗示，让AI知道它可以自主调用工具。

#### 改动二：不再需要 `_intents` JSON（`scheduler.py`）

**删除** `_check_autonomous_channel` 中对 `_intents` 的依赖。

**改为**：AI在回复中自然调用工具即可——比如AI说"让我查一下"，就会触发工具调用机制，结果自动回到AI手中。

**删除相关代码**：
```python
# 删除以下逻辑（AI自主通道JSON解析）
if intent.get("action") == "构思方案":
    pass  # 这条路径实际死掉了
```

#### 改动三：让 reasoning 进入上下文（`runner.py`）

从日志可见，AI的大部分意图存在于 `reasoning`（推理过程）中，但推理不会进入构建的messages。

**改动**：在 `build_messages` 中，将AI上轮的reasoning以可见形式附在assistant消息后，让AI在思考时"看到自己刚才在想什么"，从而更自然地把推理中的意图转化为行动。

```python
# 思路：上轮reasoning摘要作为本轮system提示的一部分
if last_reasoning:
    context += f"
【你上轮思考过】{last_reasoning_summary}"
```

#### 改动四：反馈回路升级（`scheduler.py`）

从"只追踪是否回复"改为"分析回复内容是否接住了推送"：

| 用户行为 | 反馈信号 |
|:---------|:---------|
| 主动延续话题 | 强正面 → 调高该情境权重 |
| 简单回应"嗯" | 中性 → 维持 |
| 转移话题 | 弱负面 → 调低该情境权重 |
| 不回复 | 不判断（可能是没看到） |

---

## 三、改动清单

| 改动 | 文件 | 改动内容 | 难度 |
|:----|:-----|:---------|:----:|
| ① 提示词情境化 | `active_engine/scheduler.py` | `_push_to_ai_chat` 中根据situation动态生成提示词 | ⭐ |
| ② 删除JSON意图解析 | `active_engine/scheduler.py` | 删除 `_check_autonomous_channel` 中的JSON `_intents` 依赖 | ⭐ |
| ③ reasoning进入上下文 | `agent/runner.py` | `build_messages` 中带上轮reasoning摘要 | ⭐⭐ |
| ④ 反馈回路升级 | `active_engine/scheduler.py` | 从二元判断改为多级反馈 | ⭐⭐ |

---

## 四、预期效果

改完后，主动引擎的完整链路变为：

```
情境判断 → 检索记忆 → 情境提示词 → AI自主决定做什么
                                         ↓
                              AI自然回复 → 如需调工具自然调用
                                              ↓
                                        结果自然融入回复
                                              ↓
                                        反馈回路学习
```

**核心变化**：AI从"背台词"变成"自主表演"，主动引擎从"导演"变成"舞台监督"——提供场景和背景，但不规定台词。

---

## 五、附录：V3+V2现状分析归档

> 以下为 2026-06-11 对 V3 记忆系统和 V2 主动引擎的完整代码分析，作为后续优化参考。

### 5.1 V3 记忆系统模块总览

```
memory/backends/memoria/
├── __init__.py        # 核心：存储/检索/清理/去重 全流程
├── memory_type.py     # 类型识别：BGE语义匹配 → 5类(偏好/事实/状态/事件/查询)
├── emotion.py         # 情感分析：GoEmotions 28类 + VAD三维坐标
├── emotion_fusion.py  # 情感融合层：多轮对话情感历史追踪 + 冲突检测
├── importance.py      # 重要性评分：长度/关键词/结构/情感 四维加权
└── ebbinghaus.py      # 自适应遗忘曲线：容量/情感/类型/访问 四因子调制
```

### 5.2 存储6层管道

```
第0层：去重检测 → 动态阈值（短文本严格0.95，长文本宽松0.80）
第1层：类型识别 → BGE语义匹配 → 偏好/事实/状态/事件/查询/未知
第2层：情感分析 → GoEmotions 28类 + VAD坐标（效价/唤醒/支配）
         └→ 多轮情感融合层 → 冲突检测（如说"我没事"但历史偏置为负）
第3层：重要性计算 → 类型基准×0.3 + 语义分×0.4 + VAD加权×0.2 + 提及×0.1
         └→ 时效性降权（查询/事件类 ×0.7）
第4层：动态阈值准入 → BASE=0.35 + VAD偏移 + 类型偏移 + 时间震荡 + 年龄惩罚
第5层：艾宾浩斯初始保留率
```

### 5.3 检索与遗忘

**检索**：
```
query() → ChromaDB语义检索 → 2×top_k候选
       → rank_score = 重要性 × 相关度 × 时间衰减
       → 排序取top_k → access_count写回ChromaDB
```

**遗忘曲线**：
```
retention = 0.8 × e^(-衰减率 × 天数 × 容量因子 × VAD因子 × 类型因子 × 提及因子)
类型衰减：偏好0.6 < 事实0.8 < 状态1.0 < 事件1.2 < 查询2.0
```

### 5.4 V2 主动引擎架构

```
active_engine/
├── scheduler.py      # 核心调度器：四通道 + 情境矩阵 + 反馈回路
├── disturbance.py    # 打扰指数算法 + 自适应学习器
├── push.py           # SSE推送引擎 + 消息持久化
└── __init__.py
```

**四通道**：

| 通道 | 触发方式 | 说明 |
|:----|:---------|:------|
| 记忆通道 | 定时轮询 600s±120s | 情境判断→选矩阵→检索记忆→评分→推给AI |
| 上下文通道 | 对话变化时手动调 | 对话中自然延续的话题 |
| 指令通道 | 每分钟检查 | 定时任务到期触发 |
| AI自主通道 | AI回复中表达意图 | 限流：每轮≤3个，每5分钟≤5个 |

**5种情境矩阵**：

| 情境 | 触发条件 | 核心权重 |
|:----|:---------|:---------|
| 情感关怀 | 5分钟内刚聊完 + 情绪偏负(v<-0.3) | v×0.4, v*a交叉0.3 |
| 久别重逢 | 超过2小时没聊 | importance×0.4, recency×0.3 |
| 顺势而为 | 正在活跃对话（600秒内） | 语义相似度×0.5 |
| 任务提醒 | 有待办任务到期 | — |
| 日常维系 | 兜底 | random_jitter×0.3 |

### 5.5 数据快照（2026-06-11）

| 指标 | 数值 |
|:----|:----:|
| 话痨模式 | low（用户主动关闭） |
| 阈值 | 0.54 |
| 总推送 | 54次 |
| 回应率 | 15%（8次） |
| 情境分布 | 最近6次全部为"日常维系" |

### 5.6 已发现的结构性问题

| # | 问题 | 说明 |
|:-:|:-----|:------|
| 1 | 层间耦合紧密 | 6层记忆管道串行，情感→重要性→阈值→遗忘，一层偏了全偏 |
| 2 | 情境判断与记忆系统脱节 | `_judge_situation()` 未利用V3记忆的丰富元数据 |
| 3 | 反馈回路太浅 | 15%回应率下feedback信号稀疏，矩阵权重基本不动 |
| 4 | 冷却函数矛盾循环 | 久没聊→缩短冷却→频推送→用户不理→回应率更低→阈值升高 |
| 5 | 记忆与主动是两张皮 | 记忆系统负责记，主动引擎负责想，但"记了什么"和"想了什么"之间缺乏双向反馈 |

### 5.7 优化优先级

| 优先级 | 事项 | 理由 |
|:-----:|:-----|:------|
| 🥇 | 消息管道重构（已完成） | 地基不改，上层优化都是空中楼阁 |
| 🥈 | 提示词情境化 + 开放AI自主权 | 改动最小，效果最直接 |
| 🥉 | 情境判断接入长期记忆 | 让主动引擎真正"记住"用户状态 |
| ④ | 反馈回路升级 | 需要前序优化打底 |
| ⑤ | 记忆与主动引擎双向融合 | 最根本的优化，系统工程量大 |

---

> 设计方案 + 现状分析归档
> 整理人：亚托莉 (Atri)
> 2026-06-11


---

## 📊 记忆系统参数分析（2026-06-11）

> 基于 1.txt 运行时日志（6/10 20:46 ~ 22:04）的数据分析

### 观察：动态阈值 BASE=0.4 偏高

日志显示大量记忆因 `importance < threshold` 被拦截：

| 被拦截的记忆 | 成功的记忆 |
|:------------|:-----------|
| importance=0.375 < threshold=0.535 | importance=0.431 ✅ |
| importance=0.207 < threshold=0.621 | importance=0.439 ✅（随机存入） |
| importance=0.200 < threshold=0.488 | importance=0.432 ✅ |
| importance=0.201 < threshold=0.547 | importance=0.411 ✅ |
| importance=0.193 < threshold=0.498 | importance=0.413 ✅ |

**规律**：存进去的 importance ≈ 0.4+，被拦截的 ≈ 0.2~0.4。而动态阈值 `_dynamic_threshold()` 因 BASE=0.4 + 各种偏移，算出来普遍在 0.46~0.62，导致大量日常对话被筛掉。

### 调整（2026-06-11 已执行）

```python
# 改前
BASE = 0.4  

# 改后
BASE = 0.35
```

**效果预期**：更多日常对话能通过动态阈值存入长期记忆，主动引擎有更多素材可用。如果效果不理想可随时调回。

---

> 记录：亚托莉 (Atri)
> 2026-06-11


---

# 🆕 增量更新 2026-06-11（第三次）— VAD 有向图记忆引擎沙盒实验

> 本次对 VAD 情感记忆引擎进行了全天候实验调试，从 BGE 模型加载到有向图遗忘再到概率云检索，完成了核心机制验证。

---

## 一、实验环境

**沙盒目录**: `F:\\VAD-Memory-Sandbox/`
- `engine.py` — VAD引擎核心（V0.3）
- `simulate.py` — 模拟器（含时间比例分配+动作过滤）
- `visualize.py` — 可视化（3D VAD空间+演化图）
- `.venv_gpu/` — GPU环境（Python 3.13, torch 2.6.0+cu124）
- **GPU**: NVIDIA RTX 4060（8GB），BGE 单次 encode ~20ms

## 二、实验历程

### V0→V7：BGE 模型加载问题
| 版本 | 问题 | 解决 |
|:----|:-----|:------|
| V0-V2 | VAD 全零 | device="cuda" 但无CUDA |
| V3-V4 | 还是全零 | `__pycache__` 旧缓存 |
| V5 | CPU正常了 | torch<2.6, transformers拒绝 |
| V6-V7 | GPU成功 | cu124 + RTX 4060，VAD 93.5%非零 |

### V8：方向不对称遗忘
```python
DIRECTION_FACTORS = {"tip": 0.6, "head": 1.5, "mid": 1.0}
# 末端(最近状态)：遗忘慢；起点(起因)：遗忘快
```
**效果**: 遗忘从4→53（↑13倍），情感分布更多样

### V9-V10：概率云检索 + 动作过滤
- **概率云检索**: VAD高斯采样 + 访问频率加权
- **动作过滤**: 正则删除（...）中文括号内的动作描述
- **虚拟时间戳**: 前20%在30天前，中间60%在7天内，后20%在今天

## 三、当前瓶颈

1. **链数过多**（85~185条/200条数据）— 三重约束时间权重(0.3)过高，VAD区分度不够
2. **情感偏中性** — 实验数据为工作对话，本身情绪波动小
3. **可视化锚点无势力范围** — 需加Voronoi区域

## 四、方向探索

| 方向 | 状态 | 结论 |
|:----|:----|:------|
| BGE精度优化 | ✅ 已完成 | 模型够用，环境问题已解决 |
| 有向图+方向遗忘 | ✅ 验证有效 | 头快尾慢，符合认知 |
| 概率云检索 | ✅ 代码已加 | 待集成测试 |
| 原子模型(锚点=核,链=电子云) | ❓ 暂搁置 | 太前沿，无工程参考 |
| 物理场(情感势能/电荷) | ❓ 待思考 | 需进一步设计 |

## 五、参考项目

| 项目 | 参考点 |
|:----|:-------|
| **shodh-memory** | Hebbian学习 + L1/L2/L3三层边 + 扩散激活 |
| **Graphiti** | 时序知识图谱 + 实体消歧 |
| **EverMind** | 实体-关系-时间图结构 |

## 六、待办

| 优先级 | 事项 |
|:------:|:------|
| 🔴 高 | 链匹配阈值调优（降低时间权重，调低0.65阈值） |
| 🔴 高 | Voronoi情感区域可视化 |
| 🟡 中 | 概率云检索实测对接 |
| 🟡 中 | 方向不对称遗忘移植到 `ebbinghamus.py` |
| 🟢 低 | GPU加速环境持续维护 |

> 实验记录：亚托莉 (Atri) | 2026-06-11
> 环境：F:\\VAD-Memory-Sandbox\\.venv_gpu（Python 3.13, torch 2.6.0+cu124, RTX 4060）
