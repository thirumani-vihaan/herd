import { useEffect, useRef, useState } from "react";
import {
  investigate,
  loadContext,
  type AppContext,
  type Investigation,
} from "./lib/api";
import Masthead from "./components/Masthead";
import ReportSlip from "./components/ReportSlip";
import VerdictPlate from "./components/VerdictPlate";
import CascadeStrip from "./components/CascadeStrip";
import EvidenceLedger from "./components/EvidenceLedger";
import StrainPanel from "./components/StrainPanel";
import FeedPanel, { type FeedEntry } from "./components/FeedPanel";

export default function App() {
  const [showSplash, setShowSplash] = useState(true);
  const [data, setData] = useState<Investigation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ctx, setCtx] = useState<AppContext | null>(null);
  const [feed, setFeed] = useState<FeedEntry[]>(() => {
    try {
      const stored = localStorage.getItem("herd_feed");
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });
  const seq = useRef(0);

  useEffect(() => {
    loadContext()
      .then(setCtx)
      .catch(() => setCtx(null));
  }, []);

  useEffect(() => {
    localStorage.setItem("herd_feed", JSON.stringify(feed));
  }, [feed]);

  useEffect(() => {
    const timer = setTimeout(() => setShowSplash(false), 3000);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    const baseUrl = import.meta.env.VITE_API_URL || window.location.origin;
    const wsUrl = baseUrl.replace(/^http/, "ws") + "/ws";
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.verdict && payload.strain) {
          setFeed((prev) => {
            // Prevent duplicates if local investigate() already added it
            if (prev.some(p => p.strainId === payload.strain.id && Math.abs(p.at - Date.now()) < 5000)) return prev;
            return [
              {
                seq: (seq.current += 1),
                at: Date.now(),
                verdict: payload.verdict,
                claim: payload.claim?.text || "New report received",
                strainId: payload.strain.id,
                count: payload.strain.report_count,
                velocity: payload.strain.velocity,
              },
              ...prev,
            ].slice(0, 10);
          });
        }
      } catch (e) {
        console.error("WebSocket message error:", e);
      }
    };

    return () => ws.close();
  }, []);

  async function run(v: {
    text: string;
    isForwarded: boolean;
    isFrequentlyForwarded: boolean;
    image?: File | null;
  }) {
    setBusy(true);
    setData(null);
    setError(null);
    try {
      const res = await investigate({
        ...v,
        reporterHash: `web_${Math.random().toString(36).slice(2, 10)}`,
      });
      if (res.result) {
        const r = res.result;
        setData(r);
        setFeed((prev) =>
          [
            {
              seq: (seq.current += 1),
              at: Date.now(),
              verdict: r.verdict,
              claim: r.claim?.text || v.text,
              strainId: r.strain.id,
              count: r.strain.report_count,
              velocity: r.strain.velocity,
            },
            ...prev,
          ].slice(0, 10)
        );
      } else setError("The investigation returned no result.");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not reach the investigator."
      );
    } finally {
      setBusy(false);
    }
  }

  if (showSplash) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-paper text-ink transition-opacity duration-500">
        <div className="relative flex flex-col items-center">
          <div className="absolute -inset-10 animate-scan mix-blend-multiply opacity-[0.03] bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] pointer-events-none" style={{ backgroundSize: '100px 100px' }}></div>
          <h1 className="font-display text-[clamp(4rem,10vw,8rem)] tracking-tight flex">
            <span className="animate-slide-left" style={{ animationDelay: '0.1s' }}>H</span>
            <span className="animate-slide-left" style={{ animationDelay: '0.3s' }}>E</span>
            <span className="animate-slide-right" style={{ animationDelay: '0.5s' }}>R</span>
            <span className="animate-slide-right" style={{ animationDelay: '0.7s' }}>D</span>
          </h1>
          <p className="font-mono text-sm tracking-[0.2em] uppercase text-muted mt-2 animate-fade-in" style={{ animationDelay: '0.4s' }}>Immune System</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen animate-fade-in">
      <Masthead ctx={ctx} />

      <main className="mx-auto grid max-w-[1240px] gap-7 px-6 py-11 sm:px-10 lg:grid-cols-[minmax(320px,390px)_1fr] lg:items-start">
        <div className="space-y-6 lg:sticky lg:top-8">
          <ReportSlip onSubmit={run} busy={busy} samples={ctx?.samples ?? []} />
          {data && <StrainPanel data={data} />}
          <FeedPanel entries={feed} />
        </div>

        <div className="space-y-7" aria-live="polite">
          {error && (
            <div className="border border-false/40 bg-card px-7 py-5" role="alert">
              <p className="label text-false">Service Unavailable</p>
              <p className="mt-2 text-[14px] text-ink">{error}</p>
              <p className="mt-2 text-[13px] text-muted">
                Our global network is currently unreachable. Please check your internet connection or try again in a few moments.
              </p>
            </div>
          )}

          {busy && !data && <Working />}

          {!busy && !data && !error && <Standby />}

          {data && (
            <>
              <VerdictPlate data={data} />
              <CascadeStrip data={data} />
              <EvidenceLedger data={data} />
            </>
          )}
        </div>
      </main>

      <footer className="mt-6 border-t border-rule">
        <div className="mx-auto max-w-[1240px] px-6 py-7 sm:px-10">
          <p className="max-w-2xl text-[12.5px] leading-relaxed text-faint">
            Every verdict on this page was produced by the same calibrated
            pipeline, offline-first, with no verdict written by a language
            model. The investigation analysis and prose are generated in real-time by <strong className="text-ink font-semibold">Featherless.ai</strong>; the underlying mathematical judgement is not.
          </p>
        </div>
      </footer>
    </div>
  );
}

