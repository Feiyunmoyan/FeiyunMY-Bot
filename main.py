"""
FeiyunMY-Bot 主入口
启动 FastAPI 服务，初始化所有模块
"""
import os
import sys
import time
import logging
import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(__file__))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# 加载 .env（敏感配置：API Key / 访问令牌），必须在读取 config.yaml 之前
try:
    from dotenv import load_dotenv

    _ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(_ENV_FILE):
        load_dotenv(_ENV_FILE, override=False)
        logger.info("已从 .env 加载环境变量")
except ImportError:
    logger.warning("未安装 python-dotenv，跳过 .env 加载（可 pip install python-dotenv）")

# 初始化数据目录
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
for sub in ["logs", "memories", "personas", "mcp", "skills"]:
    os.makedirs(os.path.join(DATA_DIR, sub), exist_ok=True)

# 数据库路径
DB_PATH = os.path.join(DATA_DIR, "feiyun.db")


def validate_config(cfg: dict) -> list[str]:
    """校验配置合法性，返回警告/错误信息列表"""
    warnings = []
    provider = cfg.get("provider", {})
    if not provider.get("api_key") and not os.environ.get("FEIYUN_API_KEY"):
        warnings.append("⚠️ provider.api_key 未设置！请在 .env 中配置 FEIYUN_API_KEY")
    if not provider.get("base_url"):
        warnings.append("⚠️ provider.base_url 未设置，将使用默认值")
    if not provider.get("model"):
        warnings.append("⚠️ provider.model 未设置，将使用默认值 deepseek-chat")

    tools_cfg = cfg.get("tools", {})

    shell_whitelist = cfg.get("shell_whitelist", {})
    if shell_whitelist.get("enabled", True):
        cmds = shell_whitelist.get("commands", [])
        if not cmds:
            warnings.append("⚠️ shell_whitelist 已启用但命令列表为空")

    return warnings


# 加载配置（通过配置热加载模块管理）
from utils.config_reloader import init_config as init_config_reloader
config = init_config_reloader(os.path.join(os.path.dirname(__file__), "config.yaml"))

# 校验配置
cfg_warnings = validate_config(config)
for w in cfg_warnings:
    logger.warning(w)

# 初始化 Provider
from provider.openai_provider import OpenAIProvider
from provider.manager import ProviderManager

provider_cfg = config.get("provider", {})
provider = OpenAIProvider(
    base_url=provider_cfg.get("base_url", ""),
    api_key=provider_cfg.get("api_key", ""),
    model=provider_cfg.get("model", "deepseek-chat"),
)

# 初始化多 Provider 管理器
provider_manager = ProviderManager(config)

# 初始化人格管理器
from persona.manager import PersonaManager

persona_manager = PersonaManager()

# 激活配置的人格
active_persona = config.get("persona", {}).get("active", "default")
persona_manager.activate(active_persona)

# 初始化记忆系统
from memory.selector import MemorySelector

memory_cfg = config.get("memory", {})
memory_enabled = memory_cfg.get("enabled", False)
# enabled=false -> simple, enabled=true -> 读取 mode 字段（默认 memoria）
memory_target = memory_cfg.get("mode", "memoria") if memory_enabled else "simple"
memory_selector = MemorySelector(mode=memory_target, config=config)

# 初始化工具注册中心
from tools.registry import ToolRegistry
# 新合并工具导入
from tools.web import web, WEB_DEFINITION
from tools.web_search import web_search, WEB_SEARCH_DEFINITION, set_search_config
from tools.web_extract import web_extract, WEB_EXTRACT_DEFINITION

# 注入搜索配置
ws_cfg = config.get("web_search", {})
ws_api_key = ws_cfg.get("api_key", "")
if not ws_api_key or ws_api_key.startswith("${"):
    ws_api_key = os.environ.get("TAVILY_API_KEY") or ws_api_key
