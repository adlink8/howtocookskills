"""Rebuild references/recipe_index.json with repository-relative paths."""
from __future__ import annotations

import json
from pathlib import Path

from recipe_search import RecipeSearcher

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data"
INDEX_PATH = ROOT / "references" / "recipe_index.json"


def portable_path(value: str | Path) -> str:
    path = Path(value)
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        return path.as_posix()


def build_portable_index() -> dict:
    searcher = RecipeSearcher(cookbook_path=str(DATA_ROOT))
    index = searcher.build_index(force_rebuild=True)

    for info in index.get("all_recipes", []):
        if info.get("path"):
            info["path"] = portable_path(info["path"])

    for info in index.get("by_name", {}).values():
        if info.get("path"):
            info["path"] = portable_path(info["path"])

    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return index


def main() -> int:
    index = build_portable_index()
    print(
        json.dumps(
            {
                "recipes": len(index.get("all_recipes", [])),
                "index": portable_path(INDEX_PATH),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
