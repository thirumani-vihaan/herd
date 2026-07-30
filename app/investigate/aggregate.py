"""Evidence aggregation into a calibrated posterior (ADR-0013).

No agent produces a label. Agents produce `Evidence`, and this module is the
only place a label is decided. That separation is a security control, not
tidiness: the input is a screenshot an attacker controls, so if an LLM could
emit a label then a prompt injection could reach the verdict directly. Here,
the worst an injection can do is add text that the deterministic rules then
score like any other text.

The arithmetic is log-odds:

    log_odds  =  log(prior / (1 - prior))  +  Σ  direction × strength × reliability

with two corrections that turn a plausible-looking number into a calibrated one:

CORRELATION GROUPS. `url_shortener`, `young_domain` and `freemail` are not
three independent observations — they are three faces of one attack kit. Summed
naively, an ordinary scam saturates the posterior at 0.99 and the system becomes
unable to express doubt about anything. Within a group the strongest signal
counts in full and the rest are discounted (0.30), so a kit that trips five
correlated rules ends up meaningfully less certain than one that trips three
genuinely independent ones.

PER-AGENT CAPS. An agent that searched the college site and found nothing has
learned very little — colleges announce late, and pages move. Its contradiction
is capped at 0.30 while its *support* is uncapped, because finding the notice
settles the question and failing to find it does not. The asymmetry is in
config/thresholds.yaml, and every cap there is a claim about how the world
works that a test can hold us to.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from app.contracts import Evidence, VerdictLabel


@dataclass(frozen=True)
class Contribution:
    """One agent's arithmetic, kept so the UI can show the working."""

    agent: str
    signal: str
    raw_strength: float
    reliability: float
    cap_applied: float | None
    correlation_group: str
    discounted: bool
    delta_log_odds: float


