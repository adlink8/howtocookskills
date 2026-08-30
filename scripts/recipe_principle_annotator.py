"""HowToCook recipe principle annotator.

Turn a procedural recipe into a teaching-oriented representation:
step -> goal -> principle tags -> control variables -> observable signals -> failure modes.

The annotator is intentionally deterministic and dependency-free. It does NOT pretend
that keyword rules can fully explain cooking science. Its job is to create a reliable
scaffold for the Skill/LLM to deepen, verify and teach from without changing the source
recipe.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

try:
    from recipe_parser import RecipeParser
except ImportError:  # package-style import
    from .recipe_parser import RecipeParser


RULES = [
    {
        "id": "heat-transfer",
        "title": "传热与锅温",
        "keywords": ["热锅", "锅热", "大火", "中火", "小火", "火", "加热", "烧热", "煮", "蒸", "焖", "炖"],
        "goal": "把热量以合适速度送入食材，并控制内外温差。",
        "mechanism": "锅具、热源、食材水分和下锅量共同决定实际温度变化；食材下锅会吸热并可能因蒸发显著降温。",
        "variables": ["热源功率", "锅材质与厚度", "锅温", "一次下锅量", "食材初温", "含水量"],
        "signals": ["油/水状态", "蒸汽量", "锅内声音", "表面颜色", "是否明显积水"],
        "failures": ["锅温过低导致出水或缺少焦香", "锅温过高导致外焦内生或糊锅"],
    },
    {
        "id": "protein",
        "title": "蛋白质与嫩度",
        "keywords": ["肉", "鸡", "牛", "猪", "羊", "鱼", "虾", "蛋", "上浆", "腌制", "腌"],
        "goal": "达到安全/目标熟度，同时避免不必要的失水和过度收缩。",
        "mechanism": "蛋白质受热会变性、凝固并逐渐收缩；持续高温通常会增加失水，肉类切法和预处理也会影响嫩度。",
        "variables": ["食材部位", "切片厚度", "纹理方向", "加热强度", "加热时间", "是否腌制/上浆"],
        "signals": ["颜色变化", "表面出汁", "弹性", "内部熟度", "锅底积水"],
        "failures": ["过度加热导致发柴", "块太厚导致外熟内生", "锅温下降导致肉出水"],
    },
    {
        "id": "starch",
        "title": "淀粉与粘度",
        "keywords": ["淀粉", "生粉", "勾芡", "水淀粉", "挂糊", "面粉", "米", "面", "土豆"],
        "goal": "利用淀粉吸水、糊化或成膜来控制粘度、挂汁和表面口感。",
        "mechanism": "淀粉颗粒在水和热作用下吸水膨胀并糊化；浓度、温度和剪切决定最终粘度。",
        "variables": ["淀粉浓度", "液体量", "温度", "加入速度", "搅动强度"],
        "signals": ["液体由稀变稠", "挂勺/挂汁程度", "是否出现结块", "表面是否形成均匀薄层"],
        "failures": ["一次加入过多造成过稠或结块", "温度不足导致糊化不充分"],
    },
    {
        "id": "vegetable-water",
        "title": "蔬菜与水分",
        "keywords": ["青菜", "白菜", "生菜", "菠菜", "包菜", "西兰花", "青椒", "番茄", "西红柿", "菌菇", "蘑菇", "蔬菜"],
        "goal": "在达到目标熟度的同时控制失水，保持脆嫩、颜色和香气。",
        "mechanism": "蔬菜组织含水量高；切割、盐和加热会改变细胞结构并促进水分迁移。",
        "variables": ["切割尺寸", "表面残水", "锅温", "下锅量", "盐加入时机", "加热时间"],
        "signals": ["颜色变化", "体积变化", "脆度", "锅底出水量", "蒸汽量"],
        "failures": ["锅温低或装锅过满导致水煮感", "盐过早可能促进部分蔬菜出水", "加热过久导致软烂"],
    },
    {
        "id": "browning-aroma",
        "title": "褐变与香气",
        "keywords": ["煎", "炸", "煸", "爆香", "炒香", "焦黄", "金黄", "上色", "香"],
        "goal": "形成期望的褐变和挥发性香气，而不是单纯把表面烧黑。",
        "mechanism": "表面足够干、温度足够高且接触条件合适时，更有利于美拉德反应等风味生成；大量水分会把表面温度限制在较低区间。",
        "variables": ["表面水分", "锅温", "油量", "接触面积", "翻动频率", "食材密度"],
        "signals": ["颜色从浅到金黄/褐色", "香气增强", "滋滋声稳定", "表面不再大量出水"],
        "failures": ["频繁翻动或表面太湿导致不上色", "温度过高导致焦苦"],
    },
    {
        "id": "seasoning",
        "title": "调味与加入时机",
        "keywords": ["盐", "糖", "酱油", "生抽", "老抽", "醋", "料酒", "味精", "鸡精", "蚝油", "调味"],
        "goal": "建立咸、甜、酸、鲜、香的平衡，并利用加入时机控制渗透、挥发和上色。",
        "mechanism": "调味不仅由总量决定，也由浓度、接触位置、受热时间和食材含水状态决定。",
        "variables": ["调味料浓度", "加入时机", "锅内水量", "受热时间", "食材表面积"],
        "signals": ["尝味后的平衡", "颜色", "汁液浓度", "酸香/酱香是否仍清晰"],
        "failures": ["过早长时间加热使部分香气损失", "水量变化使最终咸度偏离", "只按固定克数忽略食材量"],
    },
    {
        "id": "knife-size",
        "title": "刀工与尺寸",
        "keywords": ["切丝", "切片", "切块", "切丁", "切段", "切成", "改刀"],
        "goal": "通过统一尺寸控制成熟速度、口感和调味附着。",
        "mechanism": "尺寸越小，单位质量表面积越大，通常升温、失水和调味交换更快；尺寸不一致会导致成熟度不一致。",
        "variables": ["厚度", "长度", "形状一致性", "纹理方向", "表面积"],
        "signals": ["尺寸是否均匀", "同批食材成熟是否同步", "咀嚼阻力"],
        "failures": ["大小不一导致部分过熟、部分未熟", "逆/顺纹选择不当影响肉类咀嚼感"],
    },
    {
        "id": "water-control",
        "title": "水分控制",
        "keywords": ["沥干", "擦干", "控水", "加水", "清水", "收汁", "汤汁", "水分"],
        "goal": "控制锅内自由水，决定温度上限、浓度、口感和是否容易褐变。",
        "mechanism": "水的蒸发会带走大量热；自由水越多，越难让食材表面快速进入高温褐变状态。",
        "variables": ["初始水量", "蒸发表面积", "火力", "锅盖", "食材出水", "加热时间"],
        "signals": ["蒸汽强弱", "汤汁体积", "气泡形态", "锅内声音由水煮声向煎炒声变化"],
        "failures": ["水过多导致味道稀、缺少焦香", "水过少导致糊锅或食材未熟"],
    },
]

TIME_RE = re.compile(r"(?<!\d)(\d+(?:\.\d+)?(?:\s*[-~～至]\s*\d+(?:\.\d+)?)?)\s*(秒|分钟|分|小时|h|min|s)\b", re.I)
TEMP_RE = re.compile(r"(?<!\d)(\d{2,3})\s*(?:℃|°C|度)", re.I)


class PrincipleAnnotator:
    """Create explainable teaching scaffolds from parsed recipes."""

    def annotate_step(self, step: str, index: int = 1) -> Dict:
        matched = []
        for rule in RULES:
            hits = [kw for kw in rule["keywords"] if kw in step]
            if hits:
                matched.append({
                    "id": rule["id"],
                    "title": rule["title"],
                    "matched_keywords": hits,
                    "goal": rule["goal"],
                    "mechanism": rule["mechanism"],
                    "variables": rule["variables"],
                    "signals": rule["signals"],
                    "failures": rule["failures"],
                })

        explicit_times = [m.group(0) for m in TIME_RE.finditer(step)]
        explicit_temps = [m.group(0) for m in TEMP_RE.finditer(step)]
        parameter_notes = []
        if explicit_times:
            parameter_notes.append(
                "步骤包含明确时间；应把它视为特定食材尺寸、锅温、火力和分量下的参考参数，并补充状态判断。"
            )
        if explicit_temps:
            parameter_notes.append(
                "步骤包含明确温度；需区分设备设定温度、锅面温度和食材内部温度，三者通常不相等。"
            )

        if not matched:
            parameter_notes.append(
                "规则库未命中明确原理标签；保留原步骤，交由烹饪导师根据上下文补充解释，不自动编造机制。"
            )

        return {
            "step_index": index,
            "source_step": step,
            "principles": matched,
            "explicit_times": explicit_times,
            "explicit_temperatures": explicit_temps,
            "parameter_notes": parameter_notes,
        }

    def annotate_recipe(self, recipe: Dict) -> Dict:
        return {
            "schema_version": "1.0",
            "recipe": {
                "name": recipe.get("name", "未知菜谱"),
                "category": recipe.get("category", "unknown"),
                "difficulty": recipe.get("difficulty", 0),
                "ingredients": recipe.get("ingredients", []),
                "source_path": recipe.get("path"),
            },
            "teaching_contract": {
                "preserve_source_steps": True,
                "time_is_reference_not_goal": True,
                "prefer_observable_signals": True,
                "mark_inference": True,
                "do_not_invent_exact_parameters": True,
            },
            "steps": [
                self.annotate_step(step, i)
                for i, step in enumerate(recipe.get("steps", []), 1)
            ],
        }

    def build_deep_explanation_prompt(self, annotated: Dict) -> str:
        payload = json.dumps(annotated, ensure_ascii=False, indent=2)
        return f"""你是烹饪原理导师。下面是从 HowToCook 原始菜谱生成的规则标注骨架。

