"""Secret scanner. Blocks a commit if a credential reaches the staged diff.

Exit 0 = clean, 1 = leak found. No override path by design (L2).
"""
from __future__ import annotations

import re
import subprocess
import sys

# Patterns are deliberately specific. A scanner that cries wolf gets disabled,
# which is worse than not having one.
PATTERNS: list[tuple[str, str]] = [
    ("google_api_key", r"AIza[0-9A-Za-z_\-]{30,}"),
    ("google_oauth_key", r"\bAQ\.[A-Za-z0-9_\-]{25,}"),
    ("github_pat_classic", r"\bghp_[A-Za-z0-9]{30,}"),
    ("github_pat_fine", r"\bgithub_pat_[A-Za-z0-9_]{50,}"),
    ("telegram_bot_token", r"\b\d{8,12}:AA[A-Za-z0-9_\-]{30,}"),
    ("aws_access_key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("private_key_block", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ("slack_token", r"\bxox[baprs]-[0-9A-Za-z\-]{10,}"),
    ("bearer_in_url", r"://[^/\s:@]+:[^/\s@]{16,}@"),
]

# Files that are allowed to contain pattern-shaped text because they document
# the shape rather than carry a value.
ALLOWLIST_PATHS = {
    "tools/secret_scan.py",
    "tools/acceptance/T003.py",
}

# A placeholder is not a secret. Anything matching these is ignored.
PLACEHOLDER = re.compile(
    r"(?i)(your[_\-]?|example|placeholder|xxxx|<[a-z_]+>|\*\*\*|dummy|redacted|changeme)"
)


def staged_diff() -> str:
    r = subprocess.run(
        ["git", "diff", "--cached", "--unified=0"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return r.stdout or ""


def working_tree_files() -> list[str]:
    r = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return [p for p in (r.stdout or "").splitlines() if p.strip()]


def scan_text(text: str, origin: str) -> list[str]:
    hits: list[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if PLACEHOLDER.search(line):
            continue
        for name, pat in PATTERNS:
            if re.search(pat, line):
                hits.append(f"{origin}:{lineno}  [{name}]")
    return hits


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "staged"
    hits: list[str] = []

    if mode in ("staged", "all"):
        diff = staged_diff()
        added = "\n".join(
            l[1:] for l in diff.splitlines()
            if l.startswith("+") and not l.startswith("+++")
        )
        hits += scan_text(added, "STAGED")

    if mode == "all":
        for path in working_tree_files():
            if path in ALLOWLIST_PATHS:
                continue
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    hits += scan_text(fh.read(), path)
            except (OSError, UnicodeError):
                continue

    if hits:
        print("SECRET SCAN FAILED - commit blocked (L2)")
        for h in hits:
            print("  " + h)
        return 1

    print(f"SECRET SCAN CLEAN ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
