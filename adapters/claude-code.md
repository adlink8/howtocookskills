# Claude Code Adapter

Claude Code 只作为调用层，不承载核心烹饪逻辑。

## 接入合同

1. 让 Claude Code 能读取仓库根目录的 `SKILL.md`。
2. 允许执行 `python scripts/howtocook_cli.py ...`。
3. 菜谱事实、原理标注和失败索引统一从 CLI 获取。
4. 不依赖固定 `~/.claude/skills/howtocook` 路径；仓库可以位于任意目录。

## 推荐调用

```bash
python scripts/howtocook_cli.py search --name 西红柿
python scripts/howtocook_cli.py recipe 西红柿炒鸡蛋
python scripts/howtocook_cli.py annotate 宫保鸡丁
python scripts/howtocook_cli.py diagnose 肉发柴
```

Claude 专用配置只负责“什么时候调用”，不要复制 `SKILL.md` 的知识正文。
