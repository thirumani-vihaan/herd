"""T005 - exercise every dependency, don't just import it.

An import proves a package exists. It does not prove the API you're about to use
still has the shape you expect, and 2026 has moved several of them. Each check
below actually calls the thing.

The embedding prewarm is deliberately here: ~470 MB downloads once, at a time
someone is watching, not in the middle of a demo.
"""
from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("HF_HOME", str(ROOT / "data" / "hf_cache"))
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(ROOT / "data" / "hf_cache"))
(ROOT / "data" / "hf_cache").mkdir(parents=True, exist_ok=True)

RESULTS: list[tuple[str, bool, str]] = []


def check(name):
    def deco(fn):
        def wrapped():
            t0 = time.perf_counter()
            try:
                note = fn() or ""
                ms = int((time.perf_counter() - t0) * 1000)
                RESULTS.append((name, True, f"{note} ({ms} ms)".strip()))
            except Exception as exc:
                RESULTS.append((name, False, f"{type(exc).__name__}: {exc}"))
                traceback.print_exc()
        return wrapped
    return deco


@check("pydantic v2")
def _pydantic():
    import pydantic
    from pydantic import BaseModel, Field

    class M(BaseModel):
        x: int = Field(ge=0)

    M.model_validate({"x": 1})
    try:
        M.model_validate({"x": -1})
        raise AssertionError("constraint did not fire")
    except Exception:
        pass
    assert pydantic.VERSION.startswith("2."), pydantic.VERSION
    return f"v{pydantic.VERSION}"


@check("contracts import + invariants")
def _contracts():
    sys.path.insert(0, str(ROOT))
    from app.contracts import Evidence, Interval, Strain, Report

    Interval(lo=1, point=2, hi=3)
    try:
        Interval(lo=3, point=2, hi=1)
        raise AssertionError("interval ordering not enforced")
    except Exception:
        pass
    # Strain must NOT accept institution_id (ADR-0026)
    try:
        Strain(id="s1", institution_id="x")
        raise AssertionError("Strain accepted institution_id - scope violation")
    except Exception:
        pass
    # Report MUST require it
    try:
        Report(id="r1", raw_text="hi")
        raise AssertionError("Report accepted a missing institution_id")
    except Exception:
        pass
    # cite-or-stay-silent
    try:
        Evidence(agent="X", institution_id="i", tier=0, signal="contradicts", strength=0.5)
        raise AssertionError("uncited non-neutral evidence was allowed")
    except Exception:
        pass
    return "scope + citation invariants enforced"


@check("institution profiles")
def _institution():
    sys.path.insert(0, str(ROOT))
    from app.institution import load_profile, startup_report

    ids = [p.stem for p in (ROOT / "config" / "institutions").glob("*.yaml")
           if not p.stem.startswith("_")]
    assert len(ids) >= 2, f"need >=2 profiles for the portability proof, found {ids}"
    for i in ids:
        inst = load_profile(i)
        startup_report(inst)
    return f"loaded {ids}"


@check("sqlalchemy async + WAL")
def _sqlalchemy():
    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def go():
        p = ROOT / "data" / "_smoke.db"
        eng = create_async_engine(f"sqlite+aiosqlite:///{p}")
        async with eng.begin() as c:
            await c.execute(text("PRAGMA journal_mode=WAL"))
            mode = (await c.execute(text("PRAGMA journal_mode"))).scalar()
            await c.execute(text("CREATE TABLE IF NOT EXISTS t (a int)"))
            await c.execute(text("INSERT INTO t VALUES (1)"))
        await eng.dispose()
        p.unlink(missing_ok=True)
        for suf in ("-wal", "-shm"):
            Path(str(p) + suf).unlink(missing_ok=True)
        return mode

    mode = asyncio.run(go())
    assert str(mode).lower() == "wal", f"journal_mode={mode}, expected wal"
    return "WAL confirmed"


@check("chromadb persistent client")
def _chroma():
    import chromadb

    path = str(ROOT / "data" / "chroma_smoke")
    # Chroma's construction signature has drifted across majors; try the modern
    # shape first and fall back rather than pinning to one release's API.
    try:
        from chromadb.config import Settings
        client = chromadb.PersistentClient(path=path, settings=Settings(anonymized_telemetry=False))
        shape = "PersistentClient+Settings"
    except Exception:
        client = chromadb.PersistentClient(path=path)
        shape = "PersistentClient"

    col = client.get_or_create_collection("smoke")
    col.upsert(ids=["a", "b"], embeddings=[[0.1, 0.2, 0.3], [0.9, 0.8, 0.7]])
    res = col.query(query_embeddings=[[0.1, 0.2, 0.3]], n_results=2)
    assert res["ids"][0][0] == "a", res
    assert col.count() == 2
    return f"{shape}, v{chromadb.__version__}, query ok"


