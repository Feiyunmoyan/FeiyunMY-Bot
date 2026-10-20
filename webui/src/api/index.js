// ==========================================
// 📁 文件管理 API
// ==========================================
export const filesApi = {
  list: () => api.get('/files'),
  upload: async (file) => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await fetch('/api/files/upload', { method: 'POST', body: formData })
    if (!res.ok) throw new Error(`上传失败: ${res.status}`)
    return res.json()  // { file_id: "xxx.txt" }
  },
  delete: (name) => api.del(`/files/${name}`),
}/**
 * API 请求封装
 * 所有请求都基于相对路径 /api，由 Vite 代理转发
 */

const BASE_URL = '/api'

async function request(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    },
    ...options
  }

  if (config.body && typeof config.body === 'object') {
    config.body = JSON.stringify(config.body)
  }

  try {
    const response = await fetch(url, config)
    
    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`API Error ${response.status}: ${errorText}`)
    }

    // 检查是否是 SSE 响应
    const contentType = response.headers.get('content-type')
    if (contentType && contentType.includes('text/event-stream')) {
      return response
    }

    // 处理空响应
    const text = await response.text()
    return text ? JSON.parse(text) : null
  } catch (error) {
    console.error(`[API] ${options.method || 'GET'} ${url} failed:`, error)
    throw error
  }
}

// 快捷方法
const api = {
  get: (endpoint, params = {}) => {
    const query = new URLSearchParams(params).toString()
    const url = query ? `${endpoint}?${query}` : endpoint
    return request(url, { method: 'GET' })
  },
  
  post: (endpoint, body = {}) => request(endpoint, { method: 'POST', body }),
  
  put: (endpoint, body = {}) => request(endpoint, { method: 'PUT', body }),
  
  del: (endpoint) => request(endpoint, { method: 'DELETE' }),
}

// ==========================================
// 💬 对话 API
// ==========================================
export const chatApi = {
  // 非流式对话
  send: (message, sessionId, fileIds) => 
    api.post('/chat', { message, session_id: sessionId, ...(fileIds?.length ? { file_ids: fileIds } : {}) }),
  
  // 流式对话 (SSE)
  sendStream: (message, sessionId, fileIds) => 
    request('/chat/stream', { method: 'POST', body: { message, session_id: sessionId, ...(fileIds?.length ? { file_ids: fileIds } : {}) } }),
}

// ==========================================
// ⚙️ 配置 API
// ==========================================
export const configApi = {
  get: () => api.get('/config'),
  update: (data) => api.post('/config', data),
  reload: () => api.post('/config/reload'),
}

// ==========================================
// 👤 人格 API
// ==========================================
export const personaApi = {
  list: () => api.get('/personas'),
  get: (name) => api.get(`/personas/${name}`),
  create: (data) => api.post('/personas', data),
  update: (name, data) => api.put(`/personas/${name}`, data),
  delete: (name) => api.del(`/personas/${name}`),
  activate: (name) => api.post(`/personas/${name}/activate`),
  reload: () => api.post('/personas/reload'),
}

// ==========================================
// 📝 会话 API
// ==========================================
export const sessionApi = {
  list: () => api.get('/sessions'),
  create: (name) => api.post('/sessions', { name }),
  rename: (id, name) => api.put(`/sessions/${id}`, { name }),
  delete: (id) => api.del(`/sessions/${id}`),
  getMessages: (id) => api.get(`/sessions/${id}/messages`),
  autoName: (id) => api.post(`/sessions/${id}/autoname`),
}

// ==========================================
// 🧠 记忆 API
// ==========================================
export const memoryApi = {
  list: (page = 1, pageSize = 20) => 
    api.get('/memories', { page, page_size: pageSize }),
  delete: (id) => api.del(`/memories/${id}`),
  clear: () => api.post('/memories/clear'),
  toggle: (enabled) => api.post('/memory/toggle', { enabled }),
  switchMode: (mode) => api.post('/memory/switch', { mode }),
}

// ==========================================
// 🔌 MCP API
// ==========================================
export const mcpApi = {
  list: () => api.get('/mcp/servers'),
  create: (data) => api.post('/mcp/servers', data),
  update: (name, data) => api.put(`/mcp/servers/${name}`, data),
  delete: (name) => api.del(`/mcp/servers/${name}`),
}

// ==========================================
// 🧩 Skills API
// ==========================================
export const skillsApi = {
  list: () => api.get('/skills'),
  create: (data) => api.post('/skills', data),
  update: (name, data) => api.put(`/skills/${name}`, data),
  delete: (name) => api.del(`/skills/${name}`),
  upload: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request('/skills/install/upload', { 
      method: 'POST', 
      body: formData,
      headers: {} // 让浏览器自动设置 Content-Type
    })
  },
}

// ==========================================
// 🔍 搜索引擎 API
// ==========================================
export const searchApi = {
  list: () => api.get('/search/engines'),
  create: (data) => api.post('/search/engines', data),
  update: (name, data) => api.put(`/search/engines/${name}`, data),
  delete: (name) => api.del(`/search/engines/${name}`),
}

// ==========================================
// 💻 Shell 白名单 API
// ==========================================
export const shellApi = {
  list: () => api.get('/shell/whitelist'),
  addCommand: (command) => api.post('/shell/whitelist/commands', { command }),
  deleteCommand: (cmd) => api.del(`/shell/whitelist/commands/${cmd}`),
  toggle: (enabled) => api.put('/shell/whitelist/toggle', { enabled }),
}

// ==========================================
// 🤖 Provider API
// ==========================================
export const providerApi = {
  test: (data) => api.post('/provider/test', data),
  getModels: (data) => api.post('/provider/models', data),
}

// ==========================================
// 🛠️ 工具 & 统计 API
// ==========================================
export const toolsApi = {
  toggle: (name, enabled) => api.post('/tools/toggle', { name, enabled }),
}

export const statsApi = {
  get: () => api.get('/stats'),
  getSystem: () => api.get('/system/stats'),
}

// ==========================================
// 📋 日志 API
// ==========================================
export const logsApi = {
  get: (params = {}) => api.get('/logs', params),
}

// ==========================================
// 🔌 提供商管理 API
// ==========================================
export const providerMgmtApi = {
  list: () => api.get('/providers'),
  save: (data) => api.post('/providers', data),
  switch: (providerId) => api.post('/providers/switch', { provider_id: providerId }),
}

