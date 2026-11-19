"""Validate packaged application skills; --write exports the current Plan schema."""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
from app.schemas import Plan
from app.skill_runtime import SKILLS, load_skill, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    base = ROOT / "apps/api/app/skills"
    contract = base / "intent-recognition/references/plan.schema.json"
    expected = json.dumps(Plan.model_json_schema(), ensure_ascii=False, indent=2) + "\n"
    if args.write:
        contract.write_text(expected, "utf-8")
    if contract.read_text("utf-8") != expected:
        raise SystemExit("Plan schema is stale; run check_agent_skills.py --write")
    allowed = set(Plan.model_json_schema()["properties"]["intent"]["enum"])
    if set(load_skill("operation-execution")["policy"]["intent_tools"]) != allowed:
        raise SystemExit("Execution whitelist and Plan enum disagree")
    for name in SKILLS:
        load_skill(name)
        path = base / name / "SKILL.md"
        for link in re.findall(r"\]\(([^)]+)\)", path.read_text("utf-8")):
            if not (path.parent / link).is_file():
                raise SystemExit(f"Broken skill reference: {name}/{link}")
    print(json.dumps({"status": "PASS", **manifest()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
