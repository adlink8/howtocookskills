import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_teaching_corpus import build_corpus
from recipe_parser import RecipeParser


SAMPLE_RECIPE = """# 测试青椒肉丝的做法

预估烹饪难度：★★

## 必备原料和工具

- 青椒
- 猪肉
- 盐

## 操作

- 青椒切丝，肉切丝
- 锅烧热后，大火翻炒肉丝 30 秒
- 加入青椒和盐，继续翻炒

## 附加内容

- 不要一次下锅太多
"""

NESTED_RECIPE = """# 测试宫保鸡丁的做法

预估烹饪难度：★★★★

## 必备原料和工具

- 鸡肉
- 盐

### 可选原料

- 花生

## 操作

### 简易版本

- 鸡肉切丁
- 大火翻炒鸡丁 30 秒

### 复杂版本

- 加入花生继续翻炒

## 附加内容

- 根据锅温调整时间
"""


class BuildTeachingCorpusTests(unittest.TestCase):
    def test_parser_keeps_steps_below_nested_headings(self):
        with tempfile.TemporaryDirectory() as temp:
            recipe_path = Path(temp) / "nested.md"
            recipe_path.write_text(NESTED_RECIPE, encoding="utf-8")
            recipe = RecipeParser().parse(str(recipe_path))
            self.assertEqual(3, len(recipe["steps"]))
            self.assertIn("大火翻炒鸡丁 30 秒", recipe["steps"])
            self.assertIn("花生", recipe["ingredients"])

    def test_builds_compact_corpus_and_reverse_failure_index(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            recipe_root = temp_path / "dishes"
            category_dir = recipe_root / "meat_dish"
            category_dir.mkdir(parents=True)
            (category_dir / "sample.md").write_text(SAMPLE_RECIPE, encoding="utf-8")

            output_dir = temp_path / "generated"
            manifest = build_corpus(recipe_root, output_dir)

            self.assertEqual(1, manifest["stats"]["recipes_emitted"])
            self.assertEqual(3, manifest["stats"]["steps"])
            self.assertGreaterEqual(manifest["stats"]["tagged_steps"], 2)

            corpus_lines = (output_dir / "recipe_principles.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(1, len(corpus_lines))
            record = json.loads(corpus_lines[0])
            self.assertEqual("测试青椒肉丝", record["recipe"]["name"])
            self.assertIn("protein", record["steps"][1]["principle_ids"])
            self.assertIn("30 秒", record["steps"][1]["explicit_times"])

            failure_index = json.loads(
                (output_dir / "failure_index.json").read_text(encoding="utf-8")
            )
            failure = "过度加热导致发柴"
            self.assertIn(failure, failure_index["failures"])
            matches = failure_index["failures"][failure]["matches"]
            self.assertTrue(any(m["recipe"] == "测试青椒肉丝" for m in matches))

            catalog = json.loads(
                (output_dir / "principle_catalog.json").read_text(encoding="utf-8")
            )
            self.assertIn("heat-transfer", catalog["principles"])
            self.assertIn("protein", catalog["principles"])

            manifest_json = json.loads(
                (output_dir / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["source_fingerprint"], manifest_json["source_fingerprint"])


if __name__ == "__main__":
    unittest.main()
