"""Strain recognition — the part that makes HERD a memory rather than a checker.

The claim being made is simple and testable: the *second* time a piece of
misinformation appears, answering it should cost almost nothing. That only
works if two superficially different messages that are the same underlying scam
land on the same strain.

Three mechanisms, in order of authority:

1. Exact/near-exact image match (sha256, then perceptual hash). Free, certain.
2. Dual-vector semantic similarity (ADR-0006): the native-language text and an
   English rendering are embedded separately, and we take the MAXIMUM of the
   two similarities. A Hinglish variant of an English scam is far apart in
   native space but close in English space, and vice-versa for a translated
   template. Taking the max means either route can recognise it; taking the
   mean would let one weak channel veto a correct match.
3. Entity hard gates (ADR-0008). Semantics are fuzzy and will happily merge
   "pay Rs.750 to Zentara" with "pay Rs.5000 to Vertex" because both are
   placement-fee scams. Money and payment rails are facts, not vibes, so a
   disagreement on them VETOES a merge no matter how high the cosine is.

Assignment is incremental (ADR-0007), never a batch re-clustering. A re-cluster
would silently re-partition history, meaning the strain a verdict was attached
to could stop existing. Incremental assignment is also the only version that
can meet the 300 ms cache-hit budget.
"""
from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from app.contracts import Claim, Entities, InstitutionSighting, MutationDiff, Strain
from app.interfaces import EmbeddingModel, Store, VectorIndex

NATIVE_NS = "strain_native"
EN_NS = "strain_en"


@dataclass(frozen=True)
class Assignment:
    """The outcome of showing one claim to the memory."""

    strain: Strain
    kind: str                    # "exact" | "same" | "mutation" | "new"
    similarity: float
    matched_via: str             # "sha256" | "phash" | "native" | "en" | "none"
    gate_vetoed: list[str]       # gates that blocked a higher-scoring candidate
    mutation_diff: MutationDiff | None

    @property
    def recognised(self) -> bool:
        """True means we have seen this before and can serve from memory."""
        return self.kind in ("exact", "same")


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return max(-1.0, min(1.0, num / (na * nb)))


def hamming_hex(a: str | None, b: str | None) -> int | None:
    """Perceptual-hash distance. None when either side is missing."""
    if not a or not b or len(a) != len(b):
        return None
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Entity gates
# --------------------------------------------------------------------------

def _amounts_conflict(a: Sequence[float], b: Sequence[float], tolerance: float) -> bool:
    """True when both sides name money and none of it is compatible.

    Asymmetric on purpose: if one side names no amount, there is no conflict —
    a scam template often drops the figure in one variant. It is only a veto
    when both sides make a claim about money and the claims disagree.
    """
    if not a or not b:
        return False
    for x in a:
        for y in b:
            if x == 0 and y == 0:
                return False
            if abs(x - y) <= tolerance * max(abs(x), abs(y)):
                return False
    return True


def _upi_conflict(a: Sequence[str], b: Sequence[str]) -> bool:
    """Different payment rails means different operations.

    Two scams that share wording but collect at different VPAs are genuinely
    two strains: taking down one does nothing about the other, and telling a
    student "this is the Zentara scam, do not pay ...@okaxis" would name the
    wrong account.
    """
    if not a or not b:
        return False
    return not (set(a) & set(b))


def _org_conflict(a: Sequence[str], b: Sequence[str]) -> bool:
    """Named organisations must overlap once both sides name one.

    Compared on a normalised form so 'Zentara Systems' and 'ZENTARA systems'
    are the same claim, but 'Zentara' and 'Vertex' are not.
    """
    if not a or not b:
        return False
    na = {re.sub(r"[^a-z]", "", x.lower()) for x in a}
    nb = {re.sub(r"[^a-z]", "", x.lower()) for x in b}
    if na & nb:
        return False
    # Substring containment covers 'Zentara' vs 'Zentara Systems'.
    return not any(x in y or y in x for x in na for y in nb if x and y)


