#!/usr/bin/env python3
"""Entrypoint for groupctl deterministic collaboration CLI."""

import sys
from groupctl_pkg.cli import main

if __name__ == "__main__":
    sys.exit(main())