@dataclass
class Aggregation:
    prior: float
    posterior_false: float
    log_odds: float
    label: VerdictLabel
    confidence: float
    contributions: list[Contribution] = field(default_factory=list)
    clamped: bool = False
    downgraded_for_lack_of_confirmation: bool = False
    downgraded_for_insufficient_standing: bool = False

    @property
    def abstained(self) -> bool:
        return self.label is VerdictLabel.UNVERIFIED


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class Aggregator:
    @classmethod
    def from_thresholds(cls, thresholds: Any) -> "Aggregator":
        """Single construction site, so a new knob can never be wired in one
        caller and forgotten in another."""
        agg = thresholds.get("aggregation")
        return cls(
            prior_false=agg["prior_false"],
            correlated_discount=agg["correlated_discount"],
            max_abs_log_odds=agg["max_abs_log_odds"],
            caps=agg["caps"],
            reliability=agg["reliability"],
            bands=thresholds.get("verdict.bands"),
            log_odds_per_unit_strength=agg["log_odds_per_unit_strength"],
            confirming_agents=thresholds.get("verdict.confirming_agents"),
            true_requires_confirmation=thresholds.get("verdict.true_requires_confirmation"),
            cannot_conclude_alone=thresholds.get("verdict.cannot_conclude_alone"),
        )

    def __init__(self, *, prior_false: float, correlated_discount: float,
                 max_abs_log_odds: float, caps: dict[str, dict[str, float]],
                 reliability: dict[str, float], bands: dict[str, float],
                 log_odds_per_unit_strength: float,
                 confirming_agents: Sequence[str] = (),
                 true_requires_confirmation: bool = True,
                 cannot_conclude_alone: Sequence[str] = ()) -> None:
        self.prior_false = prior_false
        self.correlated_discount = correlated_discount
        self.max_abs_log_odds = max_abs_log_odds
        self.caps = caps
        self.reliability = reliability
        self.bands = bands
        # Evidence.strength is a 0..1 confidence, not a log-odds delta. Without
        # this conversion the arithmetic looks right and is inert: the whole
        # evidence set could agree and still not reach a verdict band.
        self.scale = log_odds_per_unit_strength
        self.confirming_agents = set(confirming_agents)
        self.true_requires_confirmation = true_requires_confirmation
        self.cannot_conclude_alone = set(cannot_conclude_alone)

    # -- the arithmetic ----------------------------------------------------

    def aggregate(self, evidence: Sequence[Evidence]) -> Aggregation:
        usable = [e for e in evidence if e.status == "ok" and e.signal != "neutral"]

        # Order matters: the strongest member of each correlation group counts
        # at full weight, so sort before grouping.
        scored: list[tuple[Evidence, float, float, float | None]] = []
        for ev in usable:
            reliability = self.reliability.get(ev.agent, 1.0)
            cap = self._cap_for(ev)
            strength = min(ev.strength, cap) if cap is not None else ev.strength
            scored.append((ev, strength, reliability, cap))
        scored.sort(key=lambda t: -(t[1] * t[2]))

        seen_groups: set[str] = set()
        contributions: list[Contribution] = []
        total = 0.0
        for ev, strength, reliability, cap in scored:
            group = ev.correlation_group or "independent"
            # "independent" is a sentinel, not a group: two independent signals
            # must never discount each other.
            discounted = group != "independent" and group in seen_groups
            seen_groups.add(group)
            weight = strength * reliability
            if discounted:
                weight *= self.correlated_discount
            direction = 1.0 if ev.signal == "contradicts" else -1.0
            delta = direction * weight * self.scale
            total += delta
            contributions.append(Contribution(
                agent=ev.agent, signal=ev.signal, raw_strength=ev.strength,
                reliability=reliability, cap_applied=cap, correlation_group=group,
                discounted=discounted, delta_log_odds=round(delta, 4)))

        raw = _logit(self.prior_false) + total
        clamped = abs(raw) > self.max_abs_log_odds
        # The clamp is what keeps confidence away from 1.0. A system that can
        # say "certain" will eventually say it about something it is wrong
        # about, and there is no way to walk that back.
        bounded = max(-self.max_abs_log_odds, min(self.max_abs_log_odds, raw))
        posterior = _sigmoid(bounded)
        confirmed = self._has_confirmation(evidence)
        label = self.label_for(posterior, confirmed=confirmed)

        # ADR-0026. A verdict resting only on what happened at another campus
        # is not this campus's verdict.
        contributing = {c.agent for c in contributions}
        insufficient = bool(contributing) and contributing <= self.cannot_conclude_alone
        if insufficient:
            label = VerdictLabel.UNVERIFIED

        return Aggregation(
            prior=self.prior_false, posterior_false=posterior, log_odds=bounded,
            label=label, confidence=self._confidence(posterior, label),
            contributions=contributions, clamped=clamped,
            downgraded_for_lack_of_confirmation=(
                label is VerdictLabel.UNVERIFIED
                and posterior <= self.bands["unverified_above"]),
            downgraded_for_insufficient_standing=insufficient)

    def _has_confirmation(self, evidence: Sequence[Evidence]) -> bool:
        """Did any agent that is entitled to confirm actually confirm?

        Entitlement matters. FraudHeuristics can observe that nothing looks
        wrong; only an agent that went and looked at a source can observe that
        something is right.
        """
        return any(e.agent in self.confirming_agents and e.status == "ok"
                   and e.signal == "supports" for e in evidence)

    def _cap_for(self, ev: Evidence) -> float | None:
        agent_caps = self.caps.get(ev.agent)
        if not agent_caps:
            return None
        return agent_caps.get(ev.signal)

    def label_for(self, posterior: float, *, confirmed: bool = True) -> VerdictLabel:
        if posterior > self.bands["false_above"]:
            return VerdictLabel.FALSE
        if posterior > self.bands["misleading_above"]:
            return VerdictLabel.MISLEADING
        if posterior > self.bands["unverified_above"]:
            return VerdictLabel.UNVERIFIED
        # The arithmetic says TRUE. That is necessary but not sufficient: the
        # only thing that can make a claim TRUE is a source that found it.
        if self.true_requires_confirmation and not confirmed:
            return VerdictLabel.UNVERIFIED
        return VerdictLabel.TRUE

    def _confidence(self, posterior: float, label: VerdictLabel) -> float:
        """Distance into the band, not the posterior itself.

        Reporting the posterior as confidence would mean a claim sitting at
        0.66 — barely over the MISLEADING line — is announced with 66%
        confidence, when in truth we are almost undecided between two labels.
        Confidence here answers "how far from flipping is this?".
        """
        if label is VerdictLabel.FALSE:
            lo, hi = self.bands["false_above"], 1.0
        elif label is VerdictLabel.MISLEADING:
            lo, hi = self.bands["misleading_above"], self.bands["false_above"]
        elif label is VerdictLabel.UNVERIFIED:
            lo, hi = self.bands["unverified_above"], self.bands["misleading_above"]
        else:
            lo, hi = 0.0, self.bands["unverified_above"]
            return round(max(0.0, min(1.0, 0.5 + 0.5 * (hi - posterior) / max(hi - lo, 1e-6))), 3)
        span = max(hi - lo, 1e-6)
        return round(max(0.0, min(1.0, 0.5 + 0.5 * (posterior - lo) / span)), 3)

    # -- introspection used by the cascade ---------------------------------

    def decisiveness(self, agg: Aggregation) -> float:
        """How far the posterior is from the nearest band edge, in [0, 1].

        The cascade exits when this is high — meaning more evidence is unlikely
        to change the label — rather than when the posterior is merely extreme.
        """
        edges = [0.0, self.bands["unverified_above"], self.bands["misleading_above"],
                 self.bands["false_above"], 1.0]
        p = agg.posterior_false
        lo = max(e for e in edges if e <= p)
        hi = min(e for e in edges if e >= p)
        if hi == lo:
            return 0.0
        return min(p - lo, hi - p) / ((hi - lo) / 2)


def explain(contributions: Iterable[Contribution]) -> list[str]:
    """Plain-language lines for the evidence panel."""
    out: list[str] = []
    for c in contributions:
        direction = "against" if c.signal == "contradicts" else "for"
        note = []
        if c.cap_applied is not None and c.cap_applied < c.raw_strength:
            note.append(f"capped at {c.cap_applied:.2f}")
        if c.discounted:
            note.append(f"discounted (correlated with another {c.correlation_group} signal)")
        suffix = f" [{'; '.join(note)}]" if note else ""
        out.append(f"{c.agent}: {direction} the claim, {abs(c.delta_log_odds):.2f} log-odds{suffix}")
    return out