def entity_gates(new: Entities, old: Entities, *, amount_tolerance: float) -> list[str]:
    """Return the names of every gate that vetoes merging `new` into `old`."""
    vetoes: list[str] = []
    if _amounts_conflict(new.amounts, old.amounts, amount_tolerance):
        vetoes.append("amount")
    if _upi_conflict(new.upi_handles, old.upi_handles):
        vetoes.append("upi")
    if _org_conflict(new.organisations, old.organisations):
        vetoes.append("organisation")
    return vetoes


# --------------------------------------------------------------------------
# Mutation description
# --------------------------------------------------------------------------

def describe_mutation(new: Claim, parent: Strain, similarity: float,
                      phash_distance: int | None) -> MutationDiff:
    """Say what actually changed, in the words a human would use.

    This is what makes the mutation story legible on stage: not "cosine 0.79"
    but "same scam, new payment account". The dominant signal is whichever
    dimension moved most, because that is the one worth reporting.
    """
    changes: dict[str, list[str]] = {}
    for field in ("organisations", "upi_handles", "domains", "urls"):
        before = set(getattr(parent.entities, field) or [])
        after = set(getattr(new.entities, field) or [])
        added, removed = sorted(after - before), sorted(before - after)
        if added or removed:
            changes[field] = [f"+{v}" for v in added] + [f"-{v}" for v in removed]
    before_amt = set(parent.entities.amounts or [])
    after_amt = set(new.entities.amounts or [])
    if before_amt != after_amt and (before_amt and after_amt):
        changes["amounts"] = [f"+{v:g}" for v in sorted(after_amt - before_amt)] + \
                             [f"-{v:g}" for v in sorted(before_amt - after_amt)]

    if "upi_handles" in changes:
        dominant, summary = "entity", "same scam, new payment account"
    elif "amounts" in changes:
        dominant, summary = "entity", "same scam, different amount"
    elif "organisations" in changes:
        dominant, summary = "entity", "same template, different company name"
    elif "domains" in changes or "urls" in changes:
        dominant, summary = "entity", "same scam, new link"
    elif phash_distance is not None and phash_distance > 0:
        dominant, summary = "phash", "same wording, re-rendered image"
    else:
        dominant, summary = "semantic", "same scam, reworded"

    return MutationDiff(
        dominant_signal=dominant,
        semantic_distance=round(1.0 - similarity, 4),
        entity_changes=changes,
        phash_distance=phash_distance,
        summary=summary,
    )


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------

