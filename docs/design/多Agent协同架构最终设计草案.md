# 🧠 多 Agent 协同架构 — 最终设计草案

> 基于 FeiyunMY-Bot 项目扩展，整合全部 20 个问题的解决方案
> 版本：v1.0 ｜ 日期：2026-06-02

---

## 一、架构总览

```
                        🧑 用户
                        │  ↕ 无 @ → 主脑
                        │
              ┌─────────┴─────────┐
              │  🧠 主脑（绯璃）    │ ← 项目经理 + 主动引擎
              │  + 🔔 主动引擎     │ ← 定时/记忆/监控触发
              └─────────┬─────────┘
                        │ @主脑（子Agent汇报）
                        │
      ┌─────────────────┼─────────────────┐
      │                 │                 │
      │ @code           │ @design         │ @test
      ▼                 ▼                 ▼
  ┌────────┐      ┌────────┐      ┌────────┐
  │ 💻 Code │      │ 🎨 Des │      │ 🧪 Test │
  │ Agent   │      │ Agent  │      │ Agent   │
  ├────────┤      ├────────┤      ├────────┤
  │独立人格  │      │独立人格  │      │独立人格  │
  │独立记忆  │      │独立记忆  │      │独立记忆  │
  │知识库📚  │      │知识库📚  │      │知识库📚  │
  │独立模型  │      │独立模型  │      │独立模型  │
  │独立APIKey│      │独立APIKey│      │独立APIKey│
  └────────┘      └────────┘      └────────┘
       │              │              │
       │   也可以互相 @               │
       └──────────────┼──────────────┘
                      │
              ┌───────┴───────┐
              │  📋 工作空间    │ ← 独立房间 + 持久化
              │  data/workspaces/ │ ← 断电可恢复
              └───────────────┘
```

### 核心规则

| 场景 | 交互方式 | 说明 |
|:----|:--------|:-----|
| 🧑 用户聊天 | 直接发消息 | 自动路由到主脑，不需要 `@` |
| 🧑 找特定 Agent | `@code 帮我写登录页` | `@` 必须在**消息开头**才算路由 |
| 🤖 Agent 汇报 | `@主脑 任务完成` | Agent 干完了，切回主脑审核 |
| 🤖 Agent 间协作 | `@design 我需要你设计这个组件` | 多边形网状结构，任意节点互通 |
| 🧑 中途介入 Agent | `@code 颜色改一下` | 直接在 code_agent 会话里回复 |
| 🔔 主动推送 | SSE 长连接 | 主动引擎推送给用户 |

### `@` 路由解析规则

```python
def parse_route(message: str) -> tuple:
    """返回 (agent_name, actual_content) 或 (None, message)"""
    if message.startswith("@"):
        parts = message[1:].split(" ", 1)
        agent_name = parts[0]
        content = parts[1] if len(parts) > 1 else ""
        return agent_name, content
    return None, message
```

- `@` 必须在消息**开头**才算路由指令
- `user@example.com` → 正常文本，不影响
- Agent 如需 @ 别人，约定放开头或用换行

---

## 二、组件设计

### 2.1 🧠 主脑（绯璃）

- **就是系统现有的 AI**，人格和模型本来就是可配置的（config.yaml 可切换）
- 用户直接发消息 = 和主脑聊天，不需要 `@`
- 用户提出做项目时（如"做个博客网站"），主脑调用 `create_workspace` 工具创建空间
- 拆解完任务先问用户确认，再派发给子 Agent，避免拆错返工
- 拥有最终仲裁权，子Agent冲突时主脑拍板，拿不准再问用户

### 2.2 🤖 子 Agent 池

每个子 Agent 拥有独立的：
- **人格** — 从已有的人格预设中选择
- **长期记忆** — 专属 ChromaDB collection，领域经验积累
- **知识库** — 可挂载专属文档（可选）
- **模型** — 从已有的模型提供商中选择
- **API Key** — 可配置独立 Key，实现真正并行
- **工具白名单** — `file_ops` 限定只能访问所属工作空间目录

取名规则：不能和主脑重名，不能和其他 Agent 重名。

### 2.3 🔀 对话路由器（原 API 分发器）

解析 `@` 前缀，路由到目标 Agent 的会话，加载其配置（模型/人格/记忆/知识库）。

| 消息来源 | 路由目标 |
|:--------|:---------|
| 用户消息（无 @） | 主脑 |
| 用户消息（@code） | code_agent |
| Agent 消息（@主脑） | 主脑 |
| Agent 消息（@design） | design_agent |

**并发策略**：默认并行调用，LLM API 本身支持并发。各 Agent 可配独立 API Key。遇到 Rate Limit 时自动降级为排队+重试。

### 2.4 📋 工作空间

