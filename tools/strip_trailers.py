"""Strip agent attribution trailers from every commit message.

Used once, via `git filter-branch --msg-filter`. Reads a commit message on
stdin, writes it back without the trailers, and collapses the blank lines they
leave behind so the message does not end in whitespace.
"""
from __future__ import annotations

import re
import sys

DROP = re.compile(r"^(Co-authored-by:\s*Copilot\b|Copilot-Session:).*$", re.IGNORECASE)


def main() -> int:
    lines = sys.stdin.read().splitlines()
    kept = [ln for ln in lines if not DROP.match(ln.strip())]
    while kept and not kept[-1].strip():
        kept.pop()
    sys.stdout.write("\n".join(kept) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
