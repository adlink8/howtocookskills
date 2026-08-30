# HowToCook Portable Skill

一个**不绑定具体 Agent Runtime** 的个人烹饪原理导师与菜谱工具。

核心目标不是“给一道菜谱就结束”，而是把每个关键步骤拆成：

> **操作 → 目标 → 原理 → 控制变量 → 观察信号 → 失败模式 → 修正方法**

仓库可以被 Claude Code、Codex、Pi Agent、OpenAI Agents SDK 或任何能够读取 Markdown、执行本地 Python 的 Agent 复用。

## 架构

```text
Agent-specific adapter
        ↓
SKILL.md + skill.json
        ↓
scripts/howtocook_cli.py
        ↓
┌──────────────────────────────┐
│ data/dishes                  │ 原始菜谱
│ references/*                 │ 原理与学习路线
│ generated/recipe_principles  │ 原理标注语料
│ generated/failure_index      │ 失败现象反向索引
└──────────────────────────────┘
```

**核心逻辑不感知当前 Agent 是 Claude、Codex 还是 Pi。**

## 现在具备的能力

| 能力 | 说明 |
|---|---|
| 菜谱搜索 | 菜名、食材、分类、难度、时间筛选 |
| 原始菜谱 | 读取 HowToCook 菜谱事实 |
| 原理标注 | 自动映射传热、蛋白质、淀粉、水分、褐变、调味、刀工等候选原理 |
| 时间解释 | 明确“秒数是参考参数，不是目标状态” |
| 失败诊断 | 从肉柴、出水、不上色等现象反向查相关步骤和原理 |
| 理论学习 | 先学模型，后续有厨房时再做单变量实验 |
| 多 Agent 接入 | 统一 JSON CLI + 薄适配层 |

## 快速使用

无需第三方 Python 依赖。

```bash
python scripts/howtocook_cli.py search --name 西红柿 --pretty
python scripts/howtocook_cli.py recipe 西红柿炒鸡蛋 --pretty
python scripts/howtocook_cli.py annotate 宫保鸡丁 --pretty
python scripts/howtocook_cli.py diagnose 肉发柴 --pretty
python scripts/howtocook_cli.py principles --id protein --pretty
python scripts/howtocook_cli.py status --pretty
```

CLI 默认返回稳定 JSON：

```json
{
  "ok": true,
  "action": "search",
  "data": []
}
```

这使不同 Agent 可以调用同一套核心能力，而不用解析自然语言终端输出。

## Skill 文件

- `SKILL.md`：Agent-neutral 行为与教学规则
- `skill.json`：本项目的可移植能力清单与 CLI 合同
- `adapters/README.md`：Claude Code / Codex / Pi Agent / OpenAI Agents SDK 接入思路

> `skill.json` 是本项目自己的 portability manifest，不宣称是行业统一标准。

## 教学语料流水线

```bash
python -m unittest discover -s tests -v
python scripts/build_teaching_corpus.py
```

生成：

```text
generated/
├─ recipe_principles.jsonl
├─ principle_catalog.json
├─ failure_index.json
└─ manifest.json
```

当前流水线会扫描 HowToCook 菜谱，生成原理候选标签和失败反向索引。GitHub Actions 在 `main` 更新后自动重新生成这些文件。

### 当前语料规模

最近一次 CI 构建已处理：

- 356 个菜谱文件
- 337 个可解析菜谱
- 3409 个操作步骤
- 2668 个步骤命中至少一个原理标签
- 622 个步骤包含显式时间
- 70 个步骤包含显式温度
- 19 类失败候选模式

仍有少量上游菜谱格式无法被当前 parser 提取，后续继续兼容。

## 原理知识树

```text
烹饪
├─ 热与传热
├─ 蛋白质与嫩度
├─ 淀粉与粘度
├─ 蔬菜与水分
├─ 褐变与香气
├─ 调味与加入时机
├─ 刀工与尺寸
└─ 中式技法
   ├─ 炒 / 爆 / 煸
   ├─ 煎 / 炸
   ├─ 焯 / 蒸 / 煮
   ├─ 烧 / 焖 / 炖
   └─ 上浆 / 挂糊 / 勾芡
```

重点不是记住“炒 30 秒”，而是理解：

```text
食材尺寸
× 初始温度
× 锅温与恢复速度
× 火力
× 下锅量
× 含水量
→ 实际成熟过程
```

## 仓库分工

建议保持两层：

```text
adlink8/HowToCook
└─ 原始参考菜谱库，尽量跟随 upstream

adlink8/howtocookskills
└─ 个人 Skill / 原理层 / Agent 接口 / 教学语料
```

不要把大量个人 Agent 逻辑改回原始菜谱仓库，否则会增加上游同步成本。

## 多 Agent 设计原则

1. 核心事实只维护一份。
2. Agent-specific adapter 必须尽量薄。
3. 统一使用 CLI JSON 作为机器接口。
4. 不依赖固定安装目录。
5. 不把 Agent 私有 API 写进核心烹饪逻辑。
6. 原菜谱事实与 AI/规则推断分离。

详细接入方式见 [`adapters/README.md`](adapters/README.md)。

## 数据来源

菜谱数据基于 [Anduin2017/HowToCook](https://github.com/Anduin2017/HowToCook) 及本 fork 内置数据。原始菜谱用于还原步骤；本仓库新增的原理标注属于教学解释层，不应伪装成上游原文。
