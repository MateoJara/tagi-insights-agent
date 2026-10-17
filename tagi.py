"""Entry point of the Tagi plugin: runs each step of the analysis from any folder.

Usage: python tagi.py <command> [options]

  setup      prepare a Python with the libraries the analysis needs
  ingest     inspect a folder of reviews, or apply an import plan
  metrics    figures of the reviews, as JSON
  comments   export the comments, or count their labels
  dashboard  build the owner's HTML dashboard

Run `python tagi.py <command> --help` for the options of each one.
"""

import importlib
import sys
from pathlib import Path

# The plugin can be installed anywhere: make its own code importable from any folder.
sys.path.insert(0, str(Path(__file__).resolve().parent))

COMMANDS = {
    "setup": "src.setup_env",
    "ingest": "src.ingest",
    "metrics": "src.metrics",
    "comments": "src.comments",
    "dashboard": "src.dashboard",
}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in COMMANDS:
        print(__doc__, file=sys.stderr)
        return 2
    importlib.import_module(COMMANDS[argv[0]]).main(argv[1:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
