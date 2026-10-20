<template>
  <div class="panel">
    <h2 class="text-2xl font-bold text-text-primary mb-6">{{ pageTitle }}</h2>
    
    <div v-if="loading" class="flex justify-center py-12"><LoadingSpinner size="lg" /></div>
    
    <div v-else class="max-w-3xl space-y-6">
      
      <!-- 配置总览（占位，等待后续内容） -->
      <div v-if="activePanel === 'config'" class="card text-center py-16">
        <Settings class="w-16 h-16 mx-auto mb-4 text-text-disabled" />
        <h3 class="text-xl font-semibold text-text-primary mb-2">配置总览</h3>
        <p class="text-text-secondary">请从左侧子菜单中选择具体配置项</p>
      </div>
      
      <!-- ====== 普通配置 ====== -->
      <div v-if="activePanel === 'config-general'" class="card">
        <h3 class="text-lg font-semibold text-text-primary mb-4 flex items-center gap-2">
          <SlidersHorizontal class="w-5 h-5 text-primary" /> 普通配置
        </h3>
        <div class="space-y-6">
          <!-- 当前模型选择 -->
          <div>
            <label class="block text-sm text-text-secondary mb-2">当前使用的模型</label>
            <select v-model="selectedModelKey" class="input-base">
              <option value="" disabled>— 请选择模型 —</option>
              <optgroup v-for="p in providers" :key="p.id" :label="p.name || '未命名'">
                <option v-for="m in p.models" :key="p.id + '/' + m.id" :value="p.id + '/' + m.id" :disabled="!m.id">
                  {{ m.id || '（空）' }}
                </option>
              </optgroup>
            </select>
            <p class="text-xs text-text-secondary mt-1.5">
              从已配置的提供商中选择一个模型作为当前使用的模型
            </p>
          </div>
          
          <!-- 已选模型信息 -->
          <div v-if="currentSelectedModel" class="bg-bg-hover/50 rounded-lg p-3 text-sm">
            <div class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-success" />
              <span class="text-text-primary font-medium">{{ currentSelectedModel.providerName }}</span>
              <span class="text-text-secondary">/</span>
              <span class="text-text-primary">{{ currentSelectedModel.modelId }}</span>
            </div>
          </div>
          
          <!-- ====== 上下文压缩 ====== -->
          <div class="border-t border-border pt-4">
            <div class="flex items-center justify-between mb-4">
              <h4 class="text-base font-semibold text-text-primary flex items-center gap-2">
                <svg class="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7"/>
                </svg>
                上下文压缩
              </h4>
              <Toggle v-model="config.compression.enabled" />
            </div>
            
            <div v-if="config.compression.enabled" class="space-y-4 pl-2">
              <div>
                <label class="block text-sm text-text-secondary mb-1">压缩模式</label>
                <select v-model="config.compression.mode" class="input-base">
                  <option value="summarize">LLM 总结</option>
                  <option value="truncate">直接删除</option>
                </select>
              </div>
              <div>
                <label class="block text-sm text-text-secondary mb-1">压缩间隔（轮次）</label>
                <div class="flex items-center gap-3">
                  <input v-model.number="config.compression.interval" type="range" min="5" max="50" class="flex-1 accent-primary" />
                  <span class="text-sm text-text-primary font-medium w-8 text-right">{{ config.compression.interval }}</span>
                </div>
              </div>
              <div>
                <label class="block text-sm text-text-secondary mb-1">压缩模型</label>
                <select v-model="config.compression.model" class="input-base">
                  <option value="">同对话模型</option>
                  <optgroup v-for="p in providers" :key="p.id" :label="p.name || '未命名'">
                    <option v-for="m in p.models" :key="p.id + '/' + m.id" :value="m.id" :disabled="!m.id">
                      {{ m.id || '（空）' }}
                    </option>
                  </optgroup>
                </select>
              </div>
              <div v-if="config.compression.mode === 'summarize'">
                <label class="block text-sm text-text-secondary mb-1">压缩提示词</label>
                <textarea v-model="config.compression.prompt" class="input-base h-20 resize-none" placeholder="自定义 LLM 压缩时的提示词，留空使用默认提示词" />
              </div>
            </div>
            <div v-else class="text-xs text-text-secondary pl-2">
              上下文压缩已关闭，AI 对话将保留全部历史记录。
            </div>
          </div>
          
          <!-- 保存按钮（独立在压缩区块外，对整个普通配置生效） -->
          <div class="border-t border-border pt-4 flex gap-3">
            <button @click="saveGeneralConfig" class="btn-primary">保存配置</button>
          </div>
        </div>
      </div>
      
      <!-- ====== 系统配置（主动引擎） ====== -->
      <div v-if="activePanel === 'config-system'" class="card">
        <h3 class="text-lg font-semibold text-text-primary mb-4 flex items-center gap-2">
          <Monitor class="w-5 h-5 text-primary" /> 主动引擎
        </h3>
        <div class="space-y-5">
          <div>
            <label class="block text-sm text-text-secondary mb-1.5">话痨模式</label>
            <select v-model="activeConfig.chatter_mode" class="input-base">
              <option value="off">关闭</option>
              <option value="low">安静</option>
              <option value="medium">适中</option>
              <option value="high">话痨</option>
            </select>
            <p class="text-xs text-text-secondary mt-1">控制 AI 主动发起对话的频率</p>
          </div>
          
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm text-text-secondary mb-1.5">免打扰开始</label>
              <select v-model="activeConfig.quiet_hours_start" class="input-base">
                <option v-for="h in 24" :key="h" :value="h - 1">{{ String(h - 1).padStart(2, '0') }}:00</option>
              </select>
            </div>
            <div>
              <label class="block text-sm text-text-secondary mb-1.5">免打扰结束</label>
              <select v-model="activeConfig.quiet_hours_end" class="input-base">
                <option v-for="h in 24" :key="h" :value="h - 1">{{ String(h - 1).padStart(2, '0') }}:00</option>
              </select>
            </div>
          </div>
          <p class="text-xs text-text-secondary">免打扰时段内 AI 不会主动推送消息</p>
          
          <div v-if="activeStats" class="border-t border-border pt-4">
            <h4 class="text-sm font-semibold text-text-primary mb-3">推送统计</h4>
            <div class="grid grid-cols-3 gap-3 text-center text-sm">
              <div class="bg-bg-hover/50 rounded-lg p-3">
                <p class="text-lg font-bold text-primary">{{ activeStats.adaptive?.total_pushes || 0 }}</p>
                <p class="text-xs text-text-secondary">总推送</p>
              </div>
              <div class="bg-bg-hover/50 rounded-lg p-3">
                <p class="text-lg font-bold text-success">{{ formatReplyRate(activeStats.adaptive?.reply_rate) }}</p>
                <p class="text-xs text-text-secondary">回应率</p>
              </div>
              <div class="bg-bg-hover/50 rounded-lg p-3">
                <p class="text-lg font-bold" :class="activeStats.push_engine?.connected ? 'text-success' : 'text-text-disabled'">
                  {{ activeStats.push_engine?.connected ? '已连接' : '未连接' }}
                </p>
                <p class="text-xs text-text-secondary">SSE 状态</p>
              </div>
            </div>
            <div class="mt-2 text-[10px] text-text-disabled text-center">
              阈值 {{ activeStats.adaptive?.active_threshold ?? '-' }} · 队列 {{ activeStats.push_engine?.queue_size ?? 0 }}
            </div>
          </div>
          
          <div class="flex gap-3 pt-2">
            <button @click="saveActiveConfig" class="btn-primary">保存配置</button>
          </div>
        </div>
      </div>
      
      <!-- ====== 模型配置（多提供商） ====== -->
      <section v-if="activePanel === 'config-model'" class="p-0 overflow-hidden max-w-5xl">
        <!-- 顶栏 -->
        <div class="flex items-center justify-between px-4 py-3 border-b border-border bg-bg-card">
          <h3 class="text-lg font-semibold text-text-primary flex items-center gap-2">
            <Cpu class="w-5 h-5 text-primary" /> 模型配置
          </h3>
          <button @click="addProvider" class="btn-primary text-sm flex items-center gap-1">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
            </svg>
            添加提供商
          </button>
        </div>
        
        <!-- 主体：左右分栏 -->
        <div class="flex min-h-[500px]">
          <!-- 左侧：提供商列表 -->
          <div class="w-[220px] border-r border-border p-2 space-y-1 bg-bg-card/50">
            <button
              v-for="p in providers"
              :key="p.id"
              @click="selectedProviderId = p.id"
              :class="[
                'w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm transition-all text-left',
                selectedProviderId === p.id
                  ? 'bg-primary/15 text-primary font-medium'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
              ]"
            >
              <span class="w-2 h-2 rounded-full flex-shrink-0" :class="p.enabled ? 'bg-success' : 'bg-text-disabled'" />
              <span class="truncate flex-1">{{ p.name || '未命名' }}</span>
            </button>
            <div v-if="providers.length === 0" class="py-8 text-center text-text-disabled text-sm">
              暂无提供商<br>点击上方添加
            </div>
          </div>
          
          <!-- 右侧：选中提供商的配置 -->
          <div v-if="selectedProvider" class="flex-1 p-4 space-y-4 overflow-y-auto">
            <!-- 基础信息 -->
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm text-text-secondary mb-1">自定义名称</label>
                <input v-model="selectedProvider.name" class="input-base" placeholder="例如：硅基流动" />
              </div>
              <div>
                <label class="block text-sm text-text-secondary mb-1">接口类型</label>
                <select v-model="selectedProvider.type" class="input-base">
                  <option value="openai">OpenAI 兼容</option>
                  <option value="deepseek">DeepSeek</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="other">其他</option>
                </select>
              </div>
            </div>
            <div>
              <label class="block text-sm text-text-secondary mb-1">API 地址</label>
              <input v-model="selectedProvider.base_url" class="input-base" placeholder="https://api.openai.com/v1" />
            </div>
            <div>
              <label class="block text-sm text-text-secondary mb-1">API Key</label>
              <div class="relative">
                <input 
                  v-model="selectedProvider.api_key" 
                  :type="showProviderKey[selectedProvider.id] ? 'text' : 'password'"
                  class="input-base pr-10" 
                  placeholder="sk-..."
                />
                <button @click="toggleProviderKey(selectedProvider.id)" class="absolute right-3 top-1/2 -translate-y-1/2 text-text-secondary">
                  <EyeOff v-if="!showProviderKey[selectedProvider.id]" class="w-4 h-4" />
                  <Eye v-else class="w-4 h-4" />
                </button>
              </div>
            </div>
            <div class="flex items-center gap-3">
              <Toggle v-model="selectedProvider.enabled" />
              <span class="text-sm text-text-secondary">{{ selectedProvider.enabled ? '已启用' : '未启用' }}</span>
            </div>
            
            <!-- 模型列表 -->
            <div>
              <div class="flex items-center justify-between mb-2">
                <label class="text-sm text-text-secondary">模型列表</label>
                <div class="flex items-center gap-2">
                  <button @click="fetchProviderModels(selectedProvider)" class="text-xs btn-secondary py-1 px-2">获取模型</button>
                  <button @click="addModel(selectedProvider)" class="text-xs btn-primary py-1 px-2">+ 添加模型</button>
                </div>
              </div>
              <div class="space-y-1.5">
                <div v-for="(model, idx) in selectedProvider.models" :key="idx"
                  class="flex items-center gap-2 px-3 py-2 rounded-lg bg-bg-hover/50 text-sm group"
                >
                  <Toggle v-model="model.enabled" />
                  <span v-if="model.status === 'available'" class="w-1.5 h-1.5 rounded-full bg-success flex-shrink-0" />
                  <span v-else class="w-1.5 h-1.5 rounded-full bg-text-disabled flex-shrink-0" />
                  <input v-model="model.id" class="flex-1 bg-transparent border-none outline-none text-text-primary text-sm" placeholder="模型ID" />
                  <button @click="testModel(selectedProvider, idx)" class="text-xs text-info hover:underline opacity-0 group-hover:opacity-100 transition-opacity">测试</button>
                  <button @click="selectedProvider.models.splice(idx, 1)" class="text-error hover:text-error/80 opacity-0 group-hover:opacity-100 transition-opacity">✕</button>
                </div>
                <div v-if="selectedProvider.models.length === 0" class="text-xs text-text-disabled py-2">暂无模型，点击「+ 添加模型」添加</div>
              </div>
            </div>
            
            <!-- 操作按钮 -->
            <div class="flex gap-2 pt-2">
              <button @click="saveCurrentProvider" class="btn-primary text-sm">保存</button>
              <button @click="testProviderConnection(selectedProvider)" class="btn-secondary text-sm">测试连接</button>
              <button @click="removeProvider(selectedProvider.id)" class="btn-danger text-sm ml-auto">删除</button>
            </div>
          </div>
          
          <!-- 右侧空状态 -->
          <div v-else class="flex-1 flex items-center justify-center text-text-disabled text-sm">
            请从左侧选择一个提供商
          </div>
        </div>
      </section>
      
      <!-- 删除提供商确认弹窗 -->
      <ConfirmDialog 
        :show="showDeleteProviderConfirm" 
        title="删除提供商" 
        :message="`确定要删除提供商「${deleteProviderTarget}」吗？所有模型配置将一同删除，此操作不可撤销。`"
        @confirm="confirmDeleteProvider"
        @update:show="showDeleteProviderConfirm = false"
      />
      
      <!-- ====== 记忆配置 ====== -->
      <section v-if="activePanel === 'config-memory'" class="card">
        <h3 class="text-lg font-semibold text-text-primary mb-4 flex items-center gap-2">
          <Database class="w-5 h-5 text-primary" /> 记忆配置
        </h3>
        <div class="space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-text-primary font-medium">启用记忆</p>
              <p class="text-xs text-text-secondary">允许 AI 记住对话历史，关闭后为 Simple 模式</p>
            </div>
            <Toggle :modelValue="config.memory.enabled" @update:modelValue="toggleMemory" />
          </div>
          <div class="flex items-center gap-2 px-3 py-2 rounded-lg bg-bg-hover/50">
            <span class="w-2 h-2 rounded-full" :class="config.memory.enabled ? 'bg-success' : 'bg-text-disabled'" />
            <span class="text-sm text-text-primary font-medium">{{ config.memory.enabled ? 'Memoria' : 'Simple' }}</span>
            <span class="text-xs text-text-secondary ml-auto">{{ config.memory.enabled ? '向量数据库 + 情感分析 + 艾宾浩斯遗忘' : '关键词匹配 + JSON 文件持久化' }}</span>
          </div>
        </div>
      </section>
      
      <!-- ====== 工具配置 ====== -->
      <section v-if="activePanel === 'config-tools'" class="card p-0 overflow-hidden">
        <div class="px-4 py-3 border-b border-border">
          <h3 class="text-lg font-semibold text-text-primary flex items-center gap-2">
            <Wrench class="w-5 h-5 text-primary" /> 工具配置
          </h3>
        </div>
        <div class="divide-y divide-border">
          <div v-for="tool in toolList" :key="tool.key" class="px-4">
            <!-- 工具标题行 -->
            <div class="flex items-center justify-between py-3 cursor-pointer select-none" @click="toggleTool(tool.key)">
              <div class="flex items-center gap-3 min-w-0 flex-1">
                <component :is="tool.icon" class="w-5 h-5 flex-shrink-0" :class="getToolEnabled(tool.key) ? 'text-primary' : 'text-text-disabled'" />
                <div class="min-w-0">
                  <p class="text-sm font-medium text-text-primary truncate">{{ tool.label }}</p>
                  <p class="text-xs text-text-secondary truncate">{{ tool.desc }}</p>
                </div>
              </div>
              <div class="flex items-center gap-2 flex-shrink-0" @click.stop>
                <Toggle :modelValue="getToolEnabled(tool.key)" @update:modelValue="v => handleToolToggle(tool.key, v)" />
                <svg class="w-4 h-4 text-text-secondary transition-transform duration-200" :class="{ 'rotate-90': expandedTools[tool.key] }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                </svg>
              </div>
            </div>
            <!-- 工具配置展开区域 -->
            <Transition name="tool-expand">
              <div v-if="expandedTools[tool.key]" class="pb-4">
                <!-- 执行工具：Shell 白名单配置 -->
                <div v-if="tool.key === 'execute'" class="space-y-3 pl-8">
                  <div class="flex gap-2">
                    <input v-model="newCommand" class="input-base flex-1 text-sm" placeholder="输入允许的命令" @keydown.enter="addCommand" />
                    <button @click="addCommand" class="btn-secondary text-xs">添加</button>
                  </div>
                  <div class="flex flex-wrap gap-1.5">
                    <span v-for="cmd in shellWhitelistCommands" :key="cmd" class="inline-flex items-center gap-1 px-2.5 py-1 bg-bg-hover rounded-full text-xs">
                      {{ cmd }}
                      <button @click="removeCommand(cmd)" class="text-error hover:text-error/80 leading-none">×</button>
                    </span>
                  </div>
                  <p class="text-xs text-text-disabled">⚠️ 仅白名单内的命令可执行</p>
                </div>
                <!-- Web 搜索：API 配置 -->
                <div v-else-if="tool.key === 'web'" class="space-y-3 pl-8">
                  <div>
                    <label class="block text-xs text-text-secondary mb-1">搜索提供商</label>
                    <select v-model="config.webSearch.provider" class="input-base text-sm">
                      <option value="tavily">Tavily</option>
                      <option value="duckduckgo">DuckDuckGo</option>
                      <option value="baidu">百度</option>
                      <option value="serpapi">SerpAPI</option>
                    </select>
                  </div>
                  <div>
                    <label class="block text-xs text-text-secondary mb-1">API Key</label>
                    <div class="relative">
                      <input v-model="config.webSearch.api_key" class="input-base text-sm pr-10" placeholder="tvly-..." type="password" @change="saveWebKey" />
                      <div class="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1">
                        <Lock v-if="hasWebKey" class="w-4 h-4 text-success" />
                        <span v-if="hasWebKey" class="text-xs text-success font-medium">已存</span>
                      </div>
                    </div>
                    <p class="text-xs text-text-secondary mt-1">Key 仅保存在后端，刷新后不回显。留空则尝试从环境变量 <code class="text-primary text-xs">TAVILY_API_KEY</code> 读取</p>
                  </div>
                </div>
                <!-- 文件操作：路径说明 -->
                <div v-else-if="tool.key === 'file_ops'" class="pl-8 space-y-3">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="text-sm text-text-primary">全盘访问</p>
                      <p class="text-xs text-text-secondary">开启后可读取整个磁盘，关闭后仅限 data/ 目录</p>
                    </div>
                    <Toggle v-model="config.file_ops_full_access" @update:modelValue="saveFileOpsAccess" />
                  </div>
                  <div class="border-t border-border pt-3 mt-3">
                    <div class="flex items-center justify-between mb-2">
                      <p class="text-sm text-text-primary font-medium">已上传文件</p>
                      <label class="text-xs btn-secondary py-1 px-2 cursor-pointer flex items-center gap-1">
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/>
                        </svg>
                        上传文件
                        <input type="file" class="hidden" @change="handleFileUpload" />
                      </label>
                    </div>
                    <div v-if="files.length === 0" class="text-xs text-text-disabled py-2">暂无上传文件</div>
                    <div v-else class="space-y-1 max-h-32 overflow-y-auto">
                      <div v-for="f in files" :key="f.name || f" class="flex items-center justify-between px-2 py-1.5 rounded bg-bg-hover/50 text-xs group">
                        <span class="text-text-primary truncate flex-1">{{ f.name || f }}</span>
                        <button @click="deleteFile(f.name || f)" class="text-error hover:underline flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">删除</button>
                      </div>
                    </div>
                  </div>
                </div>
                <!-- HTTP 请求 -->
                <div v-else-if="tool.key === 'http_request'" class="pl-8 space-y-2">
                  <p class="text-xs text-text-secondary">允许 AI 向外部服务发送 HTTP 请求</p>
                </div>
                <!-- 其余工具通用提示 -->
                <div v-else class="pl-8 space-y-2">
                  <p class="text-xs text-text-secondary">{{ tool.configHint || '无需额外配置，仅控制启用/禁用' }}</p>
                </div>
              </div>
            </Transition>
          </div>
        </div>
      </section>
      
      <!-- ====== Shell 白名单（旧版，保留兼容） ====== -->
      <section v-if="activePanel === 'config-shell'" class="card">
        <h3 class="text-lg font-semibold text-text-primary mb-4 flex items-center gap-2">
          <Terminal class="w-5 h-5 text-primary" /> Shell 白名单
        </h3>
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <p class="text-text-primary font-medium">启用 Shell 执行</p>
            <Toggle :modelValue="config.shell_whitelist?.enabled ?? true" @update:modelValue="saveShellEnabled" />
          </div>
          <div class="flex gap-2">
            <input v-model="newCommand" class="input-base flex-1" placeholder="输入允许的命令" @keydown.enter="addCommand" />
            <button @click="addCommand" class="btn-secondary">添加</button>
          </div>
          <div class="flex flex-wrap gap-2">
            <span v-for="cmd in shellWhitelistCommands" :key="cmd" class="inline-flex items-center gap-1 px-3 py-1 bg-bg-hover rounded-full text-sm">
              {{ cmd }}
              <button @click="removeCommand(cmd)" class="text-error hover:text-error/80 text-lg leading-none">×</button>
            </span>
          </div>
        </div>
      </section>
      
      <!-- 保存/重载按钮 -->
      <div v-if="!['config', 'config-tools', 'config-model', 'config-general', 'config-memory', 'config-system'].includes(activePanel)" class="flex gap-3">
        <button @click="saveConfig" class="btn-primary">保存配置</button>
        <button @click="reloadConfig" class="btn-secondary">重载配置</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { configApi, providerApi, shellApi, memoryApi, providerMgmtApi, filesApi } from '@/api/index.js'
