"""
Run every guard suite. Exit non-zero if any fails.

    ./venv/Scripts/python.exe tests/run_all.py

Each suite corresponds to a defect recorded in docs/ASSISTANT_DEFECTS.md.
"""
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

suites = sorted(glob.glob(os.path.join(HERE, "verify_*.py")))

failed = []

for path in suites:
    name = os.path.basename(path)
    result = subprocess.run(
        [sys.executable, path],
        capture_output=True,
        text=True,
    )
    ok = result.returncode == 0
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok:
        failed.append(name)
        print(result.stdout[-2000:])
        print(result.stderr[-2000:])

print()
print(f"{len(suites) - len(failed)}/{len(suites)} suites passed")

sys.exit(1 if failed else 0)