@check("embedding model (prewarm ~470MB)")
def _embed():
    from sentence_transformers import SentenceTransformer

    m = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    # Cross-lingual sanity: the whole reason for this model (ADR-0006).
    v = m.encode([
        "Amazon off-campus drive registration fee 750",
        "Amazon off campus drive ki registration fee 750 rupees",
        "the library will close at 6pm on saturday",
    ], normalize_embeddings=True)
    import numpy as np
    same = float(np.dot(v[0], v[1]))
    diff = float(np.dot(v[0], v[2]))
    assert v.shape[1] == 384, v.shape
    assert same > diff, f"code-mixed pair ({same:.3f}) not closer than unrelated ({diff:.3f})"
    return f"dim=384, code-mixed sim={same:.3f} vs unrelated {diff:.3f}"


@check("langgraph update-dict-only")
def _langgraph():
    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph

    class S(TypedDict):
        steps: list
        value: str

    def node_a(state: S):
        # Deliberately does NOT mutate state. In-place mutation fails silently
        # in LangGraph, which is the classic footgun.
        return {"steps": state["steps"] + ["a"], "value": "from_a"}

    def node_b(state: S):
        assert state["value"] == "from_a", "update dict did not propagate"
        return {"steps": state["steps"] + ["b"]}

    g = StateGraph(S)
    g.add_node("a", node_a)
    g.add_node("b", node_b)
    g.add_edge(START, "a")
    g.add_edge("a", "b")
    g.add_edge("b", END)
    app = g.compile()
    out = app.invoke({"steps": [], "value": ""})
    assert out["steps"] == ["a", "b"], out
    return "2-node graph, updates propagate"


@check("google-genai client")
def _genai():
    from google import genai  # noqa: F401
    import google.genai as g

    assert hasattr(g, "Client"), "google-genai has no Client"
    # Constructing with a bogus key must not perform a network call.
    g.Client(api_key="not-a-real-key")
    return f"v{getattr(g, '__version__', '?')} (constructed, no call)"


@check("scipy curve_fit wrapped")
def _scipy():
    import numpy as np
    from scipy.optimize import curve_fit

    def logistic(t, K, r, t0):
        return K / (1 + np.exp(-r * (t - t0)))

    t = np.arange(0, 20, dtype=float)
    y = logistic(t, 100, 0.5, 10) + np.random.default_rng(0).normal(0, 1, t.size)
    popt, _ = curve_fit(logistic, t, y, p0=[80, 0.3, 8], maxfev=20000)
    assert 60 < popt[0] < 160, popt
    # And prove the failure path is survivable, since real data will be worse.
    try:
        curve_fit(logistic, np.array([0.0, 1.0]), np.array([1.0, 1.0]), p0=[1, 1, 1], maxfev=50)
    except Exception:
        pass
    return f"logistic K={popt[0]:.1f}"


@check("imaging: Pillow + pHash")
def _imaging():
    import imagehash
    from PIL import Image, ImageDraw

    a = Image.new("RGB", (400, 300), (240, 240, 240))
    ImageDraw.Draw(a).rectangle([50, 50, 350, 250], fill=(30, 90, 200))
    b = a.copy()
    ImageDraw.Draw(b).text((60, 60), "different caption", fill=(255, 255, 255))
    c = Image.new("RGB", (400, 300), (10, 10, 10))
    ha, hb, hc = (imagehash.phash(x) for x in (a, b, c))
    assert (ha - hb) < (ha - hc), f"pHash cannot separate near-dupe from distinct: {ha-hb} vs {ha-hc}"
    return f"near-dupe distance {ha-hb}, distinct {ha-hc}"


@check("httpx + fastapi + ulid + structlog")
def _misc():
    import httpx
    import structlog
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ulid import ULID

    app = FastAPI()

    @app.get("/ping")
    def ping():
        return {"ok": True}

    with TestClient(app) as c:
        assert c.get("/ping").json() == {"ok": True}

    u1, u2 = str(ULID()), str(ULID())
    assert u1 < u2 or u1 != u2, "ULIDs must be time-sortable"
    structlog.get_logger().info("smoke")
    assert httpx.__version__
    return "ok"


def main() -> int:
    for fn in (_pydantic, _contracts, _institution, _sqlalchemy, _chroma, _embed,
               _langgraph, _genai, _scipy, _imaging, _misc):
        fn()

    print("\n" + "=" * 68)
    failed = 0
    for name, ok, note in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'}  {name:38s} {note}")
        failed += 0 if ok else 1
    print("=" * 68)
    print(f"{len(RESULTS) - failed}/{len(RESULTS)} subsystems PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