import { Settings, Cpu, Database, Terminal, SlidersHorizontal, Monitor, Eye, EyeOff, Wrench, Search, FileCode, Globe, Code2, TerminalSquare, Brain, FileText as FileTextIcon, Lock } from 'lucide-vue-next'
import Toggle from '../shared/Toggle.vue'
import LoadingSpinner from '../shared/LoadingSpinner.vue'
import ConfirmDialog from '../shared/ConfirmDialog.vue'

const config = ref({
  provider: { base_url: '', api_key: '', model: '' },
  memory: { enabled: true, mode: 'simple' },
  compression: { enabled: false, mode: 'summarize', interval: 20, model: '', prompt: '' },
  tools: {},
  webSearch: { enabled: false, provider: 'tavily', api_key: '' },
  file_ops_full_access: true,
  shell_enabled: false,
  shell_whitelist: []
})
const loading = ref(false)
const showKey = ref(false)
const newCommand = ref('')

// 兼容 shell_whitelist 两种格式（对象或数组）
const shellWhitelistCommands = computed(() => {
  const wl = config.value.shell_whitelist
  if (Array.isArray(wl)) return wl
  if (wl?.commands) return wl.commands
  return []
})

// ─── 工具配置 ───
const expandedTools = reactive({})

// 加载文件列表（当文件操作展开时）
const toggleTool = (key) => {
  expandedTools[key] = !expandedTools[key]
  if (key === 'file_ops' && expandedTools[key]) {
    loadFiles()
  }
}

