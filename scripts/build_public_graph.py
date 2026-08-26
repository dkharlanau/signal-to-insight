#!/usr/bin/env python3
"""Build the public knowledge page from the published-only graph projection."""

from __future__ import annotations

import build_graph
from public_projection import public_graph


def main() -> int:
    build_graph.public_graph = public_graph
    return build_graph.main()


if __name__ == "__main__":
    raise SystemExit(main())
