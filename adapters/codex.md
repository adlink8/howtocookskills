# Codex Adapter

Codex 适配层只负责把通用 Skill 暴露给 Agent。

## 接入合同

1. 在项目说明中引用 `SKILL.md`，不要复制其完整内容。
2. 允许 Codex 在仓库根目录执行 Python CLI。
3. 需要事实检索时优先调用 CLI，再基于 `SKILL.md` 组织回答。

## 工具映射

```text
search     -> python scripts/howtocook_cli.py search ...
recipe     -> python scripts/howtocook_cli.py recipe <name>
annotate   -> python scripts/howtocook_cli.py annotate <name>
diagnose   -> python scripts/howtocook_cli.py diagnose <symptom>
principles -> python scripts/howtocook_cli.py principles ...
```

Codex-specific instruction 应保持很薄：识别烹饪意图、调用上述接口、遵守 `SKILL.md`。