const toolList = [
  { key: 'web', label: '网络工具', icon: Search, desc: '网页搜索与内容提取（合并了搜索+网页读取）', configHint: '需配置搜索提供商和 API Key' },
  { key: 'execute', label: '执行工具', icon: TerminalSquare, desc: '执行 Python 代码或系统命令（合并了代码+Shell）', configHint: 'Shell 执行需配置白名单命令' },
  { key: 'file_ops', label: '文件操作', icon: FileCode, desc: '读写 data/ 目录下的文件', configHint: '无需额外配置，仅控制启用/禁用' },
  { key: 'common_utils', label: '通用工具', icon: Code2, desc: '获取时间、计算、随机数等（合并了时间+计算+随机）', configHint: '无需额外配置，仅控制启用/禁用' },
  { key: 'http_request', label: 'HTTP 请求', icon: Globe, desc: '发送 HTTP 请求到外部服务', configHint: '无需额外配置，仅控制启用/禁用' },
  { key: 'memory_query', label: '记忆查询', icon: Brain, desc: 'AI 主动查询长期记忆库', configHint: '无需额外配置，仅控制启用/禁用' },
  { key: 'note_taking', label: '笔记记录', icon: FileTextIcon, desc: 'AI 可读写笔记文件', configHint: '无需额外配置，仅控制启用/禁用' },
]