**文件目录**：
```
data/workspaces/{workspace_id}/
├── workspace.json       # 工作空间状态（原子写入）
├── output/              # 子 Agent 输出的文件
│   ├── code/            # code_agent 生成的文件
│   └── design/          # design_agent 生成的文件
└── sessions/            # Agent 对话历史（引用 SQLite）
```

**数据模型**：
```python
workspace = {
    "workspace_id": "uuid",
    "name": "博客项目",
    "status": "active",        # active / paused / completed / failed
    "created_at": "timestamp",
    "updated_at": "timestamp",
    "agents": [
        {"agent_ref_id": "code_001", "name": "code", "status": "done"}
    ],
    "tasks": [
        {"task_id": "t001", "agent": "code", "description": "...",
         "status": "done", "depends_on": []}
    ],
    "token_usage": 120000       # 累计 Token 消耗
}
```

**持久化策略**：
- 每次状态变化 → 原子写入 `workspace.json`（`.tmp` + `os.replace`）
- 对话历史 → SQLite `data/feiyun.db`（已有）
- 重启恢复 → 扫描 workspace 目录，active 中有任务的标记为 paused，通知用户

**数据生命周期**：
- 工作空间删除 → 临时上下文消失（会话历史、进度）
- Agent 配置不删 → 长期记忆独立保留（下次用还能想起来）
- Agent 配置删除 → 长期记忆可选清理

### 2.5 🔔 主动引擎

**三引擎驱动**：
- **⏰ 定时引擎** — 主人设的提醒、定时任务
- **🧠 记忆引擎** — ChromaDB 查询待跟进话题，标记未完结的对话
- **📊 监控引擎** — 系统资源监控、Agent 进度、Token 消耗

**消息分类**：
```
所有消息
├─ 📨 用户主动发的 → 不参与推送统计
├─ 🛎️ 系统事件（不调LLM）
│   ├─ 🔴 紧急通知（磁盘满了）→ 立即推
│   ├─ 🟡 定时提醒（喝水时间）→ 该推就推
│   └─ 📬 Agent完成通知 → 推
│
└─ 💬 AI主动聊天（调LLM，计入推送统计）
    ├─ 🧠 记忆跟进（"团子好点了吗"）
    ├─ ☀️ 日常问候（"主人今天心情如何"）
    └─ 💭 话题延伸（"上次说的那个……"）
```

**打扰指数算法**：
```python
def 打扰指数(键盘频率, cpu占用, gpu占用, 屏幕聚焦, 时段):
    输入分 = 1.0 - min(键盘频率 / 100, 1.0)
    负载分 = 1.0 - max(cpu占用, gpu占用) / 100
    焦点分 = 1.0 if 屏幕聚焦 else 0.3
    时段权重 = {
        "深夜(23-8)": 0.1, "工作时间(9-18)": 0.6, "休息时间(18-23)": 0.8
    }
    return (输入分 * 0.3 + 负载分 * 0.3 + 焦点分 * 0.2) * 时段权重
```

**话痨模式开关**（用户主动设定）：
| 档位 | 触发门槛 | 说明 |
|:----:|:-------:|:------|
| 🗣️ 高 | ≥ 0.3 | 想有人陪的时候 |
| 🙆 中 | ≥ 0.5 | 默认 |
| 🤫 低 | ≥ 0.7 | 专注工作时 |
| 🔇 关 | — | 仅紧急推送 |

**自适应学习**：只统计 `AI主动聊天` 类型的回应率，关机时存 `active_params.json`，慢速融合保存（旧×0.7 + 新×0.3）。

---

## 三、边界与容错机制

### 3.1 Agent 间循环对话 — 三层漏斗

| 层级 | 条件 | 处理 |
|:---:|:----|:-----|
| 🟢 Agent 间 | ≤ 6 轮 | 正常沟通 |
| 🟡 主脑介入 | > 6 轮 | 主脑分析分歧，尝试协调，最多 3 次 |
| 🔴 用户拍板 | 主脑 3 次失败 | 推送给用户，一句话定乾坤 |

同一对 Agent `一问一答算一轮`，超过 6 轮触发。

### 3.2 服务熔断与降级

| 层 | API 挂了 | 行为 |
|:--|:--------|:-----|
| 🧠 主脑 | DeepSeek 断连 | 本地回复："主人我现在连不上大脑了~"，服务恢复后自动切回 |
| 🤖 子Agent | DeepSeek 断连 | 工作空间标记 paused，安静等待 |
| 🔄 恢复 | 定期探测（30s） | 恢复后主动通知用户 |

### 3.3 文件权限沙箱

- `file_ops` 等工具限定目录 `data/workspaces/{项目名}/`
- 无法越界访问其他空间或系统文件
- 代码执行限制超时和内存

