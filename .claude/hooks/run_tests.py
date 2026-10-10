"""PostToolUse hook: run the test suite after an edit to src/ or tests/.

Claude Code sends the tool call as JSON on stdin. When the tests fail this exits
with code 2 and the pytest output on stderr, which Claude Code feeds back to
Claude. In every other case it exits 0 and stays silent.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WATCHED_DIRS = ("src", "tests")
VENV_PYTHONS = (ROOT / ".venv" / "Scripts" / "python.exe", ROOT / ".venv" / "bin" / "python")
MAX_OUTPUT_LINES = 60


def edited_path(payload):
    tool_input = payload.get("tool_input")
    tool_response = payload.get("tool_response")
    for source, key in ((tool_input, "file_path"), (tool_response, "filePath")):
        if isinstance(source, dict) and source.get(key):
            return Path(source[key])
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    path = edited_path(payload)
    if path is None:
        return 0
    try:
        relative = path.resolve().relative_to(ROOT)
    except ValueError:
        return 0
    if relative.parts[0] not in WATCHED_DIRS:
        return 0

    python = next((candidate for candidate in VENV_PYTHONS if candidate.exists()), None)
    if python is None:
        return 0

    result = subprocess.run(
        [str(python), "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode == 0:
        return 0

    lines = (result.stdout + result.stderr).strip().splitlines()[-MAX_OUTPUT_LINES:]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    print(f"Tests failed after editing {relative.as_posix()}:", file=sys.stderr)
    print("\n".join(lines), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
