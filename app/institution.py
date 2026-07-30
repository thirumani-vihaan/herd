"""Institution profile loader (ADR-0026).

The whole point: nothing institution-specific exists in code. This module is the
single door through which institutional facts enter the process, and
`tools/lint_institution.py` proves there is no second door.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from app.config import get_settings
from app.contracts import Institution


class ProfileError(RuntimeError):
    pass


def _normalise(raw: dict) -> dict:
    """Tolerate the two shapes the schema allows for `domains.email`.

    The template documents both `email: [...]` and `email: {verified, values}`,
    because an author needs to be able to mark a guess. Both mean the same thing
    to every consumer, so they are unified here rather than at each call site.
    """
    dom = raw.get("domains") or {}
    email = dom.get("email")
    if isinstance(email, dict):
        dom = dict(dom)
        dom["email"] = list(email.get("values") or [])
        raw = dict(raw)
        raw["domains"] = dom
    return raw


def load_profile(institution_id: str, directory: Path | None = None) -> Institution:
    d = directory or get_settings().institutions_dir
    path = d / f"{institution_id}.yaml"
    if not path.exists():
        available = sorted(p.stem for p in d.glob("*.yaml") if not p.stem.startswith("_"))
        raise ProfileError(
            f"no institution profile '{institution_id}' in {d}. Available: {available}. "
            f"Copy _template.yaml to add one - no code change is needed."
        )

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if raw.get("id") != institution_id:
        raise ProfileError(
            f"{path.name}: id field is '{raw.get('id')}' but filename stem is "
            f"'{institution_id}'. They must match."
        )
    try:
        inst = Institution.model_validate(_normalise(raw))
    except Exception as exc:
        raise ProfileError(f"{path.name} failed validation: {exc}") from exc
    return inst


@lru_cache(maxsize=8)
def get_institution(institution_id: str | None = None) -> Institution:
    """The active profile. Immutable for the process lifetime."""
    return load_profile(institution_id or get_settings().institution_id)


def startup_report(inst: Institution) -> list[str]:
    """Lines the process logs at boot. Unverified blocks are announced, not
    hidden — guessing quietly is the failure mode this prevents."""
    lines = [
        f"institution: {inst.id} ({inst.display_name})",
        f"  sources: {len(inst.sources)}  channels: {len(inst.official_channels)}",
        f"  cohort dimensions: {[d.id for d in inst.cohorts.dimensions]}",
    ]
    if inst.synthetic:
        lines.append("  SYNTHETIC PROFILE - all derived data is labelled synthetic in the UI")
    unverified = inst.unverified_blocks()
    if unverified:
        lines.append(
            f"  UNVERIFIED blocks: {unverified} - usable for reasoning, never shown as fact"
        )
    return lines
