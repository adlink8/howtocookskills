"""Portable, agent-neutral CLI for HowToCook.

Any agent runtime that can execute a local command can use this interface. The CLI
returns stable JSON envelopes by default so wrappers do not need to scrape prose.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

from recipe_parser import RecipeParser
from recipe_principle_annotator import PrincipleAnnotator
from recipe_search import RecipeSearcher

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data"
GENERATED = ROOT / "generated"
MANIFEST_PATH = ROOT / "skill.json"


def emit(data: Any, *, action: str, pretty: bool = False) -> None:
    payload = {"ok": True, "action": action, "data": data}
    print(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None))


def fail(code: str, message: str, *, action: str, pretty: bool = False) -> int:
    payload = {
        "ok": False,
        "action": action,
        "error": {"code": code, "message": message},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None))
    return 2


def portable_path(value: str | Path | None) -> str | None:
    if value is None:
        return None
    path = Path(value)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        parts = path.parts
        if "data" in parts:
            idx = parts.index("data")
            return Path(*parts[idx:]).as_posix()
        return path.as_posix()


def resolve_local_path(value: str | Path) -> Path:
    """Resolve legacy absolute paths embedded in the upstream cached index."""
    path = Path(value)
    if path.exists():
        return path

    parts = path.parts
    if "data" in parts:
        idx = parts.index("data")
        candidate = ROOT.joinpath(*parts[idx:])
        if candidate.exists():
            return candidate

    candidate = ROOT / path
    if candidate.exists():
        return candidate
    return path


def get_searcher() -> RecipeSearcher:
    # Use the repository's own data directory. The upstream cached index may contain
    # machine-specific absolute paths; resolve_local_path handles them when opening.
    return RecipeSearcher(cookbook_path=str(DATA_ROOT))


def sanitize_info(info: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(info)
    if "path" in result:
        result["path"] = portable_path(result["path"])
    return result


def parse_recipe_from_info(info: Dict[str, Any]) -> Dict[str, Any] | None:
    raw_path = info.get("path")
    if not raw_path:
        return None
    path = resolve_local_path(raw_path)
    if not path.exists():
        return None
    recipe = RecipeParser().parse(str(path))
    recipe["path"] = portable_path(path)
    return recipe


def find_recipe(name: str) -> Dict[str, Any] | None:
    searcher = get_searcher()
    matches = searcher.search_by_name(name)
    if not matches:
        return None
    exact = next((m for m in matches if m.get("name") == name), matches[0])
    return parse_recipe_from_info(exact)


def cmd_search(args: argparse.Namespace) -> int:
    searcher = get_searcher()

    if args.name:
        results = searcher.search_by_name(args.name)
    elif args.ingredient:
        results = searcher.filter_by_ingredient(args.ingredient)
    else:
        categories = [args.category] if args.category else None
        results = searcher.multi_filter(
            categories=categories,
            max_difficulty=args.max_difficulty,
            max_time=args.max_time,
        )

    if args.category and (args.name or args.ingredient):
        results = [r for r in results if r.get("category") == args.category]
    if args.max_difficulty is not None:
        results = [r for r in results if r.get("difficulty", 0) <= args.max_difficulty]
    if args.max_time is not None:
        estimates = RecipeParser.TIME_ESTIMATES
        results = [
            r for r in results if estimates.get(r.get("difficulty", 0), 30) <= args.max_time
        ]

    results = sorted(results, key=lambda x: (x.get("difficulty", 0), x.get("name", "")))
    emit([sanitize_info(r) for r in results[: args.limit]], action="search", pretty=args.pretty)
    return 0


def cmd_recipe(args: argparse.Namespace) -> int:
    recipe = find_recipe(args.name)
    if not recipe:
        return fail("recipe_not_found", f"未找到菜谱：{args.name}", action="recipe", pretty=args.pretty)

    if args.format == "markdown":
        text = RecipeParser().format_detailed(recipe)
        emit({"name": recipe["name"], "markdown": text}, action="recipe", pretty=args.pretty)
    else:
        emit(recipe, action="recipe", pretty=args.pretty)
    return 0


def _sanitize_annotation(annotation: Dict[str, Any]) -> Dict[str, Any]:
    annotation = dict(annotation)
    recipe = dict(annotation.get("recipe", {}))
    recipe["source_path"] = portable_path(recipe.get("source_path"))
    annotation["recipe"] = recipe
    return annotation


def cmd_annotate(args: argparse.Namespace) -> int:
    recipe = find_recipe(args.name)
    if not recipe:
        return fail("recipe_not_found", f"未找到菜谱：{args.name}", action="annotate", pretty=args.pretty)

    annotator = PrincipleAnnotator()
    annotated = _sanitize_annotation(annotator.annotate_recipe(recipe))
    if args.format == "prompt":
        emit(
            {"name": recipe["name"], "prompt": annotator.build_deep_explanation_prompt(annotated)},
            action="annotate",
            pretty=args.pretty,
        )
    else:
        emit(annotated, action="annotate", pretty=args.pretty)
    return 0


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def cmd_diagnose(args: argparse.Namespace) -> int:
    path = GENERATED / "failure_index.json"
    if not path.exists():
        return fail(
            "generated_corpus_missing",
            "缺少 generated/failure_index.json，请先运行 python scripts/build_teaching_corpus.py",
            action="diagnose",
            pretty=args.pretty,
        )

    index = load_json(path).get("failures", {})
    query = args.symptom.strip()
    ranked = []
    for failure, entry in index.items():
        if query in failure or failure in query:
            score = 2
        elif any(token and token in failure for token in query.replace("，", " ").split()):
            score = 1
        else:
            continue
        ranked.append((score, failure, entry))

    ranked.sort(key=lambda x: (-x[0], x[1]))
    data = []
    for _, failure, entry in ranked[: args.limit]:
        item = dict(entry)
        item["failure"] = failure
        item["matches"] = item.get("matches", [])[: args.examples]
        data.append(item)

    emit(data, action="diagnose", pretty=args.pretty)
    return 0


def cmd_principles(args: argparse.Namespace) -> int:
    path = GENERATED / "principle_catalog.json"
    if not path.exists():
        return fail(
            "generated_corpus_missing",
            "缺少 generated/principle_catalog.json，请先运行 python scripts/build_teaching_corpus.py",
            action="principles",
            pretty=args.pretty,
        )
    catalog = load_json(path)
    if args.id:
        principle = catalog.get("principles", {}).get(args.id)
        if principle is None:
            return fail("principle_not_found", f"未知原理 ID：{args.id}", action="principles", pretty=args.pretty)
        emit({args.id: principle}, action="principles", pretty=args.pretty)
    else:
        emit(catalog, action="principles", pretty=args.pretty)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    data: Dict[str, Any] = {}
    generated_manifest = GENERATED / "manifest.json"
    if generated_manifest.exists():
        data["corpus"] = load_json(generated_manifest)
    if MANIFEST_PATH.exists():
        data["skill"] = load_json(MANIFEST_PATH)
    emit(data, action="status", pretty=args.pretty)
    return 0


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Portable HowToCook skill CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="search/filter recipes")
    search.add_argument("--name")
    search.add_argument("--ingredient")
    search.add_argument("--category")
    search.add_argument("--max-difficulty", type=int)
    search.add_argument("--max-time", type=int)
    search.add_argument("--limit", type=int, default=10)
    add_common(search)
    search.set_defaults(func=cmd_search)

    recipe = sub.add_parser("recipe", help="return a full source recipe")
    recipe.add_argument("name")
    recipe.add_argument("--format", choices=["json", "markdown"], default="json")
    add_common(recipe)
    recipe.set_defaults(func=cmd_recipe)

    annotate = sub.add_parser("annotate", help="return principle annotations for a recipe")
    annotate.add_argument("name")
    annotate.add_argument("--format", choices=["json", "prompt"], default="json")
    add_common(annotate)
    annotate.set_defaults(func=cmd_annotate)

    diagnose = sub.add_parser("diagnose", help="reverse lookup a cooking failure symptom")
    diagnose.add_argument("symptom")
    diagnose.add_argument("--limit", type=int, default=5)
    diagnose.add_argument("--examples", type=int, default=5)
    add_common(diagnose)
    diagnose.set_defaults(func=cmd_diagnose)

    principles = sub.add_parser("principles", help="show principle catalog")
    principles.add_argument("--id")
    add_common(principles)
    principles.set_defaults(func=cmd_principles)

    status = sub.add_parser("status", help="show skill and corpus metadata")
    add_common(status)
    status.set_defaults(func=cmd_status)

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except BrokenPipeError:
        return 0
    except Exception as exc:
        return fail("internal_error", str(exc), action=args.command, pretty=getattr(args, "pretty", False))


if __name__ == "__main__":
    raise SystemExit(main())
