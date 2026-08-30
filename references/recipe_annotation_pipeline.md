# 菜谱原理自动标注流水线

## 目标

把 HowToCook 的“步骤型菜谱”转换成“可学习、可解释、可迁移”的教学骨架，同时严格保留原始菜谱与解释层之间的边界。

```text
HowToCook 原始 Markdown
        ↓
recipe_parser.py
        ↓
结构化菜谱
        ↓
recipe_principle_annotator.py
        ↓
规则标注骨架
        ↓
Skill / LLM 深化解释
        ↓
目标 → 原理 → 变量 → 观察信号 → 失败模式 → 修正
```

## 为什么先做规则标注，再交给 LLM

直接让模型“解释整道菜”容易出现三个问题：

1. 把推断写成原菜谱事实。
2. 为了显得专业而捏造精确时间、温度或克数。
3. 每次解释结构不同，不利于长期积累和检索。

规则标注器只负责确定性工作：识别可能涉及的知识模块、提取显式时间/温度、建立统一字段。真正需要上下文判断的机制解释交给 Skill / LLM。

## 标注数据结构

每一步至少保留：

```json
{
  "step_index": 1,
  "source_step": "原始菜谱步骤",
  "principles": [
    {
      "id": "heat-transfer",
      "title": "传热与锅温",
      "goal": "...",
      "mechanism": "...",
      "variables": ["..."],
      "signals": ["..."],
      "failures": ["..."]
    }
  ],
  "explicit_times": [],
  "explicit_temperatures": [],
  "parameter_notes": []
}
```

## 当前知识标签

| ID | 知识模块 | 典型问题 |
|---|---|---|
| `heat-transfer` | 传热与锅温 | 为什么大火、为什么锅温会掉 |
| `protein` | 蛋白质与嫩度 | 为什么肉柴、鸡蛋变老 |
| `starch` | 淀粉与粘度 | 上浆、挂糊、勾芡 |
| `vegetable-water` | 蔬菜与水分 | 为什么青菜出水、发软 |
| `browning-aroma` | 褐变与香气 | 为什么煎香、为什么不上色 |
| `seasoning` | 调味与时机 | 为什么盐/醋/酱油此时放 |
| `knife-size` | 刀工与尺寸 | 为什么切丝、厚薄影响什么 |
| `water-control` | 水分控制 | 为什么沥干、收汁、加水 |

## 时间和温度处理规则

任何明确秒数、分钟数都自动标记为“参考参数”，不能直接当目标状态。

例如：

```text
大火翻炒 30 秒
```

教学层应该继续追问：

- 食材多粗/多厚？
- 一次下锅多少？
- 家庭灶还是商用灶？
- 锅多大、多厚？
- 食材是否刚从冰箱取出？
- 30 秒之后应该看到什么状态？

温度同样要区分：

- 灶具设定温度
- 锅面温度
- 油温
- 食材表面温度
- 食材中心温度

不能把这些混成一个“温度”。

## 使用方式

### 标注单道菜

```bash
python scripts/recipe_principle_annotator.py --recipe 西红柿炒鸡蛋
```

### 输出 JSON

```bash
python scripts/recipe_principle_annotator.py \
  --recipe 西红柿炒鸡蛋 \
  --format json
```

### 生成给 AI 的深化解释 Prompt

```bash
python scripts/recipe_principle_annotator.py \
  --recipe 西红柿炒鸡蛋 \
  --format prompt
```

### 直接指定菜谱文件

```bash
python scripts/recipe_principle_annotator.py \
  --path data/dishes/vegetable_dish/某道菜.md
```

### 批量生成全部菜谱标注

```bash
python scripts/recipe_principle_annotator.py --all
```

默认输出：

```text
generated/principle_annotations/*.json
```

这些生成文件建议视为派生数据，不要反向修改 HowToCook 原菜谱。

## Skill 深化解释协议

规则标注完成后，Skill / LLM 应对关键步骤补全：

```text
原始步骤
↓
这一步的目标是什么
↓
为什么这个操作能实现目标
↓
真正控制结果的变量是什么
↓
做菜时应该观察什么，而不是只看秒表
↓
做过头/做不到位分别是什么表现
↓
下次应该调哪个变量
```

### 必须遵守

1. 原菜谱事实和推断分开。
2. 不确定就标注不确定。
3. 不捏造精确克数、温度、时间。
4. 时间只是参数，状态才是目标。
5. 食品安全底线与最佳口感区间分开讨论。
6. 规则标签只是候选，允许 Skill 根据上下文纠正。

## 后续扩展

优先级建议：

1. 增加技法标签：焯、滑炒、爆、煸、蒸、烧、焖、炸。
2. 增加食材属性：高水分蔬菜、瘦肉、带筋肉、鱼虾、蛋类。
3. 增加“家庭灶适配”字段。
4. 将人工确认后的解释缓存成结构化知识，而不是每次重新生成。
5. 建立失败现象反向索引，例如 `肉柴 -> 相关菜谱步骤 + 原理节点`。
6. 后续接入向量检索或知识图谱时，以 principle ID 作为稳定语义节点。
