# Pi Agent Adapter

推荐把 HowToCook 暴露成一组稳定工具，而不是把烹饪逻辑重写进 Pi Runtime。

## 工具建议

```text
howtocook.search
howtocook.recipe
howtocook.annotate
howtocook.diagnose
howtocook.principles
howtocook.status
```

每个工具只需把参数映射到 `scripts/howtocook_cli.py` 对应子命令，并将 stdout JSON 原样返回给 Agent。

## 指令层

- Runtime 支持 Skill 文档：加载 `SKILL.md`。
- Runtime 只支持 system/instructions：引用或注入 `SKILL.md` 的核心规则。
- 不在 Pi adapter 中复制菜谱、原理目录或失败索引。

这样后续替换 Pi 内核、模型或工具协议时，烹饪核心无需重写。
