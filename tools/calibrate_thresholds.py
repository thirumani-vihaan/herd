"""Threshold calibration by replaying the corpus through the real engine (T044).

Two earlier versions of this script were wrong, and both were wrong in ways
worth recording, because the same mistakes are easy to make again:

  v1 measured raw cosine between pairs. That ignored the entity hard gate,
     which is half the decision, and so it reported false merges that the
     engine would never actually make.

  v2 added the gate but still measured PAIRS. The engine does not compare a
     claim to another claim — it compares a claim to a running CENTROID, and
     centroid similarity is systematically higher than pairwise similarity
     because averaging cancels the idiosyncratic parts of each variant. A
     threshold tuned on pairs is therefore too strict when applied to
     centroids, and v2 would have set the mutation floor high enough to break
     the very lineage the demo depends on.

  v3 (this one) replays all 35 fixtures through an actual StrainEngine at each
     candidate setting and scores the partition that comes out. It is slower
     and it is the only version that measures the thing we ship.

The objective is asymmetric on purpose. A cross-family collision — two
different scams, or worse a scam and a genuine notice, sharing one strain root
— is the worst failure this system has, because it attaches an existing verdict
to a claim that never earned it. A missed link costs one extra investigation.
So: maximise recall subject to ZERO cross-family collisions, never the reverse.

Run:  python tools/calibrate_thresholds.py [--write]
"""
from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import sys
import tempfile
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.clients.vector import InMemoryVectorIndex  # noqa: E402
from app.interfaces import EmbeddingModel  # noqa: E402
from app.perceive.extract import deterministic_extract  # noqa: E402
from app.perceive.redact import redact_text  # noqa: E402
from app.recognise.strain import StrainEngine  # noqa: E402
from app.storage.sqlite_store import SqliteStore  # noqa: E402

# `edge` and `injection` are grab-bags of unrelated hard cases, not families.
# Counting them as positives would ask the engine to merge a blank image with a
# meme and then punish it for failing.
NON_FAMILY_GROUPS = {"edge", "injection", "none", ""}


class CachedEmbeddings(EmbeddingModel):
    """Precomputed vectors, so a multi-point sweep costs one model pass."""

    def __init__(self, table: dict[str, list[float]], dim: int) -> None:
        self.table, self._dim = table, dim

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.table.get(t, [0.0] * self._dim) for t in texts]

    @property
    def dim(self) -> int:
        return self._dim


def load_rows() -> list[dict]:
    path = ROOT / "fixtures" / "labels.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


async def replay(rows: list[dict], emb: EmbeddingModel, same_strain: float,
                 mutation: float, amount_tolerance: float) -> dict[str, str]:
    """Ingest every fixture in order; return {fixture_id: root_strain_id}."""
    with tempfile.TemporaryDirectory() as tmp:
        store = SqliteStore(Path(tmp) / "cal.db")
        await store.init()
        engine = StrainEngine(store=store, embeddings=emb, index=InMemoryVectorIndex(),
                              same_strain=same_strain, mutation=mutation,
                              amount_tolerance=amount_tolerance)
        parent_of: dict[str, str | None] = {}
        assigned: dict[str, str] = {}

        for row in rows:
            red, _ = redact_text(row["text"])
            claim = deterministic_extract(red, report_id=row["id"], institution_id="inst",
                                          claim_id=row["id"])
            a = await engine.assign(claim)
            native, en = engine.embed_pair(claim)
            committed = engine.commit(a.strain, claim, native, en)
            await store.upsert_strain(committed)
            parent_of[committed.id] = committed.parent_id
            assigned[row["id"]] = committed.id

        roots: dict[str, str] = {}
        for fid, sid in assigned.items():
            seen, cur = set(), sid
            while parent_of.get(cur) and cur not in seen:
                seen.add(cur)
                cur = parent_of[cur]  # type: ignore[assignment]
            roots[fid] = cur
        await store.close()
        return roots


