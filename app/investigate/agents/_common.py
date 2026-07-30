"""Shared machinery for agents that weigh several findings into one Evidence.

The `InvestigationAgent` contract returns a single `Evidence`, deliberately: a
verdict panel with fourteen rows is a wall, not an explanation. But an agent
that discovers four things and reports only the loudest is not reporting what
it found. `net()` is the resolution — accumulate both directions with the same
correlation discipline the aggregator uses, subtract, and cite everything
including the losing side.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

# Suffixes where the registrable domain is three labels, not two. Without this,
# `vnrvjiet.ac.in` reduces to `ac.in` and every Indian college looks like every
# other one — which would make the lookalike check accuse all of them.
MULTI_PART_SUFFIXES = {
    "ac.in", "co.in", "edu.in", "org.in", "net.in", "gov.in", "res.in",
    "nic.in", "co.uk", "ac.uk", "org.uk", "gov.uk", "com.au", "edu.au",
    "co.za", "com.br", "co.jp", "com.sg", "edu.pk", "edu.bd",
}

# TLDs that are cheap, bulk-registrable and disproportionately represented in
# campus scams. Not evidence on their own — plenty of legitimate sites use
# them — which is why the weight attached is the smallest in the agent.
SUSPICIOUS_TLDS = {
    "xyz", "top", "online", "site", "click", "link", "live", "shop", "store",
    "buzz", "icu", "cyou", "rest", "monster", "quest", "fit", "cfd", "sbs",
}

FREEMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "yahoo.in", "yahoo.co.in", "hotmail.com",
    "outlook.com", "live.com", "rediffmail.com", "protonmail.com",
    "proton.me", "icloud.com", "aol.com", "zoho.com", "mail.com",
}


def ms_since(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


def registrable(domain: str) -> str:
    """The part someone actually bought."""
    host = (domain or "").strip().lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = [p for p in host.split(".") if p]
    if len(parts) <= 2:
        return ".".join(parts)
    if ".".join(parts[-2:]) in MULTI_PART_SUFFIXES:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def label_of(domain: str) -> str:
    """The distinctive part: `vnrvjiet` from `vnrvjiet.ac.in`."""
    reg = registrable(domain)
    return reg.split(".")[0] if reg else ""


def tld_of(domain: str) -> str:
    reg = registrable(domain)
    return reg.rsplit(".", 1)[-1] if "." in reg else ""


def is_within(domain: str, officials: set[str]) -> bool:
    """True if `domain` is one of the official domains or a subdomain of one.

    Subdomains count because institutions really do run
    `placements.college.ac.in`, and refusing to recognise their own subdomains
    would make HERD flag the college for impersonating itself.
    """
    host = (domain or "").strip().lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    for official in officials:
        o = official.strip().lower().lstrip(".").rstrip(".")
        if not o:
            continue
        if host == o or host.endswith("." + o):
            return True
    return False


def edit_distance(a: str, b: str, *, cap: int = 4) -> int:
    """Levenshtein, abandoned once it exceeds `cap`.

    The cap is not an optimisation. Every use here asks "are these two strings
    nearly the same", and an exact distance of 37 answers that no better than
    "more than 4" while inviting someone to reuse the number for something it
    was never calibrated for.
    """
    if a == b:
        return 0
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (ca != cb)))
        if min(current) > cap:
            return cap + 1
        previous = current
    return previous[-1]


@dataclass
class Finding:
    """One thing an agent noticed, with the citation that backs it."""

    id: str
    signal: str                      # 'contradicts' | 'supports'
    strength: float
    title: str
    detail: str = ""
    url: str = ""
    kind: str = "rule"
    correlation_group: str = "independent"


@dataclass
class Netted:
    signal: str
    strength: float
    winners: list[Finding] = field(default_factory=list)
    all_findings: list[Finding] = field(default_factory=list)
    correlation_group: str = "independent"

    @property
    def is_neutral(self) -> bool:
        return self.strength <= 0.0


def _accumulate(findings: list[Finding], signal: str, discount: float) -> float:
    side = sorted((f for f in findings if f.signal == signal),
                  key=lambda f: -f.strength)
    groups: dict[str, list[float]] = {}
    for f in side:
        groups.setdefault(f.correlation_group, []).append(f.strength)
    total = 0.0
    for weights in groups.values():
        total += weights[0] + discount * sum(weights[1:])
    return total


def net(findings: list[Finding], *, discount: float, saturation: float) -> Netted:
    """Weigh both directions against each other and report the remainder."""
    if not findings:
        return Netted("neutral", 0.0)

    contra = _accumulate(findings, "contradicts", discount)
    supp = _accumulate(findings, "supports", discount)
    delta = contra - supp
    if abs(delta) < 1e-9:
        return Netted("neutral", 0.0, [], list(findings))

    signal = "contradicts" if delta > 0 else "supports"
    winners = sorted((f for f in findings if f.signal == signal),
                     key=lambda f: -f.strength)
    losers = [f for f in findings if f.signal != signal]
    return Netted(
        signal=signal,
        strength=min(1.0, abs(delta) / saturation),
        winners=winners,
        all_findings=winners + losers,
        correlation_group=winners[0].correlation_group if winners else "independent")
