import { useEffect, useState } from "react";
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

export default function App() {
  const [data, setData] = useState<Investigation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ctx, setCtx] = useState<AppContext | null>(null);

  useEffect(() => {
    loadContext()
      .then(setCtx)
      .catch(() => setCtx(null));
  }, []);

  async function run(v: {
    text: string;
    isForwarded: boolean;
    isFrequentlyForwarded: boolean;
  }) {
    setBusy(true);
    setError(null);
    try {
      const res = await investigate({
        ...v,
        reporterHash: `web_${Math.random().toString(36).slice(2, 10)}`,
      });
      if (res.result) setData(res.result);
      else setError("The investigation returned no result.");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not reach the investigator."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen">
      <Masthead ctx={ctx} />

      <main className="mx-auto grid max-w-[1240px] gap-7 px-6 py-11 sm:px-10 lg:grid-cols-[minmax(320px,390px)_1fr] lg:items-start">
        <div className="space-y-6 lg:sticky lg:top-8">
          <ReportSlip onSubmit={run} busy={busy} samples={ctx?.samples ?? []} />
          {data && <StrainPanel data={data} />}
        </div>

        <div className="space-y-7">
          {error && (
            <div className="border border-false/40 bg-card px-7 py-5">
              <p className="label text-false">could not investigate</p>
              <p className="mt-2 text-[14px] text-ink">{error}</p>
              <p className="mt-2 text-[13px] text-muted">
                Start the service with{" "}
                <code className="num text-[12px]">
                  venv\Scripts\python.exe -m uvicorn app.api.ingest:app
                </code>
                .
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
            model. The prose is generated; the judgement is not.
          </p>
        </div>
      </footer>
    </div>
  );
}

function Working() {
  return (
    <section className="animate-rise border border-rule bg-card px-8 py-20 text-center shadow-plate">
      <div className="mx-auto flex w-fit items-end gap-1.5" aria-hidden>
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className="w-2 animate-pulse bg-ink"
            style={{
              height: `${10 + i * 6}px`,
              animationDelay: `${i * 140}ms`,
            }}
          />
        ))}
      </div>
      <p className="mt-6 text-[14px] text-ink">Working through the tiers</p>
      <p className="mx-auto mt-2 max-w-sm text-[13px] leading-relaxed text-muted">
        Reading the wording, then the infrastructure, then the official record —
        stopping at the first tier that settles it.
      </p>
    </section>
  );
}

function Standby() {
  const steps = [
    ["0", "Reads the message", "Pressure, payment shape, template lineage. Costs nothing."],
    ["1", "Checks the infrastructure", "Domains, links and contact details against what the campus publishes."],
    ["2", "Looks at the official record", "The only tier allowed to confirm that something is genuine."],
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
            className="grid grid-cols-[2.6rem_1fr] gap-x-4 border-t border-rulesoft py-5"
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
