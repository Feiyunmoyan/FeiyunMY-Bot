# 设计文档索引

项目所有设计、架构、交接文档的入口。原 `文件/` 目录已按用途拆分到这里。

## handover/ — 交接与复盘

接手项目**先看这两份**。

| 文档 | 说明 |
|---|---|
| [HANDOVER.md](handover/HANDOVER.md) | 全面交接文档，含项目目标、模块职责、历史决策 |
| [V1复盘与评测指南.md](handover/V1复盘与评测指南.md) | v1 阶段复盘：跑通了什么、缺什么、V2 该怎么评测 |

## arch/ — 架构设计

| 文档 | 说明 |
|---|---|
| [ARCH_V2.md](arch/ARCH_V2.md) | V2 总体架构 |
| [VAD_MEMORY_ARCH_V4.md](arch/VAD_MEMORY_ARCH_V4.md) | 记忆系统架构（VAD / 情感维度相关） |

## design/ — 功能设计方案

**记忆与主动引擎**

- [记忆主动引擎一体化规划.md](design/记忆主动引擎一体化规划.md)

**多 Agent 协同**

- [多Agent协同架构设计方案.md](design/多Agent协同架构设计方案.md)
- [多Agent协同架构最终设计草案.md](design/多Agent协同架构最终设计草案.md)
- [多Agent架构待解决的问题清单.md](design/多Agent架构待解决的问题清单.md)
- [多Agent架构解决方案确认清单.md](design/多Agent架构解决方案确认清单.md)

**前端**

- [前端设计方案(扩写版).md](design/前端设计方案(扩写版).md)
- [前端设计方案.txt](design/前端设计方案.txt)
- [前端交接文档.md](design/前端交接文档.md)

**接口与人格**

- [新增后端API文档.md](design/新增后端API文档.md)
- [人格设定.txt](design/人格设定.txt)

## raw/ — 原始素材

早期对话记录（`1.txt` ~ `8.txt`），是设计思路的来源材料，非正式文档。体量较大，可按需查阅。

## assets/ — 素材

- `新记忆公式.jpg` — 记忆权重公式示意图

## archive/ — 旧版本归档

被新版取代的历史草稿，**仅供参考，不要作为当前设计依据**：

- `ARCH_V2 - 副本.md`（旧版架构稿）
- `人格设定 - 副本.txt`、`人格设定 - 副本 (2).txt`（旧版人格设定）

> 归档目录中的文件不进版本库（`* - 副本*` 已被 `.gitignore` 排除）。
