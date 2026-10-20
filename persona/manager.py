"""
人格管理器
负责加载、CRUD 和激活人格
预设人格在 persona/presets/，自定义人格在 data/personas/
"""
import os
import yaml
import shutil
import logging
from typing import List, Dict, Optional
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
        self._active_persona: str = "default"
        self._load_all()

    def _load_all(self):
        """加载所有预设和自定义人格"""
        # 加载预设
        if os.path.exists(self._presets_dir):
            for f in os.listdir(self._presets_dir):
                if f.endswith(".yaml"):
                    path = os.path.join(self._presets_dir, f)
                    try:
                        with open(path, "r", encoding="utf-8") as fh:
                            data = yaml.safe_load(fh)
                            if data and "name" in data:
                                self._personas[data["name"]] = data
                    except Exception as e:
                        logger.error(f"加载预设人格失败 {f}: {e}")

        # 加载自定义
        if os.path.exists(self._custom_dir):
            for f in os.listdir(self._custom_dir):
                if f.endswith(".yaml"):
                    path = os.path.join(self._custom_dir, f)
                    try:
                        with open(path, "r", encoding="utf-8") as fh:
                            data = yaml.safe_load(fh)
                            if data and "name" in data:
                                self._personas[data["name"]] = data
                    except Exception as e:
                        logger.error(f"加载自定义人格失败 {f}: {e}")

        logger.info(f"加载了 {len(self._personas)} 个人格")

    def _save_persona(self, name: str, data: dict):
        """保存人格到自定义目录"""
        path = os.path.join(self._custom_dir, f"{name}.yaml")
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    def list_personas(self) -> List[dict]:
        """列出所有人格（简化版）"""
        return [
            {
                "name": p.get("name", ""),
                "prompt": p.get("prompt", ""),
                "description": p.get("description", ""),
                "preset_count": len(p.get("preset_conversations", [])),
                "is_preset": os.path.exists(os.path.join(self._presets_dir, f"{p.get('name', '')}.yaml")),
                "is_active": p.get("name", "") == self._active_persona,
            }
            for p in self._personas.values()
        ]

    def get_persona(self, name: str) -> dict:
        """获取人格详情"""
        return self._personas.get(name, {})

    def get_active_persona(self) -> dict:
        """获取当前激活的人格"""
        return self._personas.get(self._active_persona, self._personas.get("default", {}))

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
        self._save_persona(name, persona)
        return True

    def update_persona(self, name: str, data: dict) -> bool:
        """更新人格"""
        if name not in self._personas:
            return False
        
        self._personas[name].update(data)
        self._personas[name]["updated_at"] = datetime.now().isoformat()
        self._save_persona(name, self._personas[name])
        return True

    def get_persona_detail(self, name: str) -> dict:
        """获取人格完整详情（含预设对话）"""
        return self._personas.get(name, {})

    def delete_persona(self, name: str) -> bool:
        """删除人格（只能删除自定义的）"""
        preset_path = os.path.join(self._presets_dir, f"{name}.yaml")
        if os.path.exists(preset_path):
            return False  # 不能删除预设
        
        if name not in self._personas:
            return False
        
        custom_path = os.path.join(self._custom_dir, f"{name}.yaml")
        if os.path.exists(custom_path):
            os.remove(custom_path)
        
        del self._personas[name]
        if self._active_persona == name:
            self._active_persona = "default"
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
        self._personas.clear()
        self._load_all()
        # 确保当前激活的人格仍然有效
        if self._active_persona not in self._personas:
            self._active_persona = "default" if "default" in self._personas else list(self._personas.keys())[0]
        logger.info(f"人格热重载完成，共 {len(self._personas)} 个人格")

    @property
    def active_name(self) -> str:
        return self._active_persona