const files = ref([])
const loadingFiles = ref(false)

const loadFiles = async () => {
  loadingFiles.value = true
  try {
    const result = await filesApi.list()
    files.value = result.files || []
  } catch (e) {
    console.error('加载文件列表失败:', e)
  } finally {
    loadingFiles.value = false
  }
}

const handleFileUpload = async (e) => {
  const file = e.target.files?.[0]
  if (!file) return
  try {
    await filesApi.upload(file)
    showToast?.(`文件 ${file.name} 上传成功`, 'success')
    await loadFiles()
  } catch (err) {
    showToast?.('上传失败: ' + err.message, 'error')
  }
  e.target.value = ''
}

const deleteFile = async (name) => {
  try {
    await filesApi.delete(name)
    await loadFiles()
    showToast?.('文件已删除', 'success')
  } catch (e) {
    showToast?.('删除失败: ' + e.message, 'error')
  }
}

const getToolEnabled = (key) => {
  // 'web' 工具的配置在 config.webSearch 里
  if (key === 'web') return config.value.webSearch?.enabled ?? false
  // 其余工具在 config.tools 里
  return config.value.tools?.[key] ?? false
}

const setToolEnabled = (key, val) => {
  if (key === 'web') {
    if (!config.value.webSearch) config.value.webSearch = { enabled: val, provider: 'tavily', api_key: '' }
    else config.value.webSearch.enabled = val
  } else {
    if (!config.value.tools) config.value.tools = {}
    config.value.tools[key] = val
  }
}

