"""
人格管理器
负责加载、CRUD 和激活人格
预设人格在 persona/presets/，自定义人格在 data/personas/

关于「同名覆盖」：
    两个目录共用一个以 name 为键的命名空间。加载顺序为「先预设、后自定义」，
    因此 data/personas 下的同名文件会整份覆盖预设版本（不是字段合并）。
    这是有意允许的（用户可微调官方人格），但必须留下痕迹：
      - 覆盖时写 warning 日志
      - 用 self._origin 记录每份数据的真实来源，供面板展示
      - 允许删除自定义版本以回退到预设
"""
import os
import yaml
import logging
from typing import List, Dict, Iterator, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class PersonaManager:
    """人格管理"""

    def __init__(self, presets_dir: str = None, custom_dir: str = None):
        base = os.path.dirname(os.path.dirname(__file__))
        self._presets_dir = presets_dir or os.path.join(base, "persona", "presets")
        self._custom_dir = custom_dir or os.path.join(base, "data", "personas")
        os.makedirs(self._custom_dir, exist_ok=True)

        self._personas: Dict[str, dict] = {}
        # name -> "preset" | "custom"，记录数据真实来源，避免面板误判
        self._origin: Dict[str, str] = {}
        self._active_persona: str = "default"
        self._load_all()

    # ─── 加载 ───

    def _iter_dir(self, directory: str, label: str) -> Iterator[Tuple[str, dict]]:
        """遍历目录下的 YAML 文件，产出 (name, data)"""
        if not os.path.exists(directory):
            return
        for f in sorted(os.listdir(directory)):
            if not f.endswith(".yaml"):
                continue
            path = os.path.join(directory, f)
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
            except Exception as e:
                logger.error(f"加载{label}人格失败 {f}: {e}")
                continue
            if data and "name" in data:
                yield data["name"], data

    def _load_all(self):
        """加载所有预设和自定义人格（自定义同名时覆盖预设，并留下日志）"""
        self._personas.clear()
        self._origin.clear()

        # 1. 先加载预设
        for name, data in self._iter_dir(self._presets_dir, "预设"):
            self._personas[name] = data
            self._origin[name] = "preset"

        # 2. 再加载自定义；同名视为有意的覆盖，但必须可见
        for name, data in self._iter_dir(self._custom_dir, "自定义"):
            before = self._personas.get(name)
            if before is not None and self._origin.get(name) == "preset":
                logger.warning(
                    "人格 [%s] 被 data/personas/%s.yaml 覆盖了预设版本"
                    "（prompt %d 字 → %d 字，预设对话 %d 组 → %d 组）。"
                    "如需回退，删除该自定义文件或在管理面板中删除此人格。",
                    name, name,
                    len(before.get("prompt") or ""),
                    len(data.get("prompt") or ""),
                    len(before.get("preset_conversations") or []),
                    len(data.get("preset_conversations") or []),
                )
            self._personas[name] = data
            self._origin[name] = "custom"

        logger.info(f"加载了 {len(self._personas)} 个人格")

    def _save_persona(self, name: str, data: dict):
        """保存人格到自定义目录"""
        path = os.path.join(self._custom_dir, f"{name}.yaml")
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    # ─── 查询 ───

    def list_personas(self) -> List[dict]:
        """列出所有人格（简化版）"""
        result = []
        for p in self._personas.values():
            name = p.get("name", "")
            origin = self._origin.get(name, "custom")
            result.append({
                "name": name,
                "prompt": p.get("prompt", ""),
                "description": p.get("description", ""),
                "preset_count": len(p.get("preset_conversations", [])),
                "is_preset": origin == "preset",
                "origin": origin,
                "overrides_preset": (
                    origin == "custom"
                    and os.path.exists(os.path.join(self._presets_dir, f"{name}.yaml"))
                ),
                "is_active": name == self._active_persona,
            })
        return result

    def get_persona(self, name: str) -> dict:
        """获取人格详情"""
        return self._personas.get(name, {})

    def get_active_persona(self) -> dict:
        """获取当前激活的人格"""
        return self._personas.get(self._active_persona, self._personas.get("default", {}))

    def get_persona_detail(self, name: str) -> dict:
        """获取人格完整详情（含预设对话）"""
        return self._personas.get(name, {})

    def get_origin(self, name: str) -> str:
        """获取人格来源："preset" / "custom" / "unknown" """
        return self._origin.get(name, "unknown")

    # ─── 增删改 ───

    def create_persona(self, name: str, prompt: str, data: dict = None) -> bool:
        """创建新的人格（简化版：仅提示词+描述+预设对话）"""
        if name in self._personas:
            return False

        persona = {
            "name": name,
            "prompt": prompt,
            "description": data.get("description", "") if data else "",
            "preset_conversations": data.get("preset_conversations", []) if data else [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self._personas[name] = persona
        self._origin[name] = "custom"
        self._save_persona(name, persona)
        return True

    def update_persona(self, name: str, data: dict) -> bool:
        """更新人格；若目标是预设，会在自定义目录生成覆盖版本（并提示）"""
        if name not in self._personas:
            return False

        if self._origin.get(name) == "preset":
            logger.warning(
                "人格 [%s] 属于预设，本次修改将写入 data/personas/%s.yaml，"
                "覆盖预设版本（原文件不受影响，可删除自定义文件回退）。",
                name, name,
            )
            self._origin[name] = "custom"

        self._personas[name].update(data)
        self._personas[name]["updated_at"] = datetime.now().isoformat()
        self._save_persona(name, self._personas[name])
        return True

    def delete_persona(self, name: str) -> bool:
        """删除人格。

        - 纯自定义人格：删除文件并从内存移除
        - 覆盖了预设的自定义人格：删除覆盖文件，回退到预设内容
        - 纯预设人格：拒绝（预设本体不可删）
        """
        if name not in self._personas:
            return False

        custom_path = os.path.join(self._custom_dir, f"{name}.yaml")
        preset_path = os.path.join(self._presets_dir, f"{name}.yaml")
        has_custom = os.path.exists(custom_path)
        has_preset = os.path.exists(preset_path)

        if has_preset and not has_custom:
            logger.warning(f"拒绝删除预设人格: {name}")
            return False

        if has_custom:
            os.remove(custom_path)

        if has_preset:
            # 回退到预设内容
            try:
                with open(preset_path, "r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
            except Exception as e:
                logger.error(f"回退预设人格失败 {name}: {e}")
                data = None
            if data and "name" in data:
                self._personas[name] = data
                self._origin[name] = "preset"
                logger.info(f"已移除自定义覆盖，回退到预设版本: {name}")
                return True

        del self._personas[name]
        self._origin.pop(name, None)
        if self._active_persona == name:
            self._active_persona = "default"
        logger.info(f"已删除人格: {name}")
        return True

    def activate(self, name: str) -> bool:
        """激活人格"""
        if name not in self._personas:
            return False
        self._active_persona = name
        logger.info(f"激活人格: {name}")
        return True

    def reload_personas(self):
        """从磁盘重新加载所有人格（热重载 YAML 文件修改）"""
        self._load_all()
        # 确保当前激活的人格仍然有效
        if self._active_persona not in self._personas:
            self._active_persona = "default" if "default" in self._personas else list(self._personas.keys())[0]
        logger.info(f"人格热重载完成，共 {len(self._personas)} 个人格")

    @property
    def active_name(self) -> str:
        return self._active_persona