任务：在不改变原始步骤事实的前提下，为每个关键步骤补全可迁移的解释。

严格要求：
1. 原始步骤与“解释/推断”必须分开；不得把推断伪装成原菜谱内容。
2. 对每个关键步骤按：目标 -> 原理 -> 控制变量 -> 观察信号 -> 做过头/做不到位 -> 修正。
3. 菜谱中的秒数/分钟数不是目标，解释它依赖的食材尺寸、锅温、火力、分量和初始温度。
4. 优先给颜色、声音、气味、质地、出水量、气泡、粘度等状态信号。
5. 不知道精确温度、克数或时间时直接说明不确定，不得伪造。
6. 规则标注只是候选知识标签；如标签与上下文不符，应纠正并说明。
7. 涉及食品安全时，将安全底线与“最佳口感区间”分开。

规则标注骨架：
```json
{payload}
```
"""

    def render_markdown(self, annotated: Dict) -> str:
        name = annotated["recipe"]["name"]
        lines = [f"# {name}：原理标注", ""]
        for step in annotated["steps"]:
            lines += [f"## 步骤 {step['step_index']}", "", f"> {step['source_step']}", ""]
            if step["explicit_times"]:
                lines.append(f"- **时间参数**：{', '.join(step['explicit_times'])}（参考值，不是目标状态）")
            if step["explicit_temperatures"]:
                lines.append(f"- **温度参数**：{', '.join(step['explicit_temperatures'])}")
            if step["principles"]:
                for p in step["principles"]:
                    lines.append(f"- **{p['title']}**")
                    lines.append(f"  - 目标：{p['goal']}")
                    lines.append(f"  - 原理：{p['mechanism']}")
                    lines.append(f"  - 关键变量：{' / '.join(p['variables'])}")
                    lines.append(f"  - 观察信号：{' / '.join(p['signals'])}")
                    lines.append(f"  - 常见失败：{' / '.join(p['failures'])}")
            for note in step["parameter_notes"]:
                lines.append(f"- **注意**：{note}")
            lines.append("")
        return "\n".join(lines)


def find_recipe_file(query: str, data_root: Path) -> Optional[Path]:
    """Find a recipe by filename or parsed recipe title, exact matches first."""
    dishes = data_root / "dishes"
    if not dishes.exists():
        return None

    files = list(dishes.rglob("*.md"))
    normalized = query.strip().replace("的做法", "")

    for path in files:
        if path.stem == normalized:
            return path

    parser = RecipeParser()
    partial = None
    for path in files:
        try:
            recipe = parser.parse(str(path))
        except Exception:
            continue
        name = recipe.get("name", "")
        if name == normalized:
            return path
        if partial is None and normalized in name:
            partial = path
    return partial


def load_recipe(recipe_name: Optional[str], recipe_path: Optional[str], data_root: Path) -> Dict:
    parser = RecipeParser()
    if recipe_path:
        path = Path(recipe_path)
    elif recipe_name:
        path = find_recipe_file(recipe_name, data_root)
        if path is None:
            raise FileNotFoundError(f"未找到菜谱: {recipe_name}")
    else:
        raise ValueError("必须提供 --recipe 或 --path")
    if not path.exists():
        raise FileNotFoundError(path)
    return parser.parse(str(path))


def iter_recipes(data_root: Path) -> Iterable[Dict]:
    parser = RecipeParser()
    for path in (data_root / "dishes").rglob("*.md"):
        if "template" in path.parts:
            continue
        try:
            yield parser.parse(str(path))
        except Exception as exc:
            print(f"[skip] {path}: {exc}", file=sys.stderr)


def write_batch(annotator: PrincipleAnnotator, data_root: Path, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for recipe in iter_recipes(data_root):
        annotated = annotator.annotate_recipe(recipe)
        safe_name = re.sub(r"[\\/:*?\"<>|]", "_", recipe["name"])
        target = out_dir / f"{safe_name}.json"
        target.write_text(json.dumps(annotated, ensure_ascii=False, indent=2), encoding="utf-8")
        count += 1
    return count


def main() -> int:
    base = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="HowToCook 菜谱原理自动标注器")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--recipe", help="按菜名查找，例如：西红柿炒鸡蛋")
    group.add_argument("--path", help="直接指定菜谱 Markdown 文件")
    group.add_argument("--all", action="store_true", help="批量标注全部菜谱")
    parser.add_argument("--data-root", default=str(base / "data"), help="包含 dishes/ 的数据目录")
    parser.add_argument("--format", choices=["json", "markdown", "prompt"], default="markdown")
    parser.add_argument("--output", help="单菜输出文件；省略则打印到 stdout")
    parser.add_argument("--out-dir", default=str(base / "generated" / "principle_annotations"), help="--all 的输出目录")
    args = parser.parse_args()

    annotator = PrincipleAnnotator()
    data_root = Path(args.data_root)

    if args.all:
        count = write_batch(annotator, data_root, Path(args.out_dir))
        print(f"已生成 {count} 份原理标注 -> {args.out_dir}")
        return 0

    recipe = load_recipe(args.recipe, args.path, data_root)
    annotated = annotator.annotate_recipe(recipe)
    if args.format == "json":
        output = json.dumps(annotated, ensure_ascii=False, indent=2)
    elif args.format == "prompt":
        output = annotator.build_deep_explanation_prompt(annotated)
    else:
        output = annotator.render_markdown(annotated)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