// 保存文件操作的全盘访问设置
const saveFileOpsAccess = async (val) => {
  config.value.file_ops_full_access = val
  try {
    await configApi.update({
      tools: { file_ops_full_access: val }
    })
    showToast?.(val ? '已开启全盘访问' : '已关闭全盘访问（仅限 data/ 目录）', 'success')
  } catch (e) {
    config.value.file_ops_full_access = !val
    showToast?.('保存失败: ' + e.message, 'error')
  }
}

// 保存网络搜索 API Key（输入后自动保存）
const saveWebKey = async () => {
  try {
    await configApi.update({ web_search: config.value.webSearch })
    showToast?.('API Key 已保存', 'success')
  } catch (e) {
    showToast?.('保存失败: ' + e.message, 'error')
  }
}

// 工具开关切换：实时保存到后端
const handleToolToggle = async (key, val) => {
  setToolEnabled(key, val)
  try {
    // file_ops 的全盘访问走专门的 saveFileOpsAccess，这里只控制开关
    if (key === 'file_ops') {
      // 单独开关 file_ops 工具
      await configApi.update({
        tools: { ...config.value.tools }
      })
    } else {
      const wl = config.value.shell_whitelist
      const commands = Array.isArray(wl) ? wl : (wl?.commands || [])
      await configApi.update({
        web_search: config.value.webSearch,
        tools: { ...config.value.tools },
        shell_whitelist: { enabled: config.value.shell_whitelist?.enabled ?? true, commands }
      })
    }
  } catch (e) {
    // 失败时回滚
    setToolEnabled(key, !val)
    showToast?.('保存失败: ' + e.message, 'error')
  }
}