### 3.4 API 费用管控

- **流程控制**：提示词约束"每完成一个文件必须 @主脑 检查"
- **软提醒**：每 20 万 token 主动推送一次消耗报告
- **主动引擎费用**：由话痨模式 + 自适应算法自然约束

---

## 四、通信方式

### 4.1 对话通信（已有）

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `POST` | `/api/chat` | 非流式对话 |
| `POST` | `/api/chat/stream` | 流式对话（SSE） |

### 4.2 主动推送（新增）

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `GET` | `/api/events` | SSE 长连接，后端主动推送给前端 |
| `GET` | `/api/active/messages?since={时间戳}` | 前端断连后拉取补漏 |

### 4.3 用户状态上报（新增）

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `POST` | `/api/user/status` | 前端每 30 秒上报键盘频率/页面焦点/系统负载 |

---

## 五、后端 API 端口设计

> 以下为前端提供完整的管理能力，前端可基于这些端口构建配置菜单、工作空间面板等。

### 5.1 🤖 Agent 配置管理

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `GET` | `/api/agents` | 列出所有已注册的 Agent 配置 |
| `POST` | `/api/agents` | 创建新 Agent 配置（含重名检测） |
| `GET` | `/api/agents/{id}` | 查看单个 Agent 详情 |
| `PUT` | `/api/agents/{id}` | 更新 Agent 配置 |
| `DELETE` | `/api/agents/{id}` | 删除 Agent 配置 |

**Agent 配置模型**：
```json
{
    "agent_id": "code_001",
    "name": "code",
    "display_name": "程序员助手",
    "description": "擅长编写前端代码",
    "avatar": "💻",
    "model_id": "deepseek-chat",
    "api_key_id": "key_001",
    "persona_id": "code_assistant",
    "knowledge_base_id": "tech_docs",
    "memory_enabled": true,
    "max_tokens": 4096,
    "temperature": 0.7,
    "tools_enabled": ["code_exec", "file_ops"]
}
```

### 5.2 📋 工作空间管理

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `GET` | `/api/workspaces` | 列出所有工作空间 |
| `POST` | `/api/workspaces` | 创建新工作空间 |
| `GET` | `/api/workspaces/{id}` | 查看工作空间详情（含状态/进度/Token消耗） |
| `PUT` | `/api/workspaces/{id}` | 更新工作空间（含关闭/归档） |
| `DELETE` | `/api/workspaces/{id}` | 删除工作空间（清理会话+文件） |
| `GET` | `/api/workspaces/{id}/agents` | 工作空间内各 Agent 状态 |
| `POST` | `/api/workspaces/{id}/assign` | 向工作空间内 Agent 派发任务 |
| `GET` | `/api/workspaces/{id}/logs` | 按 Agent 筛选对话日志（支持 `?agent=code`） |
| `GET` | `/api/workspaces/{id}/files` | 列出工作空间输出文件 |

### 5.3 🧩 模型与 API Key 管理

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `GET` | `/api/providers` | 列出所有模型提供商 |
| `POST` | `/api/providers` | 添加提供商 |
| `PUT` | `/api/providers/{id}` | 更新提供商 |
| `DELETE` | `/api/providers/{id}` | 删除提供商 |
| `POST` | `/api/providers/{id}/test` | 测试连接 |

### 5.4 👤 人格管理（复用已有）

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `GET` | `/api/personas` | 列出所有人格预设 |
| `POST` | `/api/personas` | 创建人格 |
| `PUT` | `/api/personas/{id}` | 更新人格 |
| `DELETE` | `/api/personas/{id}` | 删除人格 |

### 5.5 📚 知识库管理

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `GET` | `/api/knowledge_bases` | 列出所有知识库 |
| `POST` | `/api/knowledge_bases` | 创建知识库 |
| `GET` | `/api/knowledge_bases/{id}` | 查看知识库详情 |
| `DELETE` | `/api/knowledge_bases/{id}` | 删除知识库 |
| `POST` | `/api/knowledge_bases/{id}/upload` | 上传文档 |

### 5.6 ⚙️ 主动引擎配置

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `GET` | `/api/active/config` | 获取主动引擎配置（话痨模式/免打扰时段/自适应参数） |
| `PUT` | `/api/active/config` | 更新主动引擎配置 |
| `GET` | `/api/active/stats` | 主动推送统计数据（推送次数/回应率/费用等） |

### 5.7 📊 系统监控

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `GET` | `/api/system/stats` | 系统资源（CPU/内存/磁盘/运行时间） |

---

## 六、前端设计思路（简）

前端仅需关注以下核心页面，后端端口已预留：

