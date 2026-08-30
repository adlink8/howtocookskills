# OpenAI Agents SDK Adapter

推荐把 HowToCook CLI 包装成 function tools，核心仓库保持框架无关。

## 结构

```text
Agents SDK function tool
        ↓
参数校验
        ↓
python scripts/howtocook_cli.py <action> ...
        ↓
JSON envelope
        ↓
Agent
```

## 工具边界

建议一一映射：

- `search_recipes`
- `get_recipe`
- `annotate_recipe`
- `diagnose_cooking_failure`
- `get_cooking_principles`
- `get_skill_status`

工具 wrapper 不应包含烹饪知识，只做参数到 CLI 的映射。Agent instructions 使用 `SKILL.md`；知识和索引继续由本仓库统一维护。

这样即使后续更换模型、Agent 编排方式或工具传输协议，也无需复制或重写核心烹饪逻辑。
