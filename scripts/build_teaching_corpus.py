"""Batch-build compact teaching annotations and a reverse failure index.

This module turns every HowToCook markdown recipe into a deterministic, compact
teaching corpus derived from ``recipe_principle_annotator.py``.

Generated files:
- generated/recipe_principles.jsonl   compact recipe/step annotations
- generated/principle_catalog.json    de-duplicated principle definitions
- generated/failure_index.json        failure symptom -> relevant recipe steps
- generated/manifest.json             counts and source fingerprint

The generated layer never rewrites source recipes and does not invent exact
parameters. It only records rule candidates and source facts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List

from recipe_parser import RecipeParser
from recipe_principle_annotator import PrincipleAnnotator, RULES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECIPE_ROOT = ROOT / "data" / "dishes"
DEFAULT_OUTPUT_DIR = ROOT / "generated"


def portable_path(value: str | Path | None) -> str | None:
    """Prefer repository-relative POSIX paths so generated data is relocatable."""
    if value is None:
        return None
    path = Path(value)
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        return path.as_posix()


def iter_recipe_files(recipe_root: Path) -> Iterable[Path]:
    """Yield source recipe markdown files in deterministic order."""
    if not recipe_root.exists():
        raise FileNotFoundError(f"Recipe root not found: {recipe_root}")

    for path in sorted(recipe_root.rglob("*.md")):
        if "template" in path.parts:
            continue
        yield path


def _compact_step(step: Dict) -> Dict:
    """Remove repeated rule prose while preserving source facts and rule IDs."""
    return {
        "step_index": step["step_index"],
        "source_step": step["source_step"],
        "principle_ids": [p["id"] for p in step.get("principles", [])],
        "matched_keywords": {
            p["id"]: p.get("matched_keywords", [])
            for p in step.get("principles", [])
        },
        "explicit_times": step.get("explicit_times", []),
        "explicit_temperatures": step.get("explicit_temperatures", []),
        "parameter_notes": step.get("parameter_notes", []),
    }


def compact_annotation(annotation: Dict) -> Dict:
    """Convert verbose per-step annotation to a compact corpus record."""
    recipe = annotation["recipe"]
    return {
        "schema_version": "1.1-compact",
        "recipe": {
            "name": recipe.get("name", "未知菜谱"),
            "category": recipe.get("category", "unknown"),
            "difficulty": recipe.get("difficulty", 0),
            "ingredients": recipe.get("ingredients", []),
            "source_path": portable_path(recipe.get("source_path")),
        },
        "teaching_contract": annotation.get("teaching_contract", {}),
        "steps": [_compact_step(step) for step in annotation.get("steps", [])],
    }


def principle_catalog() -> Dict:
    """Build a de-duplicated rule catalog keyed by stable principle ID."""
    return {
        "schema_version": "1.0",
        "principles": {
            rule["id"]: {
                "title": rule["title"],
                "goal": rule["goal"],
                "mechanism": rule["mechanism"],
                "variables": rule["variables"],
                "signals": rule["signals"],
                "failures": rule["failures"],
            }
            for rule in RULES
        },
    }


def _source_fingerprint(recipe_files: List[Path]) -> str:
    """Hash source recipe contents plus the rule catalog for reproducibility."""
    digest = hashlib.sha256()
    for path in recipe_files:
        digest.update(portable_path(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    digest.update(
        json.dumps(principle_catalog(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    )
    return digest.hexdigest()


def build_failure_index(records: List[Dict], catalog: Dict) -> Dict:
    """Create reverse index: candidate failure symptom -> recipe steps.

    A failure is indexed only when its principle matched the source step. This makes
    the index useful for questions such as "为什么肉柴" or "为什么青菜出水" while
    keeping source facts separate from diagnostic candidates.
    """
    failures: Dict[str, Dict] = {}
    seen: Dict[str, set] = defaultdict(set)

    principle_defs = catalog["principles"]
    for record in records:
        recipe = record["recipe"]
        for step in record["steps"]:
            for principle_id in step["principle_ids"]:
                rule = principle_defs[principle_id]
                for failure in rule["failures"]:
                    entry = failures.setdefault(
                        failure,
                        {"principle_ids": [], "matches": []},
                    )
                    if principle_id not in entry["principle_ids"]:
                        entry["principle_ids"].append(principle_id)

                    dedupe_key = (
                        recipe["name"],
                        recipe.get("source_path"),
                        step["step_index"],
                        principle_id,
                    )
                    if dedupe_key in seen[failure]:
                        continue
                    seen[failure].add(dedupe_key)
                    entry["matches"].append(
                        {
                            "recipe": recipe["name"],
                            "category": recipe["category"],
                            "source_path": recipe.get("source_path"),
                            "step_index": step["step_index"],
                            "source_step": step["source_step"],
                            "principle_id": principle_id,
                        }
                    )

    for failure, entry in failures.items():
        entry["principle_ids"].sort()
        entry["matches"].sort(
            key=lambda x: (x["recipe"], x["step_index"], x["principle_id"])
        )

    return {
        "schema_version": "1.0",
        "description": "候选失败现象到相关菜谱步骤的反向索引；匹配表示相关，不代表该菜谱实际失败。",
        "failures": dict(sorted(failures.items())),
    }


def _write_json(path: Path, payload: Dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_corpus(
    recipe_root: Path = DEFAULT_RECIPE_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict:
    """Parse, annotate, index and write the complete teaching corpus."""
    parser = RecipeParser()
    annotator = PrincipleAnnotator()
    files = list(iter_recipe_files(recipe_root))

    records: List[Dict] = []
    skipped: List[Dict] = []
    stats = {
        "recipe_files": len(files),
        "recipes_emitted": 0,
        "recipes_skipped": 0,
        "steps": 0,
        "tagged_steps": 0,
        "untagged_steps": 0,
        "explicit_time_steps": 0,
        "explicit_temperature_steps": 0,
    }
    principle_hits: Dict[str, int] = defaultdict(int)

    for file_path in files:
        try:
            recipe = parser.parse(str(file_path))
        except Exception as exc:
            skipped.append(
                {"path": portable_path(file_path), "reason": f"parse_error: {exc}"}
            )
            continue

        if not recipe.get("steps"):
            skipped.append({"path": portable_path(file_path), "reason": "no_steps"})
            continue

        record = compact_annotation(annotator.annotate_recipe(recipe))
        records.append(record)

        for step in record["steps"]:
            stats["steps"] += 1
            if step["principle_ids"]:
                stats["tagged_steps"] += 1
            else:
                stats["untagged_steps"] += 1
            if step["explicit_times"]:
                stats["explicit_time_steps"] += 1
            if step["explicit_temperatures"]:
                stats["explicit_temperature_steps"] += 1
            for principle_id in step["principle_ids"]:
                principle_hits[principle_id] += 1

    records.sort(key=lambda r: (r["recipe"]["category"], r["recipe"]["name"]))
    stats["recipes_emitted"] = len(records)
    stats["recipes_skipped"] = len(skipped)

    catalog = principle_catalog()
    failure_index = build_failure_index(records, catalog)

    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "recipe_principles.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    _write_json(output_dir / "principle_catalog.json", catalog)
    _write_json(output_dir / "failure_index.json", failure_index)

    manifest = {
        "schema_version": "1.0",
        "source_fingerprint": _source_fingerprint(files),
        "stats": stats,
        "principle_step_hits": dict(sorted(principle_hits.items())),
        "failure_types": len(failure_index["failures"]),
        "skipped": skipped,
        "files": {
            "recipe_principles": "generated/recipe_principles.jsonl",
            "principle_catalog": "generated/principle_catalog.json",
            "failure_index": "generated/failure_index.json",
        },
    }
    _write_json(output_dir / "manifest.json", manifest)
    return manifest


def main() -> int:
    argp = argparse.ArgumentParser(description="Build HowToCook teaching corpus")
    argp.add_argument("--recipe-root", type=Path, default=DEFAULT_RECIPE_ROOT)
    argp.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = argp.parse_args()

    manifest = build_corpus(args.recipe_root, args.output_dir)
    print(json.dumps(manifest["stats"], ensure_ascii=False, indent=2))
    print(f"failure_types: {manifest['failure_types']}")
    print(f"source_fingerprint: {manifest['source_fingerprint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
