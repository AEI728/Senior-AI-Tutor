"""Validate packaged application skills and their actual model/output contract.

--write exports the Plan schema; --sync-design updates the user-owned design
packages. Normal checks never depend on that external design directory.
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
from app.schemas import Plan
from app.skill_runtime import SKILLS, load_skill, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--sync-design", action="store_true")
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
    if args.sync_design:
        design = ROOT.parent / "9.1/docs/02-方案设计"
        if not (design / "小伴Agent-共享SystemPrompt.md").is_file():
            raise SystemExit("Named original design directory is missing")
        for name in SKILLS:
            destination = design / "小伴Agent/skills" / name
            # Copy into a known explicit directory; no move or recursive deletion.
            shutil.copytree(base / name, destination, dirs_exist_ok=True)
        shutil.copy2(ROOT / "apps/api/app/prompts/shared-system.md", design / "小伴Agent-共享SystemPrompt.md")
    print(json.dumps({"status": "PASS", **manifest()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