set_search_config({"provider": ws_cfg.get("provider", "duckduckgo"), "api_key": ws_api_key})
from tools.file_ops import file_ops, FILE_OPS_DEFINITION
from tools.code_exec import code_exec, CODE_EXEC_DEFINITION
from tools.common_utils import (
    get_datetime, DATETIME_DEFINITION,
    calculator, CALCULATOR_DEFINITION,
    random_utils, RANDOM_DEFINITION,
    common_utils, COMMON_UTILS_DEFINITION,
)
from tools.agent_tools import (
    http_request, HTTP_REQUEST_DEFINITION,
    note_taking, NOTE_TOOL_DEFINITION,
    json_process, JSON_PROCESS_DEFINITION,
    shell_exec, SHELL_EXEC_DEFINITION, set_shell_whitelist,
    memory_query, MEMORY_QUERY_DEFINITION, set_memory_selector,
    manage_session, MANAGE_SESSION_DEFINITION, set_session_context,
    summary_query, SUMMARY_QUERY_DEFINITION,
    execute, EXECUTE_DEFINITION,
)
# 工作空间工具
from tools.workspace_tools import (
    workspace, WORKSPACE_DEFINITION,
    set_workspace_manager as set_ws_tool_manager,
)
# 工作空间管理器
from workspace.manager import WorkspaceManager
# Agent 配置管理器
from agent.config_manager import AgentConfigManager
# 主动引擎
from active_engine import PushEngine, AdaptiveLearner, ActiveScheduler
# 按天压缩
from active_engine.push_compressor import compress_push_messages as compress_push
# 知识库管理
from knowledge.manager import KnowledgeBaseManager

# 注入 Shell 白名单
shell_whitelist = config.get("shell_whitelist", {}).get("commands", [])
set_shell_whitelist(shell_whitelist)

# 注入依赖
set_memory_selector(memory_selector)

# 初始化文件访问模式
full_access = config.get("tools", {}).get("file_ops_full_access", True)
from tools.file_ops import set_full_access as set_fo_full_access
set_fo_full_access(full_access)

tool_registry = ToolRegistry()
tools_cfg = config.get("tools", {})

# === 合并后的新工具 ===
tool_registry.register("common_utils", common_utils, COMMON_UTILS_DEFINITION, tools_cfg.get("common_utils", True))
tool_registry.register("web", web, WEB_DEFINITION, tools_cfg.get("web", True))
tool_registry.register("execute", execute, EXECUTE_DEFINITION, tools_cfg.get("execute", False))

# === 其他工具 ===
tool_registry.register("file_ops", file_ops, FILE_OPS_DEFINITION, tools_cfg.get("file_ops", False))
tool_registry.register("http_request", http_request, HTTP_REQUEST_DEFINITION, tools_cfg.get("http_request", False))
tool_registry.register("note_taking", note_taking, NOTE_TOOL_DEFINITION, tools_cfg.get("note_taking", True))
tool_registry.register("json_process", json_process, JSON_PROCESS_DEFINITION, tools_cfg.get("json_process", True))
tool_registry.register("memory_query", memory_query, MEMORY_QUERY_DEFINITION, tools_cfg.get("memory_query", True))
tool_registry.register("manage_session", manage_session, MANAGE_SESSION_DEFINITION, tools_cfg.get("manage_session", True))
tool_registry.register("summary_query", summary_query, SUMMARY_QUERY_DEFINITION, True)

# === 工作空间工具 ===
tool_registry.register("workspace", workspace, WORKSPACE_DEFINITION, tools_cfg.get("workspace", True))

# === 旧工具保留（默认关闭，向后兼容旧对话历史） ===
tool_registry.register("web_search", web_search, WEB_SEARCH_DEFINITION, tools_cfg.get("web_search", False))
tool_registry.register("web_extract", web_extract, WEB_EXTRACT_DEFINITION, tools_cfg.get("web_extract", False))
tool_registry.register("code_exec", code_exec, CODE_EXEC_DEFINITION, tools_cfg.get("code_exec", False))
tool_registry.register("get_datetime", get_datetime, DATETIME_DEFINITION, tools_cfg.get("datetime", False))
tool_registry.register("calculator", calculator, CALCULATOR_DEFINITION, tools_cfg.get("calculator", False))
tool_registry.register("random_utils", random_utils, RANDOM_DEFINITION, tools_cfg.get("random_utils", False))
tool_registry.register("shell_exec", shell_exec, SHELL_EXEC_DEFINITION, tools_cfg.get("shell_exec", False))