const props = defineProps({
  activePanel: { type: String, default: 'config' }
})

// 检测用户是否在当前会话中输入了API Key
const hasWebKey = computed(() => {
  return config.value.webSearch?.api_key?.length > 0
})

// 根据当前子项显示对应标题
const pageTitle = computed(() => ({
  'config': '系统配置',
  'config-general': '普通配置',
  'config-system': '系统配置',
  'config-model': '模型配置',
  'config-memory': '记忆配置',
  'config-shell': 'Shell 白名单',
  'config-tools': '工具配置',
}[props.activePanel] || '系统配置'))

// ─── 多提供商管理 ───

// 主动引擎配置
const activeConfig = ref({
  chatter_mode: 'medium',
  quiet_hours_start: 23,
  quiet_hours_end: 8,
})
const activeStats = ref(null)

// 加载主动引擎配置
const loadActiveConfig = async () => {
  try {
    const res = await fetch('/api/active/config').then(r => r.json())
    // 检查是否返回了错误
    if (res && !res.error) {
      Object.assign(activeConfig.value, {
        chatter_mode: res.chatter_mode || 'medium',
        quiet_hours_start: res.quiet_hours_start ?? 23,
        quiet_hours_end: res.quiet_hours_end ?? 8,
      })
    } else if (res?.error) {
      console.warn('[Active] 加载配置失败:', res.error)
    }
  } catch (e) {
    console.warn('[Active] 加载配置失败:', e)
  }
  try {
    const res = await fetch('/api/active/stats').then(r => r.json())
    if (res && !res.error) {
      activeStats.value = res
    }
  } catch (e) {
    console.warn('[Active] 加载统计失败:', e)
  }
}

// 格式化回应率为百分比
const formatReplyRate = (rate) => {
  if (rate === undefined || rate === null) return '-'
  return (rate * 100).toFixed(0) + '%'
}

// 保存主动引擎配置
const saveActiveConfig = async () => {
  try {
    await fetch('/api/active/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      // 只发三个有效配置字段，不发只读的统计/路由信息
      body: JSON.stringify({
        chatter_mode: activeConfig.value.chatter_mode,
        quiet_hours_start: activeConfig.value.quiet_hours_start,
        quiet_hours_end: activeConfig.value.quiet_hours_end,
      })
    })
    showToast?.('主动引擎配置已保存', 'success')
  } catch (e) {
    showToast?.('保存失败: ' + e.message, 'error')
  }
}
// 普通配置：模型选择
const selectedModelKey = ref('')

// 当前选中的模型详情
const currentSelectedModel = computed(() => {
  if (!selectedModelKey.value) return null
  const [pid, ...rest] = selectedModelKey.value.split('/')
  const modelId = rest.join('/')
  const provider = providers.value.find(p => p.id === pid)
  if (!provider || !modelId) return null
  return {
    providerName: provider.name,
    modelId: modelId,
    base_url: provider.base_url,
    api_key: provider.api_key,
  }
})

// 保存通用配置
const saveGeneralConfig = async () => {
  if (!currentSelectedModel.value) {
    showToast?.('请先选择一个模型', 'warning')
    return
  }
  try {
    const m = currentSelectedModel.value
    // 压缩配置：关掉时把 interval 设 0 让后端真正停止压缩
    const isEnabled = config.value.compression.enabled
    const compressModelId = config.value.compression.model
    // 查找压缩模型所属的提供商 ID
    let compressProviderId = ''
    if (compressModelId) {
      for (const p of providers.value) {
        if (p.models?.some(m => m.id === compressModelId)) {
          compressProviderId = p.id
          break
        }
      }
    }
    
    // 先从 selectedModelKey 提取提供商 ID
    const providerId = selectedModelKey.value.split('/')[0]
    
    // 1️⃣ 先保存配置到 config.yaml（模型、压缩等）
    const providerUpdate = {
      base_url: m.base_url,
      model: m.modelId,
      compression_enabled: isEnabled,
      compression_mode: config.value.compression.mode,
      compression_interval: isEnabled ? config.value.compression.interval : 0,
      compression_model: compressModelId,
      compression_provider_id: compressProviderId,
      compression_prompt: config.value.compression.prompt,
    }
    await configApi.update({ provider: providerUpdate })
    
    // 2️⃣ 配置保存成功后再切换提供商
    if (providerId) {
      await providerMgmtApi.switch(providerId)
    }
    
    showToast?.(`已切换至 ${m.providerName} / ${m.modelId}`, 'success')
  } catch (e) {
    showToast?.('保存失败: ' + e.message, 'error')
  }
}

