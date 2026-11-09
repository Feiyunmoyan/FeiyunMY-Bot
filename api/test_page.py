"""
测试面板静态 HTML（从 api/admin.py 拆出，按需导入）

用法：
    from api.test_page import TEST_PAGE_HTML

注意：这是旧版内联测试页，功能已被 webui（/admin）取代，
仅保留供 /test 端点与排障使用。
"""

TEST_PAGE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FeiyunMY-Bot 测试面板</title>
<script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:system-ui,sans-serif}
body{background:#f5f3ff;color:#1e1b2e;padding:20px;max-width:1100px;margin:0 auto}
h1{font-size:22px;margin-bottom:20px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.card{background:#fff;border-radius:14px;padding:20px;margin-bottom:16px;border:1px solid #e8e4f4}
.card h3{font-size:14px;margin-bottom:12px;color:#6b6580;text-transform:uppercase;letter-spacing:.5px}
.row{display:flex;align-items:center;gap:12px;margin-bottom:10px;flex-wrap:wrap}
.row label{font-size:14px;min-width:100px}
.toggle{width:40px;height:22px;border-radius:11px;border:none;cursor:pointer;position:relative;transition:.25s;background:#d1d5db}
.toggle.on{background:#7c5cfc}
.toggle::after{content:'';position:absolute;top:2px;left:2px;width:18px;height:18px;border-radius:50%;background:#fff;transition:.25s;box-shadow:0 1px 3px rgba(0,0,0,.12)}
.toggle.on::after{transform:translateX(18px)}
.btn{padding:8px 18px;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:500;transition:.2s}
.btn:active{transform:scale(.97)}
.btn-p{background:#7c5cfc;color:#fff}
.btn-p:hover{background:#6d4ef0}
.btn-d{background:#fee2e2;color:#dc2626}
.btn-s{background:#d1fae5;color:#059669}
.btn-o{background:transparent;border:1.5px solid #e8e4f4;color:#6b6580}
input,select,textarea{padding:8px 12px;border:1.5px solid #e8e4f4;border-radius:8px;font-size:13px;font-family:inherit}
input:focus,select:focus,textarea:focus{outline:none;border-color:#7c5cfc}
textarea{min-height:60px;resize:vertical;width:100%}
.tag{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;background:#ede9fe;color:#7c5cfc;margin:2px}
.tag-g{background:#d1fae5;color:#059669}
.tag-r{background:#fee2e2;color:#dc2626}
.chat-box{height:300px;overflow-y:auto;padding:14px;background:#faf9ff;border-radius:10px;border:1px solid #e8e4f4;margin-bottom:10px}
.msg{margin-bottom:12px;display:flex}
.msg.right{justify-content:flex-end}
.msg .b{max-width:80%;padding:10px 14px;border-radius:14px;font-size:14px;line-height:1.5;white-space:pre-wrap}
.msg.right .b{background:#7c5cfc;color:#fff;border-bottom-right-radius:3px}
.msg.left .b{background:#fff;border:1px solid #e8e4f4;border-bottom-left-radius:3px}
.msg .reason{font-size:11px;color:#9b95b0;margin-top:4px;padding:0 4px;font-style:italic}
.chat-in{display:flex;gap:8px}
.chat-in input{flex:1}
.status{font-size:12px;color:#9b95b0;margin-left:8px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.tri{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
.desc{font-size:12px;color:#9b95b0;margin:4px 0 8px 0;line-height:1.4}
.label-hint{font-size:10px;color:#9b95b0;margin-left:4px;font-weight:normal}
@media(max-width:600px){.grid,.tri{grid-template-columns:1fr}}
</style>
</head>
<body>
<div id="app">
  <h1>☁️ FeiyunMY-Bot 测试面板 <span class="status">{{ status }}</span></h1>

  <div class="tri">
    <div class="card">
      <h3>⚙️ 功能开关</h3>
      <div class="row"><label>人格系统</label><button class="toggle" :class="{on:cfg.persona?.enabled}" @click="toggle('persona.enabled')"></button><span>{{ cfg.persona?.enabled?'已开启':'已关闭' }}</span></div>
      <div class="row"><label>联网搜索</label><button class="toggle" :class="{on:cfg.web_search?.enabled}" @click="toggle('web_search.enabled')"></button><span>{{ cfg.web_search?.enabled?'已开启':'已关闭' }}</span></div>
      <div class="row"><label>保留思考</label><button class="toggle" :class="{on:cfg.features?.keep_thinking}" @click="toggle('features.keep_thinking')"></button><span>{{ cfg.features?.keep_thinking?'已开启':'已关闭' }}</span></div>
      <div class="row"><label>记忆开关</label><button class="toggle" :class="{on:cfg.memory?.enabled}" @click="toggleMemory()"></button><span>{{ cfg.memory?.enabled?'Memoria':'Simple' }}</span></div>
      <div class="row"><label>MCP 服务</label><button class="toggle" :class="{on:cfg.mcp?.enabled}" @click="toggle('mcp.enabled')"></button><span>{{ cfg.mcp?.enabled?'已开启':'已关闭' }}</span></div>
      <div class="row"><label>Skills 技能</label><button class="toggle" :class="{on:cfg.skills?.enabled}" @click="toggle('skills.enabled')"></button><span>{{ cfg.skills?.enabled?'已开启':'已关闭' }}</span></div>
    </div>

    <div class="card">
      <h3>👤 人格 <span class="label-hint">关闭后使用默认提示词</span></h3>
      <div class="row" v-if="cfg.persona?.enabled">
        <select v-model="activePersona" @change="switchPersona" style="flex:1">
          <option v-for="p in personas" :key="p.name" :value="p.name">{{ p.name }} {{ p.is_active?'(使用中)':'' }}</option>
        </select>
      </div>
      <div v-else style="color:#9b95b0;font-size:13px">人格系统已关闭</div>

      <div style="margin-top:10px">
        <div class="row"><input v-model="newPersonaName" placeholder="人格名称" style="flex:1"><button class="btn btn-s" @click="addPersona">+ 新建</button></div>
        <div class="desc">提示：名称即 identity，prompt 决定对话风格和回答方式。</div>
      </div>
    </div>

    <div class="card">
      <h3>🔍 搜索引擎 <span class="label-hint">点击切换开关</span></h3>
      <div class="row"><input v-model="newEngineName" placeholder="引擎名称" style="flex:1"><button class="btn btn-s" @click="addEngine">+ 添加</button></div>
      <div><span v-for="e in engines" :key="e.name" class="tag" :class="e.enabled?'tag-g':'tag-r'" style="cursor:pointer;margin:4px" @click="toggleEngine(e)">{{ e.name }} {{ e.enabled?'●':'○' }}</span><span v-if="!engines.length" style="color:#9b95b0;font-size:13px">暂无</span></div>
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <h3>🔌 MCP 服务 <span class="label-hint">自由增删</span></h3>
      <div class="row">
        <input v-model="mcpForm.name" placeholder="名称" style="flex:1">
        <input v-model="mcpForm.url" placeholder="地址" style="flex:1">
        <button class="btn btn-s" @click="addMCP">+</button>
      </div>
      <div v-for="s in mcpServers" :key="s.name" class="tag" :class="s.enabled?'tag-g':''" style="cursor:pointer;margin:4px;display:inline-flex;align-items:center;gap:4px" @click="toggleMCP(s)">{{ s.name }} {{ s.enabled?'●':'○' }} <span style="cursor:pointer;color:#dc2626" @click.stop="deleteMCP(s.name)">✕</span></span>
      <div v-if="!mcpServers.length" style="color:#9b95b0;font-size:13px">暂无 MCP 服务</div>
    </div>

    <div class="card">
      <h3>🧩 Skills <span class="label-hint">自由增删</span></h3>
      <div class="row">
        <input v-model="skillForm.name" placeholder="名称" style="flex:1">
        <input v-model="skillForm.desc" placeholder="描述" style="flex:1">
        <button class="btn btn-s" @click="addSkill">+</button>
      </div>
      <div v-for="s in skills" :key="s.name" class="tag" :class="s.enabled?'tag-g':''" style="cursor:pointer;margin:4px;display:inline-flex;align-items:center;gap:4px" @click="toggleSkill(s)">{{ s.name }} {{ s.enabled?'●':'○' }} <span style="cursor:pointer;color:#dc2626" @click.stop="deleteSkill(s.name)">✕</span></span>
      <div v-if="!skills.length" style="color:#9b95b0;font-size:13px">暂无 Skills</div>
    </div>
  </div>

  <div class="card">
    <h3>💬 对话测试</h3>
    <div class="chat-box" ref="chatBox">
      <div v-for="(m,i) in chat" :key="i" class="msg" :class="m.role==='user'?'right':'left'">
        <div>
          <div class="b">{{ m.content }}</div>
          <div class="reason" v-if="m.reasoning && cfg.features?.keep_thinking">💭 {{ m.reasoning.slice(0,200) }}{{ m.reasoning.length>200?'...':'' }}</div>
        </div>
      </div>
      <div v-if="loading" class="msg left"><div class="b" style="color:#9b95b0">思考中...</div></div>
    </div>
    <div class="chat-in">
      <input v-model="chatInput" @keyup.enter="sendChat" placeholder="输入消息..." :disabled="loading">
      <button class="btn btn-p" @click="sendChat" :disabled="!chatInput.trim()||loading">{{ loading?'...':'发送' }}</button>
      <button class="btn btn-o" @click="chat=[]">清屏</button>
    </div>
    <div v-if="lastTools?.length" style="margin-top:8px;font-size:12px;color:#9b95b0">🔧 工具: {{ lastTools.join(', ') }}</div>
  </div>
</div>

<script>
const {createApp}=Vue;
createApp({
  data:()=>({
    cfg:{persona:{enabled:true},web_search:{enabled:false,engines:[]},features:{keep_thinking:false},memory:{enabled:false},mcp:{enabled:false},skills:{enabled:false}},
    personas:[],engines:[],mcpServers:[],skills:[],
    activePersona:'',newPersonaName:'',newEngineName:'',
    mcpForm:{name:'',url:''},skillForm:{name:'',desc:''},
    chat:[],chatInput:'',loading:false,lastTools:[],sid:'test_'+Date.now(),status:'加载中...',
  }),
  mounted(){this.loadAll()},
  methods:{
    async api(path,opts={}){
      try{const r=await fetch(path,{headers:{'Content-Type':'application/json'},...opts,body:opts.body?JSON.stringify(opts.body):undefined});return await r.json()}catch{return null}
    },
    async loadAll(){
      const s=await this.api('/api/stats');if(s)this.status='运行中 '+Math.floor(s.uptime_seconds)+'s';
      const c=await this.api('/api/config');if(c){this.cfg=c;this.activePersona=c.persona?.active||'default';}
      const p=await this.api('/api/personas');if(Array.isArray(p))this.personas=p;
      const e=await this.api('/api/search/engines');if(e){this.engines=e.engines||[];if(this.cfg.web_search)this.cfg.web_search.enabled=e.enabled;}
      const m=await this.api('/api/mcp/servers');if(m)this.mcpServers=m.servers||[];
      const sk=await this.api('/api/skills');if(sk)this.skills=sk.skills||[];
    },
    async toggle(path){
      const parts=path.split('.');let obj=this.cfg;
      for(let i=0;i<parts.length-1;i++)obj=obj[parts[i]];
      obj[parts[parts.length-1]]=!obj[parts[parts.length-1]];
      const body={};
      if(path.startsWith('persona'))body.persona=this.cfg.persona;
      else if(path.startsWith('web_search'))body.web_search=this.cfg.web_search;
      else if(path.startsWith('features'))body.features=this.cfg.features;
      else if(path.startsWith('mcp'))body.mcp=this.cfg.mcp;
      else if(path.startsWith('skills'))body.skills=this.cfg.skills;
      await this.api('/api/config',{method:'POST',body});
    },
    async toggleMemory(){
      const enabled=!this.cfg.memory?.enabled;
      const r=await this.api('/api/memory/toggle',{method:'POST',body:{enabled}});
      if(r?.status==='ok'){this.cfg.memory.enabled=r.enabled;this.cfg.memory.mode=r.mode;}
    },
    async switchPersona(){const r=await this.api('/api/personas/'+this.activePersona+'/activate',{method:'POST'});if(r?.status==='ok')this.loadAll();},
    async addPersona(){
      if(!this.newPersonaName.trim())return;
      const r=await this.api('/api/personas',{method:'POST',body:{name:this.newPersonaName.trim(),prompt:'你是一个AI助手。',description:'',preset_conversations:[]}});
      if(r?.status==='ok'){this.newPersonaName='';this.loadAll();}
    },
    async addEngine(){
      if(!this.newEngineName.trim())return;
      const r=await this.api('/api/search/engines',{method:'POST',body:{name:this.newEngineName.trim(),type:'web',enabled:true}});
      if(r?.engines){this.engines=r.engines;this.newEngineName='';}
    },
    async toggleEngine(e){e.enabled=!e.enabled;await this.api('/api/search/engines/'+e.name,{method:'PUT',body:{enabled:e.enabled}});},
    async addMCP(){
      if(!this.mcpForm.name.trim())return;
      const r=await this.api('/api/mcp/servers',{method:'POST',body:{name:this.mcpForm.name.trim(),url:this.mcpForm.url.trim(),description:'',enabled:true}});
      if(r?.servers){this.mcpServers=r.servers;this.mcpForm={name:'',url:''};}
    },
    async toggleMCP(s){s.enabled=!s.enabled;await this.api('/api/mcp/servers/'+s.name,{method:'PUT',body:{enabled:s.enabled}});},
    async deleteMCP(name){await this.api('/api/mcp/servers/'+name,{method:'DELETE'});const r=await this.api('/api/mcp/servers');if(r)this.mcpServers=r.servers||[];},
    async addSkill(){
      if(!this.skillForm.name.trim())return;
      const r=await this.api('/api/skills',{method:'POST',body:{name:this.skillForm.name.trim(),description:this.skillForm.desc.trim(),prompt:'',enabled:true}});
      if(r?.skills){this.skills=r.skills;this.skillForm={name:'',desc:''};}
    },
    async toggleSkill(s){s.enabled=!s.enabled;await this.api('/api/skills/'+s.name,{method:'PUT',body:{enabled:s.enabled}});},
    async deleteSkill(name){await this.api('/api/skills/'+name,{method:'DELETE'});const r=await this.api('/api/skills');if(r)this.skills=r.skills||[];},
    async sendChat(){
      const msg=this.chatInput.trim();if(!msg||this.loading)return;
      this.chat.push({role:'user',content:msg});this.chatInput='';this.loading=true;
      this.$nextTick(()=>this.scroll());
      const r=await this.api('/api/chat',{method:'POST',body:{message:msg,session_id:this.sid}});
      this.loading=false;
      if(r){this.chat.push({role:'assistant',content:r.reply||'（无回复）',reasoning:r.reasoning||null});this.lastTools=(r.tools_used||[]).map(t=>t.name);}
      this.$nextTick(()=>this.scroll());
    },
    scroll(){const el=this.$refs.chatBox;if(el)el.scrollTop=el.scrollHeight;}
  }
}).mount('#app');
</script>
</body>
</html>"""
