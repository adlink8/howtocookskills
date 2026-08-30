# Multi-Agent Adapter Guide

HowToCook 的核心不绑定任何 Agent 框架。

核心由三部分组成：

1. `SKILL.md`：行为与教学规则。
2. `scripts/howtocook_cli.py`：稳定的机器接口。
3. `data/`、`references/`、`generated/`：知识与索引。

不同 Agent 只负责两件事：**加载 `SKILL.md`**，以及**把本地 CLI 暴露成可调用工具**。

> 仓库中的 `skill.json` 是本项目自己的可移植清单，不宣称是行业统一 Skill 标准。

## 通用 Shell / 任意 Agent

只要 Agent 能执行本地命令，就可以直接接入：

```bash
python scripts/howtocook_cli.py search --name 西红柿 --pretty
python scripts/howtocook_cli.py recipe 西红柿炒鸡蛋 --pretty
python scripts/howtocook_cli.py annotate 宫保鸡丁 --pretty
python scripts/howtocook_cli.py diagnose 肉发柴 --pretty
python scripts/howtocook_cli.py principles --id protein --pretty
python scripts/howtocook_cli.py status --pretty
```

CLI 默认输出统一 JSON envelope：

```json
{
  "ok": true,
  "action": "search",
  "data": []
}
```

失败时：

```json
{
  "ok": false,
  "action": "recipe",
  "error": {
    "code": "recipe_not_found",
    "message": "..."
  }
}
```

Agent 不应解析终端自然语言，只需要读取 JSON。

## Claude Code

Claude Code 只是一个薄适配层，不再是仓库的默认运行时。

推荐做法：

- 将仓库放在任意可访问位置，不依赖 `~/.claude/skills/...` 固定路径。
- 把 `SKILL.md` 作为技能说明加载。
- 允许执行 `python scripts/howtocook_cli.py ...`。
- 不在 Claude 专用配置中复制核心烹饪逻辑；Claude 侧只保存入口信息。

## Codex

推荐做法：

- 在项目级说明中指向本仓库的 `SKILL.md`。
- 给 Codex 本地 shell / Python 执行权限。
- 所有菜谱搜索、原理标注、失败反查都经 CLI 完成。
- Codex 专用规则只描述“什么时候调用 HowToCook”，不要复制知识库正文。

这样同一个仓库既能作为 Codex 的项目知识，也能被其他 Agent 复用。

## Pi Agent

推荐把 HowToCook 注册成一个外部工具能力：

```text
Agent
  -> howtocook.search
  -> howtocook.recipe
  -> howtocook.annotate
  -> howtocook.diagnose
```

最简单的实现是每个工具映射到一个 CLI 子命令，并把 stdout JSON 直接返回给 Agent。

如果 Pi Runtime 支持 Skill 文档，则同时加载 `SKILL.md`；如果只支持工具，则在 system/instructions 中引用 `SKILL.md` 的核心规则。

## OpenAI Agents SDK

推荐把 CLI 再包一层 function tool：

```text
function tool arguments
        ↓
subprocess: python scripts/howtocook_cli.py ...
        ↓
JSON envelope
        ↓
Agent
```

工具层只负责参数校验和调用 CLI；烹饪知识、规则和数据仍保留在本仓库，避免形成第二份逻辑。

## 适配原则

任何新 Agent 接入都遵循：

```text
Agent-specific adapter
        ↓
SKILL.md + skill.json
        ↓
portable CLI
        ↓
recipe / principles / generated corpus
```

禁止：

- 在核心代码里检测“当前是不是 Claude/Codex/Pi”。
- 使用某个 Agent 的绝对安装目录作为数据路径。
- 每个平台复制一套菜谱和原理规则。
- 把自然语言输出当作跨 Agent API。

新增 Agent 时，优先只增加 `adapters/<agent>.md` 或很薄的 wrapper。