# 初始化 MCP 管理器
from mcp.manager import MCPManager
mcp_manager = MCPManager()

# 初始化 Skills 管理器
from skills.manager import SkillsManager
skills_manager = SkillsManager()

# 初始化 Agent
from agent.runner import AgentRunner
from agent.conversation_store import ConversationContext
from db.database import FeiyunDatabase

# 初始化数据库
db = FeiyunDatabase(DB_PATH)

# 初始化上下文（异步，在 startup 中初始化）
context = None  # 将在 startup 中初始化

agent_loop = None  # 将在 startup 中初始化
_active_scheduler = None  # 全局引用，供 shutdown 使用
_ws_manager = None  # 全局引用，供 shutdown 使用

# 注入依赖到 API 路由
from api import chat, admin
from api.chat import set_chat_agent_deps
from utils.logging import ConversationLogger

conversation_logger = ConversationLogger()
chat.set_runner(agent_loop)
chat.set_conversation_logger(conversation_logger)
admin.set_admin_deps(config, persona_manager, memory_selector, tool_registry, mcp_manager, skills_manager, agent_loop, provider_manager)

# 创建 FastAPI 应用
# 生命周期管理（替换 on_event）
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化，关闭时清理"""
    # startup() 和 shutdown() 定义在下方，Python在调用时才解析名称
    await startup()
    yield
    await shutdown()

app = FastAPI(title="FeiyunMY-Bot", version="1.0.0", lifespan=lifespan)

# API 限流
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ==========================================
# 跨域配置（仅放行开发模式前端来源）
# ==========================================
from fastapi.middleware.cors import CORSMiddleware

_auth_cfg = (config.get("server", {}) or {}).get("auth", {}) or {}
_cors_origins = _auth_cfg.get("cors_origins") or ["http://localhost:3000", "http://127.0.0.1:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 访问鉴权
#   1) 本机回环地址可免令牌（便于本机浏览器直接使用）
#   2) 局域网 / 移动端：Authorization: Bearer <令牌>，或登录后使用 HttpOnly Cookie
#   3) 令牌来源：环境变量 FEIYUN_ACCESS_TOKEN > data/access_token.txt > 自动生成
# ==========================================
import secrets as _secrets
from fastapi import Request
from fastapi.responses import JSONResponse

AUTH_ENABLED = bool(_auth_cfg.get("enabled", True))
AUTH_LOCAL_BYPASS = bool(_auth_cfg.get("local_bypass", True))
AUTH_COOKIE_NAME = "feiyun_token"
AUTH_COOKIE_MAX_AGE = int(_auth_cfg.get("cookie_max_age_hours", 720)) * 3600
AUTH_TOKEN_FILE = os.path.join(DATA_DIR, "access_token.txt")

# 免鉴权路径：静态资源与管理面板外壳（令牌在页面内输入）
PUBLIC_PATHS = ("/", "/favicon.ico", "/docs", "/redoc", "/openapi.json")
PUBLIC_PREFIXES = ("/admin", "/assets/", "/api/auth/")
_LOCAL_HOSTS = ("127.0.0.1", "::1", "localhost", "")


def _load_access_token() -> str:
    """读取访问令牌；没有则自动生成并落盘"""
    token = (os.environ.get("FEIYUN_ACCESS_TOKEN") or "").strip()
    if token:
        return token
    if os.path.exists(AUTH_TOKEN_FILE):
        try:
            with open(AUTH_TOKEN_FILE, "r", encoding="utf-8") as f:
                saved = f.read().strip()
            if saved:
                return saved
        except OSError:
            pass
    token = _secrets.token_urlsafe(24)
    try:
        with open(AUTH_TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(token)
        logger.warning("未配置 FEIYUN_ACCESS_TOKEN，已自动生成访问令牌 → data/access_token.txt")
    except OSError as e:
        logger.error(f"访问令牌写入失败: {e}")
    return token


ACCESS_TOKEN = _load_access_token()


def _extract_token(request: Request) -> str:
    """依次尝试 Bearer Header / X-Access-Token / Cookie"""
    auth_header = request.headers.get("authorization", "") or ""
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    header_token = (request.headers.get("x-access-token", "") or "").strip()
    if header_token:
        return header_token
    return (request.cookies.get(AUTH_COOKIE_NAME) or "").strip()


def _is_public_path(path: str) -> bool:
    if path in PUBLIC_PATHS:
        return True
    return any(path.startswith(p) for p in PUBLIC_PREFIXES)


def _is_local_request(request: Request) -> bool:
    client = getattr(request, "client", None)
    return bool(client is not None and (client.host or "") in _LOCAL_HOSTS)


def _token_ok(token: str) -> bool:
    return bool(token) and _secrets.compare_digest(token, ACCESS_TOKEN)


@app.middleware("http")
async def access_guard(request: Request, call_next):
    """全局访问守卫"""
    if not AUTH_ENABLED:
        return await call_next(request)
    if request.method == "OPTIONS":
        return await call_next(request)
    path = request.url.path
    if _is_public_path(path):
        return await call_next(request)
    if AUTH_LOCAL_BYPASS and _is_local_request(request):
        return await call_next(request)
    if _token_ok(_extract_token(request)):
        return await call_next(request)
    logger.warning(f"拒绝未授权访问: {request.method} {path} <- {getattr(request.client, 'host', '?')}")
    return JSONResponse(
        {"detail": "unauthorized", "message": "缺少或错误的访问令牌"},
        status_code=401,
    )

# 注册路由
app.include_router(chat.router, prefix="/api")
app.include_router(admin.router)

# 注册工作空间 API
from api.workspaces import router as workspaces_router, set_workspace_manager as set_ws_api_manager, set_workspace_exec_deps
app.include_router(workspaces_router, prefix="/api")

# 注册 Agent 管理 API
from api.agents import router as agents_router, set_agent_config_manager as set_agent_api_manager
app.include_router(agents_router, prefix="/api")

# 注册主动引擎 API
from api.active import router as active_router, set_active_engine_deps as set_active_api_deps
app.include_router(active_router, prefix="/api")

# 注册知识库管理 API
from api.knowledge import router as knowledge_router, set_knowledge_manager as set_kb_api_manager
app.include_router(knowledge_router, prefix="/api")

# 注册通知历史 API

# 注册普通消息持久化 API
from api.push_messages import router as push_router, set_push_store_deps as set_push_deps, set_runner as set_push_runner, set_scheduler as set_push_scheduler
app.include_router(push_router, prefix="/api")


async def startup():
    global context, agent_loop, _active_scheduler, _ws_manager

    # 初始化平台日志系统
    from utils.logging import setup_logging
    setup_logging()
    logger.info(f"平台日志已初始化: {os.path.join('data', 'logs', 'platform.log')}")

    # 初始化数据库
    await db.initialize()
    logger.info(f"SQLite 数据库已初始化: {DB_PATH}")

    # 运行 JSON → SQLite 迁移
    from db.migration import migrate_json_to_sqlite
    result = await migrate_json_to_sqlite(db)
    if result["sessions"] > 0:
        logger.info(f"数据迁移完成: {result['sessions']} 个会话, {result['messages']} 条消息")
    else:
        logger.info("无历史 JSON 数据需要迁移")

    # 初始化上下文
    context = ConversationContext(db=db, max_history=config.get("memory", {}).get("max_recent", 20))
    await context.initialize()
    
    # 注入会话上下文到工具（此时 context 已初始化完毕）
    set_session_context(context)

    # 初始化子 Agent 独立数据库（不污染主脑 feiyun.db）
    AGENT_DB_PATH = os.path.join(DATA_DIR, "agent_data.db")
    agent_db = FeiyunDatabase(AGENT_DB_PATH)
    await agent_db.initialize()
    agent_context = ConversationContext(db=agent_db, max_history=config.get("memory", {}).get("max_recent", 20))
    await agent_context.initialize()
    logger.info(f"子 Agent 独立数据库已初始化: {AGENT_DB_PATH}")

    # 初始化 Agent 配置管理器（先初始化，因为工作空间需要引用它）
    agent_config_manager = AgentConfigManager()
    set_agent_api_manager(agent_config_manager)
    logger.info(f"Agent 配置系统已初始化: {len(agent_config_manager.list_agents())} 个 Agent")

    # 初始化工作空间管理器
    ws_manager = WorkspaceManager(agent_config_manager=agent_config_manager)
    ws_manager._db = db  # 注入主脑数据库引用，用于日志查询
    ws_manager._agent_db = agent_db  # 注入子Agent独立数据库引用
    _ws_manager = ws_manager  # 保存到全局，供 shutdown 使用
    set_ws_api_manager(ws_manager)
    set_ws_tool_manager(ws_manager)
    logger.info("工作空间系统已初始化")

    # 初始化主动引擎
    push_engine = PushEngine(db=db)
    adaptive_learner = AdaptiveLearner()
    active_scheduler = ActiveScheduler(
        push_engine=push_engine,
        adaptive_learner=adaptive_learner,
        workspace_manager=ws_manager,
        memory_selector=memory_selector,
        provider=provider,
        persona_manager=persona_manager,
    )
    set_active_api_deps(push_engine, active_scheduler)
    set_push_scheduler(active_scheduler)
    _active_scheduler = active_scheduler  # 保存到全局，供 shutdown 使用

    # 初始化冷启动器
    from active_engine.cold_start import ColdStarter
    _cold_starter = ColdStarter(
        provider=provider,
        memory=memory_selector,
        persona_manager=persona_manager,
        db=db,  # 新增，用于查普通消息上下文
    )
    _active_scheduler.set_cold_starter(_cold_starter)

    # 启动调度器
    asyncio.create_task(active_scheduler.start())
    logger.info("主动引擎已初始化并启动")

    # 启动时清理过期推送消息（保留24小时）
    push_engine.cleanup_old_messages(keep_hours=24)

    # 初始化知识库管理器
    knowledge_manager = KnowledgeBaseManager()
    set_kb_api_manager(knowledge_manager)
    logger.info(f"知识库系统已初始化: {len(knowledge_manager.list_knowledge_bases())} 个知识库")

    # 注入数据库到通知 API
    
    # 启动时清理旧通知（保留 200 条）
    try:
        cleaned = await db.cleanup_old_notifications(max_count=50)
        if cleaned:
            logger.info(f"启动时清理了 {cleaned} 条旧通知")
    except Exception as e:
        logger.debug(f"通知清理跳过: {e}")

    # 初始化普通消息持久化（改用独立的 push_messages 表）
    set_push_deps(db, memory_selector, provider)
    
    # 迁移旧数据：将 conversations 表中 __push_channel__ 的数据迁移到 push_messages 表
    try:
        import uuid
        from api.push_messages import PUSH_CHANNEL_ID
        old_conv = await db.get_conversation(PUSH_CHANNEL_ID)
        if old_conv and old_conv.content:
            old_msgs = old_conv.content
            existing_count = await db.count_push_messages()
            if existing_count == 0 and old_msgs:
                for msg in old_msgs:
                    role = msg.get("role", "assistant")
                    content = msg.get("content", "")
                    source = msg.get("source", "")
                    # 保留原始时间戳，避免排序混乱
                    orig_ts = msg.get("timestamp", time.time())
                    msg_data = {
                        "id": uuid.uuid4().hex[:12],
                        "role": role,
                        "content": content,
                        "type": "chat_reply",
                        "priority": "normal",
                        "source": source,
                        "created_at": orig_ts,
                    }
                    await db.add_push_message(msg_data)
                logger.info(f"已迁移 {len(old_msgs)} 条旧普通消息到 push_messages 表（保留原始时间戳）")
    except Exception as e:
        logger.warning(f"旧消息迁移跳过: {e}")
    
    # 将持久化存储注册为推送引擎的回调
    async def _on_push_message(msg_dict: dict):
        """推送消息回调：按类型分流存储"""
        logger.info(f"[消息回调] 收到消息: type={msg_dict.get('type')}, target={msg_dict.get('target')}, content={msg_dict.get('content','')[:30]}")
        # 系统通知 → 存 SQLite 通知表
        if msg_dict.get("type") in ("system_event",) or msg_dict.get("target") == "notification":
            try:
                await db.add_notification(msg_dict)
            except Exception as e:
                logger.warning(f"存储通知失败: {e}")
        # 普通消息 → 存到 push_messages 表（展示用）+ context（上下文用）
        else:
            try:
                content = msg_dict.get("content", "")
                source = msg_dict.get("source", "")
                priority = msg_dict.get("priority", "normal")
                msg_id = msg_dict.get("id", "")
                
                # ✅ 存到展示用的 push_messages 表
                from api.push_messages import add_to_push_channel, set_last_push_id
                metadata = {"source": source, "priority": priority, "msg_type": "active_push"}
                await add_to_push_channel("assistant", content, metadata=metadata)
                
                # ✅ 存到 context（让 AI 回复时能读到主动推送的上下文）
                await context.add_message(PUSH_CHANNEL_ID, "assistant", content)
                
                if msg_id:
                    set_last_push_id(msg_id)
            except Exception as e:
                logger.warning(f"存储普通消息失败: {e}")
    push_engine.set_store_callback(lambda msg: asyncio.ensure_future(_on_push_message(msg)))
    logger.info("普通消息推送频道已初始化")

    # 恢复工作空间状态（检查是否有未完成的任务）
    paused_workspaces = ws_manager.recover_workspaces()
    if paused_workspaces:
        for ws in paused_workspaces:
            logger.info(f"  工作空间 [{ws.get('name')}] 有未完成的任务，已标记为 paused，等待用户确认")

    # 清理过期会话（保留30天）
    cleaned = await db.cleanup_old_sessions(keep_days=30)
    if cleaned:
        logger.info(f"启动时自动清理了 {cleaned} 个过期会话")

    # 清理旧通知，最多保留50条
    cleaned_notif = await db.cleanup_old_notifications(max_count=50)
    if cleaned_notif:
        logger.info(f"启动时自动清理了 {cleaned_notif} 条旧通知")

    # 启动时执行一次艾宾浩斯记忆清理（即使服务器关机多天，开机时自动清理过期记忆）
    if hasattr(memory_selector, 'get_backend'):
        memoria = memory_selector.get_backend()
        expired = 0
        if hasattr(memoria, 'cleanup_expired'):
            expired = memoria.cleanup_expired()
        if expired > 0:
            logger.info(f"启动时自动清理了 {expired} 条过期记忆")
        
        # 24小时自动清理定时任务
        async def _periodic_cleanup():
            while True:
                await asyncio.sleep(86400)  # 24小时
                try:
                    if hasattr(memoria, 'cleanup_expired'):
                        cleaned = memoria.cleanup_expired()
                        if cleaned > 0:
                            logger.info(f"定时清理了 {cleaned} 条过期记忆")
                except Exception as e:
                    logger.warning(f"定时清理失败: {e}")
        
        asyncio.create_task(_periodic_cleanup())
        logger.info("记忆清理定时任务已启动（每24小时）")
    
    # 启动时执行一次按天压缩（生成日摘要，不删消息）
    try:
        _p_name = "AI"
        try:
            _p = persona_manager.get_active_persona()
            _p_name = _p.get("name", "AI")
        except Exception:
            pass
        asyncio.create_task(compress_push(db, provider, persona_name=_p_name))
    except Exception as e:
        logger.warning(f"按天压缩启动失败（不影响主流程）: {e}")
    
    agent_loop = AgentRunner(
        provider=provider,
        context=context,
        memory=memory_selector,
        persona_manager=persona_manager,
        tool_registry=tool_registry,
        mcp_manager=mcp_manager,
        skills_manager=skills_manager,
        config=config,
        max_rounds=tools_cfg.get("max_agent_rounds", 20),
        provider_manager=provider_manager,
        scheduler=active_scheduler,  # V2主动引擎，支持AI自主通道
    )

    # 更新依赖
    chat.set_runner(agent_loop)
    chat.set_conversation_logger(conversation_logger)
    # 注入子 Agent 路由依赖到聊天 API
    set_chat_agent_deps(
        agent_config_manager=agent_config_manager,
        provider_manager=provider_manager,
        agent_context=agent_context,
        memory=memory_selector,
        persona_manager=persona_manager,
        tool_registry=tool_registry,
        main_config=config,
    )
    admin.set_admin_deps(config, persona_manager, memory_selector, tool_registry, mcp_manager, skills_manager, agent_loop, provider_manager)
    set_push_runner(agent_loop)
    # 注入工作空间执行依赖（包含子 Agent 独立上下文 + 主脑执行器）
    set_workspace_exec_deps(
        agent_config_manager=agent_config_manager,
        provider_manager=provider_manager,
        context=context,
        agent_context=agent_context,
        memory=memory_selector,
        persona_manager=persona_manager,
        tool_registry=tool_registry,
        main_config=config,
        agent_loop=agent_loop,
    )
    logger.info("Agent 执行器已初始化")

    logger.info("FeiyunMY-Bot 启动完成!")
    logger.info(f"  模型: {provider_cfg.get('model')}")
    logger.info(f"  人格: {active_persona}")
    logger.info(f"  记忆: {'MemoriaDB' if memory_enabled else 'Simple'} (开关: {memory_enabled})")
    logger.info(f"  存储: SQLite ({DB_PATH})")
    if AUTH_ENABLED:
        logger.info(f"  鉴权: 已启用（本机回环免令牌: {AUTH_LOCAL_BYPASS}，令牌见 {AUTH_TOKEN_FILE}）")


async def shutdown():
    global _active_scheduler, _ws_manager
    # 关闭主动引擎并保存自适应参数
    if _active_scheduler:
        await _active_scheduler.stop()
        logger.info("主动引擎已关闭，自适应参数已保存")

    # 关闭工作空间：将所有 active 工作空间标记为 paused
    if _ws_manager:
        for ws in _ws_manager.list_workspaces(status="active"):
            _ws_manager.update_workspace(ws["workspace_id"], {"status": "paused"})
            logger.info(f"关闭时暂停工作空间: {ws.get('name')}")

    await provider.close()
    await provider_manager.close_all()
    if context:
        await context.flush()  # 确保缓存数据写入数据库
        await context.close()
    logger.info("FeiyunMY-Bot 已关闭")


# 挂载静态文件（WebUI）
WEBUI_DIR = os.path.join(os.path.dirname(__file__), "webui", "dist")
app.mount("/admin", StaticFiles(directory=WEBUI_DIR, html=True), name="webui")


@app.get("/")
async def root():
    return {"message": "FeiyunMY-Bot API", "admin": "/admin"}


@app.get("/favicon.ico")
async def favicon():
    return {}


# ==========================================
# 鉴权接口（移动端 / 局域网访问使用）
# ==========================================
from pydantic import BaseModel


class LoginPayload(BaseModel):
    token: str = ""


@app.get("/api/auth/status")
async def auth_status(request: Request):
    """查询鉴权状态：前端据此决定是否弹出令牌输入框"""
    return {
        "auth_enabled": AUTH_ENABLED,
        "local_bypass": AUTH_LOCAL_BYPASS and _is_local_request(request),
        "authenticated": (not AUTH_ENABLED)
        or (AUTH_LOCAL_BYPASS and _is_local_request(request))
        or _token_ok(_extract_token(request)),
    }


@app.post("/api/auth/login")
async def auth_login(payload: LoginPayload):
    """用令牌换取 HttpOnly Cookie（浏览器端后续请求自动携带）"""
    token = (payload.token or "").strip()
    if not AUTH_ENABLED or _token_ok(token):
        response = JSONResponse({"ok": True, "auth_enabled": AUTH_ENABLED})
        if AUTH_ENABLED:
            response.set_cookie(
                key=AUTH_COOKIE_NAME,
                value=ACCESS_TOKEN,
                max_age=AUTH_COOKIE_MAX_AGE,
                httponly=True,
                samesite="lax",
            )
        return response
    return JSONResponse({"ok": False, "message": "访问令牌不正确"}, status_code=401)


@app.post("/api/auth/logout")
async def auth_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(AUTH_COOKIE_NAME)
    return response


if __name__ == "__main__":
    server_cfg = config.get("server", {})
    uvicorn.run(
        "main:app",
        host=server_cfg.get("host", "0.0.0.0"),
        port=server_cfg.get("port", 8765),
        reload=False,
        access_log=False,  # 关闭 HTTP 访问日志（200 OK 等）
        log_level="info",  # 保留 INFO 级别的应用日志
    )
