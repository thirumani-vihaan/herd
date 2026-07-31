"""L13 - institution neutrality linter.

Fails if any institution-specific fact appears in app/, web/, or a prompt. The
values come from the profiles themselves, so the check keeps working when a new
profile is added without anyone remembering to update this file.

Exit 0 = neutral, 1 = violation.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ["app", "web/src"]
SCAN_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".json"}

# This module is allowed to name profiles; it is the door they come through.
EXEMPT = {
    "app/institution.py",
    "app/config.py",
    "tools/lint_institution.py",
}

# Generic words that also appear in profiles but are not institution-identifying.
GENERIC = {
    "en", "hi", "te", "inr", "ug", "pg", "website", "email_domain", "telegram",
    "phone", "html", "rss", "year", "branch", "programme", "department",
    "placement", "fee", "exam", "scholarship", "drive", "internship",
    "recruitment", "never", "computing", "electronics", "mechanical",
    "management", "it", "civil", "auto",
}


def forbidden_terms() -> dict[str, str]:
    """Every identifying string from every profile -> the profile it came from."""
    terms: dict[str, str] = {}
    for path in sorted((ROOT / "config" / "institutions").glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        pid = path.stem
        if pid.startswith("_"):
            continue

        def add(v):
            if isinstance(v, str) and len(v) > 3 and v.lower() not in GENERIC:
                terms[v.lower()] = pid

        add(raw.get("id"))
        add(raw.get("display_name"))
        add(raw.get("short_name"))
        for d in (raw.get("domains") or {}).get("official") or []:
            add(d)
        for s in raw.get("sources") or []:
            add(s.get("url"))
        for c in raw.get("official_channels") or []:
            add(c.get("value"))
        for dim in (raw.get("cohorts") or {}).get("dimensions") or []:
            for v in dim.get("values") or []:
                add(v)
    return terms


def scan() -> list[str]:
    terms = forbidden_terms()
    if not terms:
        print("WARNING: no profiles found; linter has nothing to enforce")
    violations: list[str] = []
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.suffix not in SCAN_EXT or not path.is_file():
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel in EXEMPT or "node_modules" in rel:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            low = text.lower()
            for term, origin in terms.items():
                # Match on word boundaries. A cohort value like "mech" must not
                # fire on the word "mechanisms"; a substring hit is a false
                # accusation, and a linter nobody trusts gets switched off.
                m = re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", low)
                if not m:
                    continue
                line = low[: m.start()].count("\n") + 1
                violations.append(
                    f"{rel}:{line}  contains '{term}' (from profile '{origin}') - "
                    f"read it from the Institution model instead"
                )
    return violations


def main() -> int:
    v = scan()
    if v:
        print("L13 INSTITUTION NEUTRALITY VIOLATION")
        for line in v:
            print("  " + line)
        print("\nNothing institution-specific belongs in app/ or web/ (ADR-0026).")
        return 1
    print("L13 OK - no institution-specific strings in app/ or web/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
