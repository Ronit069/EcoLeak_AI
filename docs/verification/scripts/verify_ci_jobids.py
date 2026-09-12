"""Throwaway verification: are GitHub Actions job IDs in phase2-ci.yml valid?

GitHub job_id rule: must start with a letter or _ and contain only
alphanumeric characters, - or _.  An invalid job id makes the ENTIRE
workflow file invalid, so no job in it runs.
"""
import re
import subprocess

import yaml

PAT = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
PATH = ".github/workflows/phase2-ci.yml"


def check(raw: str):
    doc = yaml.safe_load(raw)
    jobs = list(doc.get("jobs", {}).keys())
    bad = [j for j in jobs if not PAT.match(j)]
    return jobs, bad


def main() -> None:
    shas = subprocess.run(
        ["git", "rev-list", "--all", "--", PATH], capture_output=True, text=True
    ).stdout.split()
    for sha in shas:
        raw = subprocess.run(
            ["git", "show", f"{sha}:{PATH}"], capture_output=True, text=True
        ).stdout
        jobs, bad = check(raw)
        print(f"{sha[:8]} jobs={jobs}")
        print(f"   INVALID: {bad if bad else 'none'}")

    print("\n--- working tree ---")
    with open(PATH, encoding="utf-8") as fh:
        jobs, bad = check(fh.read())
    print(f"jobs={jobs}")
    print(f"INVALID: {bad if bad else 'none'}")
    print("VERDICT:", "WORKFLOW INVALID -> no jobs run" if bad else "workflow job ids OK")


if __name__ == "__main__":
    main()
