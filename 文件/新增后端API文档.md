# FeiyunMY-Bot 新增后端 API 文档

> 基于原项目扩展的新增 API，前端可基于此文档对接
> 时间：2026-06-02

---

## 📋 工作空间管理

### 基础 CRUD

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `GET` | `/api/workspaces` | 列出所有工作空间（支持 `?status=active` 筛选） |
| `POST` | `/api/workspaces` | 创建工作空间 |
| `GET` | `/api/workspaces/{id}` | 查看工作空间详情 |
| `PUT` | `/api/workspaces/{id}` | 更新工作空间（修改名称/描述/状态等） |
| `DELETE` | `/api/workspaces/{id}` | 删除工作空间（支持 `?cleanup=true` 控制是否清理文件） |
| `GET` | `/api/workspaces/{id}/stats` | 获取工作空间统计（任务数/Agent数/Token等） |

**POST /api/workspaces 请求体：**
```json
{
    "name": "博客项目",
    "description": "做一个个人博客网站",
    "shared_context": {"tech_stack": "Vue + FastAPI"},
    "agents": [{"name": "code", "agent_ref_id": ""}, {"name": "design", "agent_ref_id": ""}]
}
```

**GET /api/workspaces/{id}/stats 返回：**
```json
{
    "stats": {
        "name": "博客项目",
        "status": "active",
        "total_tasks": 3,
        "done_tasks": 1,
        "pending_tasks": 1,
        "working_tasks": 1,
        "failed_tasks": 0,
        "total_agents": 2,
        "active_agents": 1,
        "token_usage": 120000,
        "created_at": 1748822400,
        "updated_at": 1748822400
    }
}
```

### 工作空间内的任务管理

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `GET` | `/api/workspaces/{id}/tasks` | 列出任务（支持 `?status=done` 筛选） |
| `POST` | `/api/workspaces/{id}/tasks` | 添加任务 |
| `PUT` | `/api/workspaces/{id}/tasks/{task_id}` | 更新任务状态 |

**POST /api/workspaces/{id}/tasks 请求体：**
```json
{
    "agent": "code",
    "description": "用Vue搭建前端框架",
    "depends_on": []
}
```

**PUT /api/workspaces/{id}/tasks/{task_id} 请求体：**
```json
{
    "status": "done",
    "result": "已完成前端框架搭建"
}
```

### 工作空间内的 Agent 管理

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `GET` | `/api/workspaces/{id}/agents` | 查看工作空间内的 Agent 状态列表 |
| `POST` | `/api/workspaces/{id}/agents` | 向工作空间添加 Agent |
| `PUT` | `/api/workspaces/{id}/agents/{name}` | 更新工作空间内 Agent 的状态 |

**PUT /api/workspaces/{id}/agents/{name} 请求体：**
```json
{
    "status": "done",
    "progress": "首页设计完成，正在做详情页",
    "result_summary": "已完成UI设计"
}
```

---

## 🤖 子 Agent 配置管理

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `GET` | `/api/agents` | 列出所有已注册的 Agent 配置 |
| `POST` | `/api/agents` | 创建新 Agent 配置（含重名检测） |
| `GET` | `/api/agents/{id}` | 查看单个 Agent 详情 |
| `PUT` | `/api/agents/{id}` | 更新 Agent 配置 |
| `DELETE` | `/api/agents/{id}` | 删除 Agent 配置 |
| `GET` | `/api/agents/names` | 获取所有 Agent 名称列表（供前端下拉选择） |

**POST /api/agents 请求体（创建 Agent）：**
```json
{
    "name": "code",
    "display_name": "程序员助手",
    "description": "擅长编写前端代码",
    "avatar": "💻",
    "model_id": "deepseek-chat",
    "persona_id": "code_assistant",
    "knowledge_base_id": "tech_docs",
    "memory_enabled": true,
    "max_tokens": 4096,
    "temperature": 0.7,
    "tools_enabled": ["code_exec", "file_ops"]
}
```

**Agent 配置模型说明：**
| 字段 | 类型 | 说明 |
|:----|:----|:------|
| `name` | string | Agent 名称（用于 @ 路由，唯一，不能和主脑重名） |
| `display_name` | string | 显示名称 |
| `model_id` | string | 引用的模型 ID（从已有模型中下拉选择） |
| `persona_id` | string | 引用的角色人格 ID（从已有预设中下拉选择） |
| `knowledge_base_id` | string | 引用的知识库 ID（从已有知识库中下拉选择，可选） |
| `memory_enabled` | bool | 是否启用长期记忆 |
| `tools_enabled` | array | 启用的工具列表 |

---

## 🔔 主动引擎

### SSE 推送

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `GET` | `/api/events` | SSE 长连接，后端主动推送给前端 |
| `GET` | `/api/active/messages?since={timestamp}` | 获取历史推送消息（断连补推） |

