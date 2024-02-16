#!/usr/bin/env python

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from entrypoint import entrypoint  # noqa: E402


if __name__ == "__main__":
    entrypoint()