// 默认预置几个常用提供商
const defaultProviders = [
  {
    id: 'default-deepseek',
    name: 'DeepSeek',
    type: 'openai',
    base_url: 'https://api.deepseek.com',
    api_key: '',
    enabled: true,
    models: []
  }
]

const providers = ref([])
const selectedProviderId = ref(null)
const showProviderKey = reactive({})

// 从后端 API 加载提供商列表
const loadProviders = async () => {
  try {
    const result = await providerMgmtApi.list()
    if (result.providers && result.providers.length > 0) {
      providers.value = result.providers
    } else {
      providers.value = JSON.parse(JSON.stringify(defaultProviders))
      await providerMgmtApi.save({ providers: providers.value, active_id: '' })
    }
    const cfg = config.value.provider
    if (cfg?.api_key) {
      // 灵活匹配：先精确匹配 base_url，再试去掉 /v1 后匹配，再试 base_url 包含关系
      let matched = providers.value.find(p => p.base_url === cfg.base_url)
      if (!matched) {
        const normalized_cfg = cfg.base_url?.replace('/v1', '')
        matched = providers.value.find(p => p.base_url?.replace('/v1', '') === normalized_cfg)
      }
      if (!matched) matched = providers.value.find(p => p.enabled) || providers.value[0]
      if (matched) {
        matched.api_key = cfg.api_key
        if (!matched.base_url) matched.base_url = cfg.base_url
        if (cfg.model && !matched.models.find(m => m.id === cfg.model)) {
          matched.models.unshift({ id: cfg.model, status: 'available', enabled: true })
        }
      }
    }
    if (providers.value.length > 0 && !selectedProviderId.value) {
      selectedProviderId.value = providers.value[0].id
    }
    syncSelectedModel()
  } catch (e) {
    providers.value = JSON.parse(JSON.stringify(defaultProviders))
  }
}

// 根据当前 config 自动匹配选中的模型
const syncSelectedModel = () => {
  const currentModel = config.value.provider?.model
  if (!currentModel) return
  for (const p of providers.value) {
    for (const m of p.models) {
      if (m.id === currentModel) {
        selectedModelKey.value = p.id + '/' + m.id
        return
      }
    }
  }
}

// 保存提供商列表到后端
const persistProviders = async () => {
  try {
    await providerMgmtApi.save({ providers: providers.value, active_id: selectedProviderId.value || '' })
  } catch (e) {
    console.error('保存提供商失败:', e)
    showToast?.('保存失败: ' + e.message, 'error')
  }
}


// 当前选中的提供商
const selectedProvider = computed(() => providers.value.find(p => p.id === selectedProviderId.value))

// 添加新提供商
const addProvider = () => {
  const id = 'provider-' + Date.now()
  providers.value.push({
    id,
    name: '新提供商',
    type: 'openai',
    base_url: '',
    api_key: '',
    enabled: false,
    models: []
  })
  selectedProviderId.value = id
  persistProviders().then()
}

const showDeleteProviderConfirm = ref(false)
const deleteProviderTarget = ref('')
const deleteProviderId = ref('')

// 删除提供商（先弹确认窗）
const removeProvider = (id) => {
  const provider = providers.value.find(p => p.id === id)
  deleteProviderTarget.value = provider?.name || '未命名'
  deleteProviderId.value = id
  showDeleteProviderConfirm.value = true
}

// 确认删除
const confirmDeleteProvider = () => {
  providers.value = providers.value.filter(p => p.id !== deleteProviderId.value)
  if (selectedProviderId.value === deleteProviderId.value) {
    selectedProviderId.value = providers.value.length > 0 ? providers.value[0].id : null
  }
  showDeleteProviderConfirm.value = false
  persistProviders().then(() => {
    showToast?.('提供商已删除', 'success')
  })
}

// 保存当前提供商
const saveCurrentProvider = async () => {
  await persistProviders()
  showToast?.('提供商已保存', 'success')
}

// 添加模型
const addModel = (provider) => {
  provider.models.push({ id: '', status: 'unknown', enabled: true })
}

// 从提供商获取可用模型列表
const fetchProviderModels = async (provider) => {
  if (!provider.base_url || !provider.api_key) {
    showToast?.('请先填写 API 地址和 Key', 'warning')
    return
  }
  try {
    const result = await providerApi.getModels({
      base_url: provider.base_url,
      api_key: provider.api_key,
      model: provider.models[0]?.id || ''
    })
    if (result.status === 'fail') {
      showToast?.('获取失败: ' + (result.message || '未知错误'), 'error')
      return
    }
    const models = result.models || []
    if (models.length === 0) {
      showToast?.('未获取到模型列表，请手动添加', 'info')
      return
    }
    // 去重添加
    const existingIds = new Set(provider.models.map(m => m.id))
    for (const modelId of models) {
      if (!existingIds.has(modelId)) {
        provider.models.push({ id: modelId, status: 'available', enabled: true })
      }
    }
    await persistProviders()
    showToast?.(`获取到 ${models.length} 个模型`, 'success')
  } catch (e) {
    showToast?.('获取模型失败: ' + e.message, 'error')
  }
}

// 测试模型（实际调用后端测试连接，携带指定模型名）
const testModel = async (provider, idx) => {
  const model = provider.models[idx]
  if (!model.id) {
    showToast?.('请输入模型ID', 'warning')
    return
  }
  model.status = 'pending'
  try {
    const result = await providerApi.test({
      base_url: provider.base_url,
      api_key: provider.api_key,
      model: model.id,
    })
    if (result.status === 'ok') {
      model.status = 'available'
      showToast?.(`模型 ${model.id} 测试通过`, 'success')
    } else {
      model.status = 'unknown'
      showToast?.(`模型 ${model.id} 测试失败: ` + (result.message || '未知错误'), 'error')
    }
    await persistProviders()
  } catch (e) {
    model.status = 'unknown'
    showToast?.('测试失败: ' + e.message, 'error')
  }
}