**SSE 消息格式**（`/api/events` 推送的事件）：
```json
// 每条 SSE 消息的 data 字段
{
    "id": "a1b2c3d4e5f6",
    "content": "主人，code_agent 在博客项目中的任务已完成~",
    "type": "active_push",     // active_push / system_event / agent_report
    "priority": "important",   // urgent / important / normal / low
    "source": "Agent进度",
    "store_policy": "ephemeral",  // ephemeral / memorable
    "created_at": 1748822400
}
```

**前端 SSE 监听示例**：
```javascript
const eventSource = new EventSource('/api/events');
eventSource.onmessage = (e) => {
    const data = JSON.parse(e.data);
    // data.type 判断消息类型
    // data.priority 判断优先级
    // data.content 显示消息内容
};
```

### 用户状态上报

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `POST` | `/api/user/status` | 前端每 30 秒上报用户状态 |

**POST /api/user/status 请求体：**
```json
{
    "keyboard_freq": 0.0,
    "cpu_usage": 0.0,
    "gpu_usage": 0.0,
    "screen_focused": true
}
```

### 主动引擎配置

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `GET` | `/api/active/config` | 获取主动引擎配置 |
| `PUT` | `/api/active/config` | 更新主动引擎配置 |
| `GET` | `/api/active/stats` | 获取主动推送统计 |

**PUT /api/active/config 请求体：**
```json
{
    "chatter_mode": "medium",
    "quiet_hours_start": 23,
    "quiet_hours_end": 8
}
```
`chatter_mode` 可选值：`high`（话痨） / `medium`（适中） / `low`（安静） / `off`（关闭）

---

## 📚 知识库管理

### 知识库 CRUD

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `GET` | `/api/knowledge_bases` | 列出所有知识库 |
| `POST` | `/api/knowledge_bases` | 创建知识库 |
| `GET` | `/api/knowledge_bases/{id}` | 查看知识库详情 |
| `PUT` | `/api/knowledge_bases/{id}` | 更新知识库 |
| `DELETE` | `/api/knowledge_bases/{id}` | 删除知识库 |

**POST /api/knowledge_bases 请求体：**
```json
{
    "name": "Vue技术文档",
    "description": "Vue 3 官方文档摘要",
    "tags": ["前端", "Vue"]
}
```

### 文档管理

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `GET` | `/api/knowledge_bases/{id}/documents` | 列出知识库中的文档 |
| `POST` | `/api/knowledge_bases/{id}/upload` | 上传文档到知识库（multipart/form-data） |
| `GET` | `/api/knowledge_bases/{id}/documents/{doc_id}` | 获取文档内容 |
| `DELETE` | `/api/knowledge_bases/{id}/documents/{doc_id}` | 删除文档 |
| `GET` | `/api/knowledge_bases/{id}/search?keyword=xxx` | 搜索知识库中的文档 |

**POST /api/knowledge_bases/{id}/upload：**
```
Content-Type: multipart/form-data
参数: file (文件)
```

---

## 系统监控

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `GET` | `/api/system/stats` | 系统资源（已有接口，新增工作空间统计集成） |

---

## 已有接口（参考）

以下接口在原有项目中已存在，也可能会用到：

| 方法 | 端点 | 说明 |
|:----|:-----|:------|
| `POST` | `/api/chat` | 非流式对话 |
| `POST` | `/api/chat/stream` | 流式对话（SSE） |
| `GET` | `/api/personas` | 列出人格预设 |
| `POST` | `/api/personas` | 创建人格 |
| `GET` `/PUT` `DELETE` | `/api/personas/{id}` | 人格 CRUD |
| `GET` | `/api/provider/models` | 获取模型列表 |
| `POST` | `/api/provider/test` | 测试 API 连接 |

---

## 前端需要新增的页面与对接建议

| 页面 | 主要 API | 说明 |
|:----|:---------|:------|
| 💬 **对话页** | `/api/chat/stream` + `/api/events` | 主脑聊天 + SSE 接收主动推送 |
| 🤖 **子 Agent 管理** | `/api/agents` + `/api/agents/names` | Agent 列表/创建/编辑（模型/人格/知识库下拉选择） |
| 📋 **工作空间管理** | `/api/workspaces/*` + `/api/workspaces/{id}/tasks/*` + `/api/workspaces/{id}/agents/*` | 工作空间列表/详情/任务/Agent状态 |
| 🧩 **模型管理** | `/api/providers`（已有） | 模型提供商 CRUD |
| 👤 **人格管理** | `/api/personas`（已有） | 人格 CRUD |
| 📚 **知识库管理** | `/api/knowledge_bases/*` + upload | 知识库 CRUD + 文档上传/搜索 |
| ⚙️ **主动引擎设置** | `/api/active/config` + `/api/active/stats` | 话痨模式开关 + 免打扰时段 + 统计 |

---

> 整理：亚托莉 (Atri)