| 页面 | 对应 API | 核心功能 |
|:----|:---------|:---------|
| 💬 **对话页** | `/api/chat/stream` + `/api/events` | 主脑聊天、接收主动推送 |
| 🤖 **子 Agent 管理** | `/api/agents` | 列表/创建/编辑，模型/人格/知识库下拉选择 |
| 📋 **工作空间** | `/api/workspaces/*` | 独立房间，状态面板+消息筛选+文件预览 |
| 🧩 **模型管理** | `/api/providers` | 模型提供商 CRUD |
| 👤 **人格管理** | `/api/personas` | 人格 CRUD |
| 📚 **知识库管理** | `/api/knowledge_bases` | 知识库 CRUD + 文档上传 |
| ⚙️ **主动引擎设置** | `/api/active/config` | 话痨模式开关、免打扰时段 |

**设计思路**：工作空间作为独立"房间"，从菜单进入后有顶部概览（消息数/Token/Agent状态）+ 左侧菜单（首页/消息/文件/设置）+ 右侧主内容区（消息栏带 Agent 筛选器）。

---

## 七、后端实现要点

### 7.1 需要新增的模块

```
F:\FeiyunMY-Bot\
├── workspace/                     # 【新增】工作空间系统
│   ├── manager.py                 # CRUD + 持久化 + 状态恢复
│   └── router.py                  # @ 路由逻辑
├── agent/                         # 【新增】子 Agent 管理
│   └── config_manager.py          # Agent 配置 CRUD + 重名检测
├── active_engine/                 # 【新增】主动引擎
│   ├── scheduler.py               # 后台调度器（三引擎）
│   ├── disturbance.py             # 打扰指数算法
│   ├── adaptive.py                # 自适应学习
│   └── push.py                    # SSE 推送 + 消息持久化
├── api/
│   ├── agents.py                  # 【新增】Agent 管理接口
│   ├── workspaces.py              # 【新增】工作空间接口
│   ├── active.py                  # 【新增】主动引擎接口
│   └── user_status.py             # 【新增】用户状态上报
├── tools/
│   ├── workspace_tools.py         # 【新增】create_workspace 等工具
│   └── agent_tools.py             # 更新已有工具（加权限沙箱）
└── data/
    └── workspaces/                # 【新增】工作空间数据目录
```

### 7.2 需要修改的现有模块

| 模块 | 修改内容 |
|:----|:---------|
| `tools/agent_tools.py` | `file_ops` 加工作空间目录沙箱限制 |
| `agent/runner.py` | `build_messages` 支持加载子Agent配置（模型/人格/记忆/知识库） |
| `provider/` | 支持多 API Key 并行调用 |
| `memory/backends/memoria/` | ChromaDB 引用计数 + 懒加载 |
| `persona/manager.py` | 保持现状（已有接口满足需求） |

### 7.3 ChromaDB 引用计数机制

```python
class ChromaDBManager:
    def __init__(self):
        self.collections = {}       # collection_name -> ref_count
        self.active = {}            # collection_name -> instance
    
    def acquire(self, agent_name):
        """引用 +1，首次使用时加载"""
        if agent_name not in self.collections:
            self.collections[agent_name] = 0
            # 从磁盘加载
            self.active[agent_name] = self._load(agent_name)
        self.collections[agent_name] += 1
    
    def release(self, agent_name):
        """引用 -1，归零时卸载"""
        self.collections[agent_name] -= 1
        if self.collections[agent_name] <= 0:
            self.active[agent_name].close()
            del self.active[agent_name]
```

主脑的 ChromaDB 启动时加载，引用计数永久 +1，常驻内存。

---

## 八、实现路线图

| 阶段 | 内容 | 依赖 | 预估 |
|:----|:------|:----|:----:|
| **Phase 1** | 🗂️ 工作空间系统：`workspace/manager.py` + `workspace/router.py` + CRUD API | 无 | 2-3天 |
| **Phase 2** | 🤖 Agent 配置管理：`agent/config_manager.py` + `api/agents.py` + 重名检测 | 无 | 2天 |
| **Phase 3** | 🔀 `@` 路由集成：修改 `agent/runner.py` 支持子Agent配置加载 + 权限沙箱 | Phase 1, 2 | 2天 |
| **Phase 4** | 🔔 主动引擎：`active_engine/scheduler.py` + `disturbance.py` + `push.py` + SSE | 无 | 2-3天 |
| **Phase 5** | 🧠 ChromaDB 引用计数 + 懒加载 | 无 | 1天 |
| **Phase 6** | 🧩 知识库 + API Key + 自适应 + 熔断等补充功能 | Phase 1~5 | 2天 |
| **Phase 7** | 🧪 集成测试 + 边界情况处理 + 最终文档 | Phase 1~6 | 2天 |

---

> 拟定：亚托莉 (Atri)
> 审核：绯璃 (FY-01)
> 2026-06-02 v1.0
