"""Tests for the plugin entry point and the Python environment check."""

import subprocess
import sys
from pathlib import Path

from src import setup_env
from tagi import COMMANDS, main


def test_parse_requirements_reads_bounds():
    parsed = setup_env.parse_requirements("pandas>=3.0,<4\n# comment\n\nopenpyxl>=3.1\n")
    assert parsed == [("pandas", (3, 0), (4,)), ("openpyxl", (3, 1), None)]


def test_missing_requirements_checks_presence_and_versions():
    assert setup_env.missing_requirements(setup_env.parse_requirements("pandas>=1.0,<99")) == []
    assert setup_env.missing_requirements(setup_env.parse_requirements("pandas>=99.0")) == ["pandas"]
    assert setup_env.missing_requirements(setup_env.parse_requirements("pandas<1.0")) == ["pandas"]
    assert setup_env.missing_requirements(setup_env.parse_requirements("no-such-package-xyz")) == ["no-such-package-xyz"]


def test_a_python_that_has_everything_is_used_as_is(tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("pandas>=1.0\n", encoding="utf-8")
    assert setup_env.prepare(tmp_path / "env", requirements) == Path(sys.executable)
    assert not (tmp_path / "env").exists()


def test_the_project_requirements_are_satisfied_here():
    text = setup_env.REQUIREMENTS.read_text(encoding="utf-8")
    assert setup_env.missing_requirements(setup_env.parse_requirements(text)) == []


def test_unknown_command_shows_usage(capsys):
    assert main(["magic"]) == 2
    usage = capsys.readouterr().err
    assert all(command in usage for command in COMMANDS)


def test_entry_point_runs_from_another_folder(tmp_path):
    # The plugin runs from the user's folder, not from the repo: imports must still work.
    output = tmp_path / "metrics.json"
    result = subprocess.run([sys.executable, str(setup_env.ROOT / "tagi.py"), "metrics", "--output", str(output)],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert '"n_reviews": 600' in output.read_text(encoding="utf-8")
