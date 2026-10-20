"""
上下文组装
消息列表组装、每日增量压缩、分层摘要注入（从 agent/runner.py 抽出）。
"""
import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ContextBuilderMixin:
    """上下文组装 mixin；宿主类需提供 self.provider / self.context / self.persona_manager。"""

    # ─── 消息组装 ───

    async def build_messages(
        self,
        system_prompt: str,
        memories: List[Dict],
        session_id: str,
        persona_enabled: bool = True,
        agent_config: Optional[dict] = None,
    ) -> List[Dict]:
        """
        组装完整的消息列表（1条人格system + 记忆system + 预设对话 + 历史对话）

        Args:
            system_prompt: 系统提示词
            memories: 检索到的记忆
            session_id: 会话 ID
            persona_enabled: 是否启用人格
            agent_config: 子 Agent 配置（可选），传入时使用子 Agent 的人格/模型设定
        """
        messages = []

        # 1. 人格设定 + 当前时间 + 自主通道规则（合并）
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        persona_content = system_prompt + "\n当前时间：" + now + "（时区：CST 中国标准时间）"

        # V2.3: AI自主行动能力——自然语言表达，系统自动执行
        persona_content += (
            "\n\n【自主行动】你可以自由决定想做什么。"
            "如果需要查资料、读文件或做其他事情，直接在对话中自然地说出来，"
            "系统会自动帮你执行。不需要特殊格式，像和人聊天一样自然就好。"
        )
        messages.append({"role": "system", "content": persona_content})

        # 2. 历史记忆（你记得什么）—— 注入过滤
        if memories:
            ctx = "以下是之前的对话记忆，不反映当前状态。如果需要实时信息，请使用工具查询。\n"
            
            # 类型偏移表（偏好最重要门槛最低，查询最不重要门槛最高）
            TYPE_OFFSET = {
                "偏好": -0.08, "事实": -0.04, "状态":  0.00,
                "事件":  0.04, "查询":  0.08, "未知":  0.10,
            }
            
            # 检索总数因子：记忆越少门槛越低，让AI多回忆
            total = len(memories)
            if total <= 2:
                count_factor = 0.6
            elif total <= 5:
                count_factor = 0.8
            elif total <= 10:
                count_factor = 0.9
            else:
                count_factor = 1.0
            
            # 按动态阈值过滤并注入
            injected = 0
            for m in memories:
                rank = m.get("rank_score", 0)
                imp = m.get("importance", 0.5)
                mtype = m.get("memory_type", "未知")
                type_offset = TYPE_OFFSET.get(mtype, 0.10)
                
                # 动态阈值 = 基值 + 类型偏移 - 重要性权重 - rank权重 x 总数因子
                filter_threshold = (0.35 + type_offset - 0.15 * imp - 0.10 * rank) * count_factor
                filter_threshold = max(0.05, min(0.55, filter_threshold))
                
                if rank < filter_threshold:
                    continue
                
                # V4: 添加来源/时间/情感标记
                meta = m.get("metadata", {}) or {}
                source = m.get("_source", "inner")
                
                created_at = meta.get("created_at", m.get("created_at", 0))
                time_tag = ""
                if created_at:
                    import datetime as _dt
                    dt = _dt.datetime.fromtimestamp(created_at)
                    now = _dt.datetime.now()
                    if dt.date() == now.date():
                        time_tag = dt.strftime("今天%H:%M")
                    elif (now - dt).days == 1:
                        time_tag = "昨天" + dt.strftime("%H:%M")
                    else:
                        time_tag = dt.strftime("%m-%d")
                
                emotion_tag = meta.get("emotion_label_cn", "")
                if emotion_tag:
                    emotion_tag = "·" + emotion_tag
                
                if source == "cloud_activated":
                    source_tag = "[云中跃出"
                else:
                    source_tag = "[记忆"
                
                if time_tag:
                    source_tag += "·" + time_tag
                if emotion_tag:
                    source_tag += emotion_tag
                source_tag += "]"
                
                ctx += f"  {source_tag} {m.get('content', '')}\n"
                injected += 1
                if injected >= 5:
                    break
            
            # 保底：一条都没选上就取最好的1条
            if injected == 0 and memories:
                m0 = memories[0]
                meta0 = m0.get("metadata", {}) or {}
                source0 = m0.get("_source", "inner")
                ca0 = meta0.get("created_at", m0.get("created_at", 0))
                tt0 = ""
                if ca0:
                    import datetime as _dt2
                    dt0 = _dt2.datetime.fromtimestamp(ca0)
                    n0 = _dt2.datetime.now()
                    if dt0.date() == n0.date():
                        tt0 = dt0.strftime("今天%H:%M")
                    elif (n0 - dt0).days == 1:
                        tt0 = "昨天" + dt0.strftime("%H:%M")
                    else:
                        tt0 = dt0.strftime("%m-%d")
                et0 = meta0.get("emotion_label_cn", "")
                if et0:
                    et0 = "·" + et0
                st0 = "[云中跃出" if source0 == "cloud_activated" else "[记忆"
                if tt0:
                    st0 += "·" + tt0
                if et0:
                    st0 += et0
                st0 += "]"
                ctx += f"  {st0} {m0.get('content', '')}\n"
            
            messages.append({"role": "system", "content": ctx})

        # 3. 人格示例（你怎么说话）
        if persona_enabled:
            if agent_config and agent_config.get("persona_id"):
                persona = self.persona_manager.get_persona(agent_config["persona_id"])
            else:
                persona = self.persona_manager.get_active_persona()
            convs = persona.get("preset_conversations", [])
            if convs:
                lines = ["以下是对话风格示例，请参考这些示例的回复风格和语气："]
                for c in convs:
                    if "user" in c and "assistant" in c:
                        lines.append(f"用户: {c['user']}")
                        lines.append(f"你: {c['assistant']}")
                messages.append({"role": "system", "content": "\n".join(lines)})

        
        
        # 4. 历史对话
        # 普通消息频道：走正常get_history（受max_turns控制），额外注入摘要
        from api.push_messages import PUSH_CHANNEL_ID
        if session_id == PUSH_CHANNEL_ID:
            history = await self.context.get_history(session_id)
            # 注入历史摘要（分层：近的完整，远的精简，超5天跳过）
            try:
                summaries = await self._get_layered_summaries()
                for s in summaries:
                    messages.append({"role": "system", "content": s})
            except Exception:
                pass
        else:
            history = await self.context.get_history(session_id)
        
        for msg in history:
            role = msg["role"]
            if role in ("tool",):
                if msg.get("tool_call_id"):
                    messages.append({"role": "tool", "content": msg["content"], "tool_call_id": msg["tool_call_id"]})
                else:
                    messages.append({"role": "system", "content": f"[工具结果] {msg.get('content', '')}"})
            else:
                # 不再把reasoning_content拼入content，前端从reasoning字段独立读取
                # 给消息加上时间戳，让AI知道每条消息的发送时间
                _content = msg.get("content", "")
                _ts = msg.get("timestamp", 0)
                if _ts and role in ("user", "assistant"):
                    try:
                        from datetime import datetime as _dt
                        _time_str = _dt.fromtimestamp(_ts).strftime("%m-%d %H:%M")
                        _content = f"[{_time_str}] {_content}"
                    except Exception:
                        pass
                messages.append({"role": role, "content": _content})

        return messages

    
    async def _check_daily_compress(self):
        """检查昨天消息是否已压缩，未压缩则触发增量压缩（只存摘要，不删消息）"""
        try:
            from datetime import datetime, timezone, timedelta
            
            now = datetime.now(timezone.utc)
            today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
            yesterday_start = today_start - timedelta(days=1)
            yesterday_end = today_start
            
            db = self.context.db
            
            # 查昨天是否有摘要
            yesterday_summaries = await db.get_push_messages_in_range(
                yesterday_start.timestamp(), yesterday_end.timestamp(),
                msg_type="daily_summary"
            )
            if yesterday_summaries:
                return  # 已有摘要，跳过
            
            # 查昨天的原始消息
            yesterday_msgs = await db.get_push_messages_in_range(
                yesterday_start.timestamp(), yesterday_end.timestamp(),
                msg_type="chat_reply"
            )
            if len(yesterday_msgs) < 3:
                return  # 消息太少，不值得压缩
            
            # 查今天的轮次，确认是否真的聊够了
            today_msgs = await db.get_push_messages_in_range(
                today_start.timestamp(), now.timestamp(),
                msg_type="chat_reply"
            )
            today_turns = sum(1 for m in today_msgs if m.get("role") == "user")
            if today_turns < 10:
                return  # 今天聊得还不够多
            
            logger.info(f"增量压缩: 昨天{len(yesterday_msgs)}条消息，今天{today_turns}轮")
            
            from active_engine.push_compressor import _generate_summary, _ts_to_date_str
            
            # 获取人格名称
            persona_name = "AI"
            try:
                p = self.persona_manager.get_active_persona()
                persona_name = p.get("name", "AI")
            except Exception:
                pass
            
            date_str = _ts_to_date_str(yesterday_start.timestamp())
            if not date_str:
                return
            
            # 所有消息都压缩，不保留（原始消息保留在push_messages表供展示）
            summary = await _generate_summary(yesterday_msgs, self.provider, date_str, persona_name)
            if not summary:
                return
            
            # 只存摘要，不删任何原始消息
            await db.add_push_message({
                "id": f"daily_summary_{date_str}",
                "role": "system",
                "content": summary,
                "type": "daily_summary",
                "priority": "normal",
                "source": "daily_compress",
                "created_at": yesterday_start.timestamp(),
            })
            logger.info(f"增量压缩: {date_str} 摘要已生成（原始消息全保留）")
            
            # 摘要滚动：超过10条删最早的
            from active_engine.push_compressor import _roll_summaries
            all_summaries = await db.get_push_messages_by_type("daily_summary")
            await _roll_summaries(db, all_summaries)
            
        except Exception as e:
            logger.warning(f"增量压缩失败（不影响主流程）: {e}")

    async def _get_layered_summaries(self) -> list:
        """获取分层摘要：最近1天完整，2~5天精简，超5天跳过"""
        try:
            db = self.context.db
            summaries = await db.get_push_messages_by_type("daily_summary")
            if not summaries:
                return []
            
            summaries.sort(key=lambda s: s.get("created_at", 0), reverse=True)
            
            now = time.time()
            result = []
            for s in summaries:
                ts = s.get("created_at", 0)
                days_ago = (now - ts) / 86400
                content = s.get("content", "")
                if not content:
                    continue
                
                if days_ago <= 1.5:
                    # 最近1天：完整注入
                    result.append(content)
                elif days_ago <= 5:
                    # 2~5天：精简到一句话（取第一句）
                    first_sentence = content.split("。")[0] + "。" if "。" in content else content[:60]
                    result.append(f"[历史] {first_sentence}")
                # 超过5天：跳过，不注入
            
            if result:
                logger.info(f"分层摘要: 注入 {len(result)} 条")
            return result
        except Exception as e:
            logger.warning(f"获取分层摘要失败: {e}")
            return []