// 测试连接（检查后端返回结果）
const testProviderConnection = async (provider) => {
  if (!provider.base_url || !provider.api_key) {
    showToast?.('请先填写 API 地址和 Key', 'warning')
    return
  }
  try {
    const result = await providerApi.test({
      base_url: provider.base_url,
      api_key: provider.api_key,
      model: provider.models[0]?.id || ''
    })
    if (result.status === 'ok') {
      showToast?.('连接成功', 'success')
    } else {
      showToast?.('连接失败: ' + (result.message || '未知错误'), 'error')
    }
  } catch (e) {
    showToast?.('连接测试失败: ' + e.message, 'error')
  }
}

// 切换 Key 显隐
const toggleProviderKey = (id) => {
  showProviderKey[id] = !showProviderKey[id]
}

onMounted(() => { loadConfig().then(async () => { await loadProviders(); loadActiveConfig() }) })

const loadConfig = async () => {
  loading.value = true
  try {
    const result = await configApi.get()
    let toolsData = result.tools || {}
    let webSearchData = result.web_search
    let shellWhitelistData = result.shell_whitelist
    
    if (result) {
      config.value = {
        provider: result.provider || config.value.provider,
        memory: result.memory || config.value.memory,
        tools: toolsData,
        webSearch: webSearchData || { enabled: false, provider: 'tavily', api_key: '' },
        file_ops_full_access: result.tools?.file_ops_full_access ?? true,
        compression: {
          enabled: result.provider?.compression_enabled ?? false,
          mode: result.provider?.compression_mode || 'summarize',
          interval: result.provider?.compression_interval || 20,
          model: result.provider?.compression_model || '',
          prompt: result.provider?.compression_prompt || '',
        },
        shell_enabled: result.features?.shell_exec ?? config.value.shell_enabled,
        shell_whitelist: shellWhitelistData || []
      }
      // 配置加载后同步选中的模型（第一次尝试，providers可能还没加载）
      // 真正的匹配在 loadProviders 中完成
    }
  } catch (e) {
    console.error('加载配置失败:', e)
  } finally {
    loading.value = false
  }
}

// 切换记忆模式（调用专用 API，同步更新后端和运行时）
const toggleMemory = async (val) => {
  config.value.memory.enabled = val
  try {
    await memoryApi.toggle(val)
    showToast?.(val ? '已切换至 Memoria 模式' : '已切换至 Simple 模式', 'success')
  } catch (e) {
    config.value.memory.enabled = !val  // 回滚
    showToast?.('切换失败: ' + e.message, 'error')
  }
}

// 保存 Shell 启用状态
const saveShellEnabled = async (val) => {
  if (!config.value.shell_whitelist || Array.isArray(config.value.shell_whitelist)) {
    config.value.shell_whitelist = { enabled: val, commands: Array.isArray(config.value.shell_whitelist) ? config.value.shell_whitelist : [] }
  } else {
    config.value.shell_whitelist.enabled = val
  }
  try {
    const commands = Array.isArray(config.value.shell_whitelist) ? config.value.shell_whitelist : (config.value.shell_whitelist?.commands || [])
    await configApi.update({
      shell_whitelist: { enabled: val, commands }
    })
    showToast?.(val ? 'Shell 执行已启用' : 'Shell 执行已关闭', 'success')
  } catch (e) {
    showToast?.('保存失败: ' + e.message, 'error')
  }
}

const saveConfig = async () => {
  try {
    await configApi.update(config.value)
    showToast?.('配置已保存', 'success')
  } catch (e) {
    showToast?.('保存失败: ' + e.message, 'error')
  }
}

const reloadConfig = async () => {
  try {
    await configApi.reload()
    await loadConfig()
    showToast?.('配置已重载', 'success')
  } catch (e) {
    showToast?.('重载失败: ' + e.message, 'error')
  }
}

const testProvider = async () => {
  try {
    await providerApi.test(config.value.provider)
    showToast?.('连接测试成功', 'success')
  } catch (e) {
    showToast?.('连接测试失败: ' + e.message, 'error')
  }
}

const fetchModels = async () => {
  try {
    await providerApi.getModels(config.value.provider)
    showToast?.('已获取模型列表', 'success')
  } catch (e) {
    showToast?.('获取模型失败: ' + e.message, 'error')
  }
}

const addCommand = async () => {
  const cmd = newCommand.value.trim()
  if (!cmd) return
  try {
    await shellApi.addCommand(cmd)
    newCommand.value = ''
    // 确保 shell_whitelist 是数组格式
    if (!Array.isArray(config.value.shell_whitelist)) {
      const arr = config.value.shell_whitelist?.commands || []
      config.value.shell_whitelist = arr
    }
    config.value.shell_whitelist.push(cmd)
    showToast?.('命令已添加', 'success')
  } catch (e) {
    showToast?.('添加失败: ' + e.message, 'error')
  }
}

const removeCommand = async (cmd) => {
  try {
    await shellApi.deleteCommand(cmd)
    config.value.shell_whitelist = config.value.shell_whitelist.filter(c => c !== cmd)
    showToast?.('命令已删除', 'success')
  } catch (e) {
    showToast?.('删除失败: ' + e.message, 'error')
  }
}
</script>
