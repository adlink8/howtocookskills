import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from recipe_principle_annotator import PrincipleAnnotator


class PrincipleAnnotatorTests(unittest.TestCase):
    def setUp(self):
        self.annotator = PrincipleAnnotator()

    def test_heat_protein_and_time_are_detected(self):
        result = self.annotator.annotate_step("锅烧热后，大火翻炒肉丝 30 秒", 1)
        ids = {item["id"] for item in result["principles"]}
        self.assertIn("heat-transfer", ids)
        self.assertIn("protein", ids)
        self.assertIn("30 秒", result["explicit_times"])
        self.assertTrue(any("参考参数" in n for n in result["parameter_notes"]))

    def test_seasoning_and_vegetable_water_are_detected(self):
        result = self.annotator.annotate_step("加入青菜和盐，快速翻炒", 2)
        ids = {item["id"] for item in result["principles"]}
        self.assertIn("vegetable-water", ids)
        self.assertIn("seasoning", ids)

    def test_unknown_step_does_not_invent_principle(self):
        result = self.annotator.annotate_step("装盘", 3)
        self.assertEqual([], result["principles"])
        self.assertTrue(any("不自动编造" in n for n in result["parameter_notes"]))

    def test_recipe_annotation_preserves_source_steps(self):
        recipe = {
            "name": "测试菜",
            "category": "vegetable_dish",
            "difficulty": 1,
            "ingredients": ["青菜", "盐"],
            "path": "data/dishes/test.md",
            "steps": ["青菜沥干", "热锅大火炒 20 秒", "加入盐调味"],
        }
        result = self.annotator.annotate_recipe(recipe)
        self.assertEqual("1.0", result["schema_version"])
        self.assertEqual("测试菜", result["recipe"]["name"])
        self.assertEqual(recipe["steps"], [s["source_step"] for s in result["steps"]])
        self.assertTrue(result["teaching_contract"]["time_is_reference_not_goal"])

    def test_prompt_contains_source_payload_and_contract(self):
        annotated = self.annotator.annotate_recipe({
            "name": "测试菜",
            "category": "unknown",
            "difficulty": 0,
            "ingredients": [],
            "steps": ["小火煮 2 分钟"],
        })
        prompt = self.annotator.build_deep_explanation_prompt(annotated)
        self.assertIn("原始步骤与“解释/推断”必须分开", prompt)
        self.assertIn("小火煮 2 分钟", prompt)
        self.assertIn("time_is_reference_not_goal", prompt)

    def test_json_serializable(self):
        result = self.annotator.annotate_step("切成薄片后煎至金黄", 1)
        dumped = json.dumps(result, ensure_ascii=False)
        self.assertIn("knife-size", dumped)
        self.assertIn("browning-aroma", dumped)


if __name__ == "__main__":
    unittest.main()