function Working() {
  return (
    <section 
      className="animate-rise border-2 border-rule bg-card px-8 py-24 text-center shadow-plate relative overflow-hidden"
      aria-busy="true"
      aria-live="assertive"
    >
      <div className="absolute inset-0 pointer-events-none mix-blend-multiply opacity-[0.08]">
        <div className="h-full w-full bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] animate-scan" style={{ backgroundSize: '100px 100px' }}></div>
      </div>
      <div className="relative mx-auto flex w-fit items-end gap-3" aria-hidden>
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="flex flex-col items-center gap-2">
            <span
              className="w-10 border border-ink bg-ink/10 animate-pulse-soft"
              style={{
                height: `${24 + i * 16}px`,
                animationDelay: `${i * 150}ms`,
              }}
            />
            <span className="font-mono text-[10px] tracking-widest text-faint animate-fade-in" style={{ animationDelay: `${i * 150}ms` }}>T{i}</span>
          </div>
        ))}
      </div>
      <h2 className="relative mt-8 font-display text-3xl text-ink tracking-tight animate-pulse-soft">Consulting the cascade...</h2>
      <p className="relative mx-auto mt-3 max-w-sm text-[14px] leading-relaxed text-muted">
        Reading the wording, then the infrastructure, then the official record —
        stopping at the first tier that settles it.
      </p>
    </section>
  );
}

function Standby() {
  const steps = [
    ["0", "Reads the message", "Pressure, payment shape, template lineage. Costs nothing."],
    ["1", "Checks the infrastructure", "Domains, links and contact details against what is publicly published."],
    ["2", "Looks at the official record", "The only tier allowed to confirm that something is genuinely official (Bypassed in Global Mode)."],
    ["3", "Searches the open web", "Bought only when everything cheaper had to abstain."],
  ];

  return (
    <section className="border border-rule bg-card px-8 py-12 shadow-plate sm:px-14 sm:py-14">
      <p className="label">standby</p>
      <h2 className="font-display mt-4 max-w-2xl text-[clamp(2rem,4vw,2.9rem)] leading-[1.05] tracking-tight">
        It does not guess, and it will tell you when it doesn't know.
      </h2>
      <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-muted">
        Paste a message on the left. You will see every agent that looked at it,
        what each one found, what it cited, and exactly how far belief moved —
        including the tiers that never had to run.
      </p>

      <ol className="mt-10 space-y-0">
        {steps.map(([n, title, body]) => (
          <li
            key={n}
            className="grid grid-cols-[2.6rem_1fr] gap-x-4 border-t border-rulesoft py-5 transition-colors hover:bg-rulesoft/50 px-4 -mx-4 rounded"
          >
            <span className="num text-[12px] text-faint">TIER {n}</span>
            <div>
              <p className="text-[14.5px] font-medium tracking-tight">{title}</p>
              <p className="mt-1 text-[13.5px] leading-relaxed text-muted">
                {body}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