class StrainEngine:
    """Incremental assignment against a live index."""

    def __init__(self, *, store: Store, embeddings: EmbeddingModel, index: VectorIndex,
                 same_strain: float, mutation: float, amount_tolerance: float,
                 min_content_chars: int = 25, phash_exact_distance: int = 6) -> None:
        self.store = store
        self.embeddings = embeddings
        self.index = index
        self.same_strain = same_strain
        self.mutation = mutation
        self.amount_tolerance = amount_tolerance
        self.min_content_chars = min_content_chars
        self.phash_exact_distance = phash_exact_distance

    def has_enough_content(self, claim: Claim) -> bool:
        """Is there enough text here to recognise anything at all?

        This guard was added because calibration caught two blank fixtures
        merging into a single strain. That is not a cosmetic scoring artifact —
        it is the shape of a poisoning attack. Near-empty text embeds to a
        near-arbitrary point that other near-empty text is close to, so an
        attacker who uploads a handful of blank screenshots could create an
        attractor strain and then push a real claim into it, inheriting
        whatever verdict that strain carries.

        Insufficient content therefore never recognises, never contributes to a
        centroid, and never enters the index.
        """
        return len((claim.text or "").strip()) >= self.min_content_chars

    def embed_pair(self, claim: Claim) -> tuple[list[float], list[float]]:
        """Native and English vectors (ADR-0006).

        When no translation exists the English vector is the native one. That
        is honest rather than clever: the max() below then simply degrades to a
        single-channel match instead of comparing against a fabricated vector.
        """
        native_text = claim.text or ""
        en_text = claim.text_en or claim.text or ""
        vecs = self.embeddings.encode([native_text, en_text])
        return vecs[0], vecs[1]

    async def assign(self, claim: Claim, *, phash: str | None = None,
                     image_sha256: str | None = None, k: int = 8) -> Assignment:
        if not self.has_enough_content(claim):
            # An image hash can still identify a re-upload of the exact same
            # blank file, but nothing semantic is allowed to match.
            return self._new_strain(claim, phash, ["insufficient_content"], 0.0)

        native, en = self.embed_pair(claim)

        candidates: dict[str, float] = {}
        via: dict[str, str] = {}
        for vec, ns, tag in ((native, NATIVE_NS, "native"), (en, EN_NS, "en")):
            for sid, sim in self.index.query(vec, ns, k=k):
                # MAX, not mean: either language channel is allowed to
                # recognise the strain on its own.
                if sim > candidates.get(sid, -1.0):
                    candidates[sid], via[sid] = sim, tag

        gate_vetoed: list[str] = []
        best: tuple[Strain, float, str, list[str]] | None = None

        for sid, sim in sorted(candidates.items(), key=lambda kv: -kv[1]):
            strain = await self.store.get_strain(sid)
            if strain is None:
                continue

            # Image identity outranks everything: the same picture is the same
            # message, whatever the cosine says.
            if image_sha256 and strain.phash and image_sha256 == strain.phash:
                return self._attach(strain, claim, 1.0, "sha256", "exact", [], None)
            dist = hamming_hex(phash, strain.phash)
            if dist is not None and dist <= self.phash_exact_distance:
                return self._attach(strain, claim, 1.0, "phash", "exact", [], None)

            vetoes = entity_gates(claim.entities, strain.entities,
                                  amount_tolerance=self.amount_tolerance)
            if vetoes and sim < self.mutation:
                # Too far apart to be related AND the facts disagree. Nothing
                # here; keep looking.
                gate_vetoed.extend(f"{sid}:{v}" for v in vetoes)
                continue
            best = (strain, sim, via[sid], vetoes)
            break

        if best is None:
            return self._new_strain(claim, phash, gate_vetoed,
                                    max(candidates.values(), default=0.0))

        strain, sim, matched_via, vetoes = best
        gate_vetoed.extend(f"{strain.id}:{v}" for v in vetoes)

        # A hard gate DEMOTES a match; it does not erase the relationship.
        #
        # This is the distinction that took a failing test to find. Two messages
        # can share a template exactly while naming a different company and a
        # different payment account — that is not one operation, so merging them
        # would make us name the wrong account in a warning. But it is also not
        # an unrelated message: it is the same kit, redeployed. Treating the veto
        # as "unrelated" threw away the single most valuable observation the
        # system makes, which is that the scam is mutating rather than recurring.
        #
        # So: gate clear + very similar -> same strain, serve from memory.
        #     gate vetoed + very similar -> child strain, lineage preserved.
        if sim >= self.same_strain and not vetoes:
            return self._attach(strain, claim, sim, matched_via, "same", gate_vetoed, None)
        if sim >= self.mutation:
            diff = describe_mutation(claim, strain, sim, hamming_hex(phash, strain.phash))
            return self._child_strain(claim, strain, sim, matched_via, gate_vetoed, diff, phash)
        return self._new_strain(claim, phash, gate_vetoed, sim)

    # -- outcome constructors ---------------------------------------------

    def _attach(self, strain: Strain, claim: Claim, sim: float, via: str,
                kind: str, vetoed: list[str], diff: MutationDiff | None) -> Assignment:
        return Assignment(strain=strain, kind=kind, similarity=sim, matched_via=via,
                          gate_vetoed=vetoed, mutation_diff=diff)

    def _child_strain(self, claim: Claim, parent: Strain, sim: float, via: str,
                      vetoed: list[str], diff: MutationDiff, phash: str | None) -> Assignment:
        """A mutation keeps its lineage.

        parent_id is what lets the UI draw the family tree, and what lets the
        prior from the parent inform the child without the child inheriting the
        parent's *verdict* outright — a reworded scam is still probably a scam,
        but it gets its own investigation.
        """
        now = datetime.now(timezone.utc)
        child = Strain(
            id=f"str_{uuid.uuid4().hex[:12]}",
            label=self._label(claim, suffix="variant"),
            parent_id=parent.id,
            aliases=list(parent.aliases),
            centroid_native=[], centroid_en=[],
            entities=claim.entities,
            phash=phash,
            first_seen=now, last_seen=now, report_count=0,
            seen_at=[], mutation_diff=diff, is_fixture=claim.id.startswith("fx_"),
        )
        return Assignment(strain=child, kind="mutation", similarity=sim, matched_via=via,
                          gate_vetoed=vetoed, mutation_diff=diff)

    def _new_strain(self, claim: Claim, phash: str | None, vetoed: list[str],
                    sim: float) -> Assignment:
        now = datetime.now(timezone.utc)
        strain = Strain(
            id=f"str_{uuid.uuid4().hex[:12]}",
            label=self._label(claim),
            parent_id=None, aliases=[],
            centroid_native=[], centroid_en=[],
            entities=claim.entities, phash=phash,
            first_seen=now, last_seen=now, report_count=0,
            seen_at=[], mutation_diff=None, is_fixture=claim.id.startswith("fx_"),
        )
        return Assignment(strain=strain, kind="new", similarity=sim, matched_via="none",
                          gate_vetoed=vetoed, mutation_diff=None)

    @staticmethod
    def _label(claim: Claim, suffix: str = "") -> str:
        """A human-readable strain name, because 'str_9fa3...' is unreadable on a wall."""
        org = claim.entities.organisations[0] if claim.entities.organisations else None
        amt = f"Rs.{claim.entities.amounts[0]:g}" if claim.entities.amounts else None
        parts = [p for p in (org, claim.claim_type.value.replace("_", " "), amt) if p]
        base = " ".join(parts) if parts else (claim.text or "unnamed")[:40]
        return f"{base} ({suffix})" if suffix else base

    # -- index maintenance -------------------------------------------------

    def commit(self, strain: Strain, claim: Claim, native: Sequence[float],
               en: Sequence[float]) -> Strain:
        """Fold a new report into the strain's centroids and re-index.

        A running mean, so the centroid tracks the family as it drifts without
        ever needing a re-cluster. Early members carry more weight than they
        would under a batch fit, which is the right bias: the first sighting is
        the one a verdict was actually attached to.

        `seen_at` is the ADR-0026 boundary made structural. The strain is global,
        but the only per-institution thing it carries is a count and a date —
        never text, never evidence. A strain object can therefore be shipped to
        another campus wholesale without leaking anything about this one.
        """
        now = datetime.now(timezone.utc)
        n = strain.report_count
        new_native = _running_mean(strain.centroid_native, native, n)
        new_en = _running_mean(strain.centroid_en, en, n)

        sightings = list(strain.seen_at)
        for i, s in enumerate(sightings):
            if s.institution_id == claim.institution_id:
                sightings[i] = s.model_copy(update={"report_count": s.report_count + 1})
                break
        else:
            sightings.append(InstitutionSighting(
                institution_id=claim.institution_id, first_seen=now, report_count=1))

        updated = strain.model_copy(update={
            "centroid_native": new_native,
            "centroid_en": new_en,
            "report_count": n + 1,
            "last_seen": now,
            "seen_at": sightings,
        })
        # A low-content claim is recorded but never indexed, so it can never
        # become something a future claim matches against.
        if self.has_enough_content(claim):
            self.index.upsert(updated.id, new_native, NATIVE_NS, {"label": updated.label})
            self.index.upsert(updated.id, new_en, EN_NS, {"label": updated.label})
        return updated


def _running_mean(current: Sequence[float], new: Sequence[float], n: int) -> list[float]:
    if not current or n <= 0:
        return list(new)
    return [(c * n + v) / (n + 1) for c, v in zip(current, new)]
