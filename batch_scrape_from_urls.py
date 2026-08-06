"""Deprecated: use `python main.py scrape urls.txt` instead."""

import sys

from sponsor_pipeline.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["scrape"] + sys.argv[1:]))
