"""Prepare a Python that can run the analysis, wherever the plugin is installed.

Uses the current Python when it already has the libraries (a sandbox that ships
pandas, or the project's own .venv). Otherwise it creates a virtual environment
in --env-dir and installs requirements.txt there, once: later runs only check.

Standard library only, because it runs before anything is installed.

Prints one line for the caller to read: TAGI_PYTHON=<path to the Python to use>.
"""

import argparse
import hashlib
import importlib.metadata
import os
import re
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements.txt"
MIN_PYTHON = (3, 11)
MARKER = "tagi-requirements.sha256"


def parse_requirements(text):
    """[(name, lower, upper)] from lines like "pandas>=3.0,<4"; bounds are int tuples or None."""
    requirements = []
    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        name = re.match(r"[A-Za-z0-9_.-]+", line).group(0)
        lower = re.search(r">=\s*([\d.]+)", line)
        upper = re.search(r"<\s*([\d.]+)", line)
        requirements.append((name, _version(lower.group(1)) if lower else None, _version(upper.group(1)) if upper else None))
    return requirements


def _version(text):
    return tuple(int(part) for part in re.findall(r"\d+", text))


def missing_requirements(requirements):
    """Names of the requirements the running Python lacks or has in a version out of range."""
    missing = []
    for name, lower, upper in requirements:
        try:
            installed = _version(importlib.metadata.version(name))
        except importlib.metadata.PackageNotFoundError:
            missing.append(name)
            continue
        if (lower and installed < lower) or (upper and installed >= upper):
            missing.append(name)
    return missing


def venv_python(env_dir):
    folder = "Scripts" if os.name == "nt" else "bin"
    return Path(env_dir).resolve() / "venv" / folder / ("python.exe" if os.name == "nt" else "python")


def prepare(env_dir, requirements_path=REQUIREMENTS):
    """Return the path of a Python with every requirement, installing them if needed."""
    if sys.version_info < MIN_PYTHON:
        raise SystemExit(
            f"Tagi necesita Python {'.'.join(map(str, MIN_PYTHON))} o más nuevo y este es "
            f"{sys.version.split()[0]}. Instálelo desde https://www.python.org/downloads/ y vuelva a intentarlo."
        )
    text = requirements_path.read_text(encoding="utf-8")
    if not missing_requirements(parse_requirements(text)):
        return Path(sys.executable)

    python = venv_python(env_dir)
    marker = Path(env_dir) / MARKER
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if python.exists() and marker.exists() and marker.read_text(encoding="utf-8") == digest:
        return python

    print("Preparando Python para Tagi (solo la primera vez, puede tardar un par de minutos)...", file=sys.stderr)
    try:
        venv.create(Path(env_dir) / "venv", with_pip=True, clear=python.exists())
    except Exception as error:  # noqa: BLE001 - any failure here gets the same plain message
        raise SystemExit(
            "No se pudo crear un entorno de Python para Tagi. En Linux suele faltar el paquete "
            f"python3-venv. Detalle técnico: {error}"
        ) from error
    install = subprocess.run([str(python), "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
                              "-r", str(requirements_path)], capture_output=True, text=True)
    if install.returncode != 0:
        detail = (install.stderr or install.stdout).strip().splitlines()[-1:] or ["sin detalle"]
        raise SystemExit(
            "No se pudieron instalar pandas y openpyxl, que Tagi necesita. Revise la conexión a "
            f"internet y vuelva a intentarlo. Detalle técnico: {detail[0]}"
        )
    marker.write_text(digest, encoding="utf-8")
    return python


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prepare the Python environment for the analysis.")
    parser.add_argument("--env-dir", default=Path.home() / ".tagi",
                        help="where to keep the environment if one is needed (default: ~/.tagi)")
    args = parser.parse_args(argv)
    print(f"TAGI_PYTHON={prepare(args.env_dir)}")


if __name__ == "__main__":
    main()