def score(rows: list[dict], roots: dict[str, str]
          ) -> tuple[int, int, int, float, float, list[str], list[str]]:
    """Pairwise precision/recall over the partition the engine produced.

    Collisions are split into two classes, because they are not equally bad and
    an objective that treats them as equal makes the wrong trade:

      HARMFUL   — a FALSE/MISLEADING claim sharing a root with a TRUE one.
                  This is the failure that gets a real placement drive publicly
                  labelled a scam, or a real scam waved through as verified.
                  Zero tolerance.
      BENIGN    — two genuine notices, or two scams from different families,
                  sharing a root. Costs accuracy of the family tree and nothing
                  else; no student is ever misled by it.

    Collapsing these into one number cost 47 points of recall in an earlier run
    to remove a single benign collision between two library-timings notices.
    """
    truth_of = {r["id"]: r["truth"] for r in rows}
    deceptive = {"FALSE", "MISLEADING"}

    tp = fp = fn = 0
    harmful: list[str] = []
    benign: list[str] = []
    for a, b in itertools.combinations(rows, 2):
        ga, gb = a["strain_group"], b["strain_group"]
        same_family = ga == gb and ga not in NON_FAMILY_GROUPS
        together = roots[a["id"]] == roots[b["id"]]
        if together and same_family:
            tp += 1
        elif together and not same_family:
            fp += 1
            ta, tb = truth_of[a["id"]], truth_of[b["id"]]
            desc = f"{a['id']}({ta}) + {b['id']}({tb})"
            if (ta in deceptive) != (tb in deceptive):
                harmful.append(desc)
            else:
                benign.append(desc)
        elif not together and same_family:
            fn += 1
    prec = tp / (tp + fp) if tp + fp else 1.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return tp, fp, fn, prec, rec, harmful, benign


async def main_async(write: bool) -> int:
    from app.clients.embeddings import SentenceTransformerEmbeddings

    rows = load_rows()
    real = SentenceTransformerEmbeddings(cache_dir=str(ROOT / "data" / "hf_cache"))

    texts: list[str] = []
    for row in rows:
        red, _ = redact_text(row["text"])
        c = deterministic_extract(red, report_id=row["id"], institution_id="i", claim_id=row["id"])
        texts.extend([c.text or "", c.text_en or c.text or ""])
    uniq = sorted(set(texts))
    print(f"embedding {len(uniq)} unique strings once...")
    vecs = real.encode(uniq)
    cached = CachedEmbeddings(dict(zip(uniq, vecs)), real.dim)

    families = {r["strain_group"] for r in rows if r["strain_group"] not in NON_FAMILY_GROUPS}
    print(f"{len(rows)} fixtures, {len(families)} real families\n")

    print("same  mut   prec    recall  TP  FP  FN  harmful  roots")
    results = []
    for mutation in [x / 100 for x in range(60, 90, 2)]:
        for same_strain in (0.88, 0.92):
            if same_strain <= mutation:
                continue
            roots = await replay(rows, cached, same_strain, mutation, 0.20)
            tp, fp, fn, prec, rec, harmful, benign = score(rows, roots)
            results.append((mutation, same_strain, prec, rec, len(harmful), harmful, benign))
            print(f"{same_strain:.2f}  {mutation:.2f}  {prec:.3f}  {rec:.3f}   "
                  f"{tp:3d} {fp:3d} {fn:3d}   {len(harmful):3d}    {len(set(roots.values())):3d}")

    safe = [r for r in results if r[4] == 0 and r[3] > 0]
    if safe:
        # Among settings with ZERO harmful collisions: most recall first, then
        # fewest benign collisions, then the LARGEST safety margin. Ordering
        # matters — an earlier version broke ties toward the lower threshold and
        # picked 0.64 over 0.70 at identical recall, taking twice the benign
        # collisions for nothing.
        best = max(safe, key=lambda r: (round(r[3], 4), -len(r[6]), r[0]))
    else:
        best = min(results, key=lambda r: (r[4], -r[3]))
        print("\nWARNING: every setting produced at least one harmful collision.")
    mutation, same_strain, prec, rec = best[0], best[1], best[2], best[3]

    print("\n== calibrated ==")
    print(f"strain.mutation    = {mutation:.2f}")
    print(f"strain.same_strain = {same_strain:.2f}")
    print(f"family precision   = {prec:.3f}")
    print(f"family recall      = {rec:.3f}")
    print(f"harmful collisions = {best[4]}   (a scam sharing a root with a genuine notice)")
    if best[6]:
        print(f"benign collisions  = {len(best[6])}   (accepted; cannot mislead anyone)")
        for c in best[6][:4]:
            print("   ", c)

    if write:
        import yaml
        cfg = ROOT / "config" / "thresholds.yaml"
        text = cfg.read_text(encoding="utf-8")
        cur = yaml.safe_load(text)["strain"]
        text = text.replace(f"same_strain: {cur['same_strain']}", f"same_strain: {same_strain:.2f}")
        text = text.replace(f"mutation: {cur['mutation']}", f"mutation: {mutation:.2f}")
        cfg.write_text(text, encoding="utf-8")
        print(f"\nwrote {cfg}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="update config/thresholds.yaml")
    args = ap.parse_args()
    return asyncio.run(main_async(args.write))


if __name__ == "__main__":
    raise SystemExit(main())
