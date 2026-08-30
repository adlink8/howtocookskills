import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "howtocook_cli.py"


class PortableSkillTests(unittest.TestCase):
    def run_cli(self, *args):
        proc = subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, proc.returncode, msg=proc.stderr or proc.stdout)
        return json.loads(proc.stdout)

    def test_manifest_is_agent_neutral(self):
        manifest = json.loads((ROOT / "skill.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["portability"]["agent_specific_core_logic"])
        self.assertTrue(manifest["portability"]["machine_readable_interface"])
        self.assertIn("codex", manifest["portability"]["adapters"])
        self.assertIn("pi-agent", manifest["portability"]["adapters"])

    def test_search_returns_json_envelope_and_portable_paths(self):
        payload = self.run_cli("search", "--name", "西红柿", "--limit", "3")
        self.assertTrue(payload["ok"])
        self.assertEqual("search", payload["action"])
        self.assertTrue(payload["data"])
        for item in payload["data"]:
            path = item.get("path")
            if path:
                self.assertFalse(path.startswith("/Users/"))
                self.assertFalse(path.startswith("/home/runner/"))

    def test_recipe_resolves_legacy_cached_absolute_path(self):
        payload = self.run_cli("recipe", "宫保鸡丁")
        self.assertTrue(payload["ok"])
        recipe = payload["data"]
        self.assertEqual("宫保鸡丁", recipe["name"])
        self.assertGreater(len(recipe["steps"]), 5)
        self.assertTrue(recipe["path"].startswith("data/"))

    def test_annotate_is_machine_readable(self):
        payload = self.run_cli("annotate", "宫保鸡丁")
        self.assertTrue(payload["ok"])
        steps = payload["data"]["steps"]
        self.assertTrue(any(step["principles"] for step in steps))
        self.assertFalse(payload["data"]["recipe"]["source_path"].startswith("/Users/"))


if __name__ == "__main__":
    unittest.main()
