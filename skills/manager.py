"""
Skills 技能管理
支持自由增删技能，支持从 skillsmp.com 下载的 zip 包安装
每个 Skill 为一个文件夹，内含 SKILL.md 定义文件
"""
import os
import json
import shutil
import zipfile
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

SKILLS_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "skills", "installed")
SKILLS_INDEX_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "skills", "index.json")


class SkillsManager:
    """技能管理器"""

    def __init__(self):
        os.makedirs(SKILLS_DATA_DIR, exist_ok=True)
        self._skills: Dict[str, dict] = {}
        self._load()

    def _load(self):
        """从 index 文件和文件夹加载技能"""
        self._skills = {}

        # 从 index.json 加载元数据
        if os.path.exists(SKILLS_INDEX_FILE):
            try:
                with open(SKILLS_INDEX_FILE, "r", encoding="utf-8") as f:
                    index_data = json.load(f)
                    self._skills = index_data
            except Exception as e:
                logger.error(f"加载技能索引失败: {e}")

        # 扫描已安装的文件夹，确保同步
        if os.path.exists(SKILLS_DATA_DIR):
            for folder_name in os.listdir(SKILLS_DATA_DIR):
                folder_path = os.path.join(SKILLS_DATA_DIR, folder_name)
                if os.path.isdir(folder_path):
                    if folder_name not in self._skills:
                        # 文件夹存在但不在索引中，读取 SKILL.md
                        skill = self._read_skill_from_folder(folder_name, folder_path)
                        if skill:
                            self._skills[folder_name] = skill

        self._save()
        logger.info(f"加载了 {len(self._skills)} 个技能")

    def _save(self):
        """保存技能索引"""
        try:
            os.makedirs(os.path.dirname(SKILLS_INDEX_FILE), exist_ok=True)
            with open(SKILLS_INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(self._skills, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存技能索引失败: {e}")

    def _read_skill_from_folder(self, name: str, folder_path: str) -> Optional[dict]:
        """从技能文件夹读取 SKILL.md 等信息"""
        skill_file = os.path.join(folder_path, "SKILL.md")
        description = ""
        prompt = ""

        if os.path.exists(skill_file):
            try:
                with open(skill_file, "r", encoding="utf-8") as f:
                    content = f.read()
                # 提取第一行作为描述
                lines = content.strip().split("\n")
                description = lines[0].replace("#", "").strip() if lines else name
                prompt = content[:500]  # 取前500字符作为 prompt
            except Exception as e:
                logger.error(f"读取 SKILL.md 失败 {name}: {e}")

        return {
            "name": name,
            "description": description or name,
            "prompt": prompt,
            "enabled": True,
            "installed_at": datetime.fromtimestamp(
                os.path.getctime(folder_path)
            ).isoformat() if os.path.exists(folder_path) else datetime.now().isoformat(),
        }

    # ─── 公共 API ───

    def list_skills(self) -> List[dict]:
        """列出所有技能"""
        return [self._skills[s] for s in self._skills]

    def get_skill(self, name: str) -> Optional[dict]:
        return self._skills.get(name)

    def install_from_zip(self, zip_path: str) -> dict:
        """从 zip 文件安装技能"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # 获取顶级目录名
                members = zf.namelist()
                top_dirs = set()
                for m in members:
                    parts = m.split('/')
                    if parts[0]:
                        top_dirs.add(parts[0])

                installed = []
                for dir_name in top_dirs:
                    # 提取到 skills 目录
                    extract_path = os.path.join(SKILLS_DATA_DIR, dir_name)
                    if os.path.exists(extract_path):
                        shutil.rmtree(extract_path)

                    # 提取该目录的所有文件
                    for member in members:
                        if member.startswith(dir_name + '/') or member == dir_name + '/':
                            zf.extract(member, SKILLS_DATA_DIR)

                    # 读取技能信息
                    skill = self._read_skill_from_folder(dir_name, extract_path)
                    if skill:
                        self._skills[dir_name] = skill
                        installed.append(dir_name)

            self._save()
            # 清理临时文件
            if os.path.exists(zip_path):
                os.remove(zip_path)

            return {"status": "ok", "installed": installed, "count": len(installed)}

        except Exception as e:
            logger.error(f"安装技能失败: {e}")
            return {"status": "fail", "reason": str(e)}

    def add_skill(self, name: str, description: str = "", prompt: str = "", enabled: bool = True) -> bool:
        """手动添加技能"""
        if name in self._skills:
            return False
        self._skills[name] = {
            "name": name,
            "description": description,
            "prompt": prompt,
            "enabled": enabled,
            "installed_at": datetime.now().isoformat(),
        }
        self._save()
        return True

    def update_skill(self, name: str, data: dict) -> bool:
        if name not in self._skills:
            return False
        self._skills[name].update(data)
        self._save()
        return True

    def delete_skill(self, name: str) -> bool:
        """删除技能（同时删除文件夹）"""
        if name not in self._skills:
            return False
        del self._skills[name]
        # 删除文件夹
        folder_path = os.path.join(SKILLS_DATA_DIR, name)
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
        self._save()
        return True

    def get_skill_folder(self, name: str) -> Optional[str]:
        """获取技能文件夹路径"""
        folder_path = os.path.join(SKILLS_DATA_DIR, name)
        return folder_path if os.path.isdir(folder_path) else None
