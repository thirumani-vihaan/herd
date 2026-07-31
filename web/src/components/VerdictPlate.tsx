import type { Investigation } from "../lib/api";
import { useState } from "react";
import { look } from "../lib/verdict";
import BeliefAxis from "./BeliefAxis";

export default function VerdictPlate({ data }: { data: Investigation }) {
  const L = look(data.verdict);
  const abstained =
    data.verdict === "UNVERIFIED" || data.verdict === "OUT_OF_SCOPE";

  const isAdmin = typeof window !== 'undefined' && window.location.search.includes('admin=true');
  const [overrideBusy, setOverrideBusy] = useState(false);

  async function handleOverride(label: string) {
    if (!confirm(`Are you sure you want to forcefully override this verdict to ${label}?`)) return;
    setOverrideBusy(true);
    try {
      const API_URL = import.meta.env.VITE_API_URL || "";
      const res = await fetch(`${API_URL}/override/${data.strain.id}?label=${label}&secret=admin_secret`, { method: "POST" });
      if (res.ok) {
        alert("Verdict overridden successfully! The Live Feed will update shortly.");
      } else {
        alert("Failed to override verdict. Check server logs.");
      }
    } catch (e) {
      alert("Error overriding verdict");
    }
    setOverrideBusy(false);
  }

  return (
    <section
      className="relative animate-rise border-x border-b border-rule bg-card shadow-plate"
      style={{ borderTop: `6px double ${L.hex}` }}
    >
      <div className="absolute inset-0 pointer-events-none overflow-hidden mix-blend-multiply opacity-10">
        <div className="h-16 w-full bg-gradient-to-b from-transparent via-[#8B8779] to-transparent blur-md animate-scan" style={{ animationDelay: "1.5s" }}></div>
      </div>
      <div className="px-8 py-10 sm:px-14 sm:py-12">
      <div className="flex items-start justify-between gap-8">
        <div className="min-w-0">
          <p className="label">the verdict</p>
          <h2
            className="font-display mt-3 text-[clamp(3.2rem,8.5vw,6rem)] leading-[0.86] tracking-tight animate-stamp-in uppercase"
            style={{ color: L.hex }}
          >
            {L.plain}
          </h2>
          <p className="mt-5 max-w-xl text-[15.5px] leading-relaxed text-muted">
            {L.meaning}
          </p>
        </div>

        <dl className="hidden shrink-0 gap-y-4 text-right sm:grid">
          <div className="print:hidden mb-2">
            <button 
              onClick={() => window.print()} 
              className="ml-auto text-[11px] uppercase tracking-wider font-mono border border-rule px-3 py-1 hover:bg-rule/10 transition-colors text-ink/70 flex items-center gap-2"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="6 9 6 2 18 2 18 9"></polyline>
                <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path>
                <rect x="6" y="14" width="12" height="8"></rect>
              </svg>
              Print Dossier
            </button>
          </div>
          <div>
            <dt className="label">label</dt>
            <dd className="num text-[15px] text-ink">{data.verdict}</dd>
          </div>
          <div>
            <dt className="label">investigated in</dt>
            <dd className="num text-[15px] text-ink">
              {data.elapsed_ms} ms <span className="text-faint ml-1">· tier {data.highest_tier_reached}</span>
            </dd>
          </div>
          <div>
            <dt className="label">claim type</dt>
            <dd className="num text-[15px] text-ink capitalize">
              {data.claim?.type || "Unknown"} <span className="uppercase text-faint ml-1">· {data.claim?.language || "UNK"}</span>
            </dd>
          </div>
          {isAdmin && (
            <div className="mt-2 border-t border-rulesoft pt-2">
              <dt className="label text-false mb-1">Admin Override</dt>
              <dd className="flex gap-2 justify-end">
                <button onClick={() => handleOverride('FALSE')} disabled={overrideBusy} className="px-2 py-1 bg-false text-paper text-xs rounded hover:opacity-80 disabled:opacity-50">FALSE</button>
                <button onClick={() => handleOverride('TRUE')} disabled={overrideBusy} className="px-2 py-1 bg-true text-paper text-xs rounded hover:opacity-80 disabled:opacity-50">TRUE</button>
              </dd>
            </div>
          )}
        </dl>
      </div>

      {data.summary && (
        <p
          className="mt-8 border-l-2 pl-6 text-[17.5px] leading-[1.6] text-ink"
          style={{ borderColor: L.hex }}
        >
          {data.summary}
        </p>
      )}

      <BeliefAxis data={data} />

      {(abstained || data.withheld_confirmation || data.deadline_exceeded || data.withheld_for_standing || data.clamped || data.claim?.degraded) && (
        <div className="mt-8 space-y-3 border-t border-rulesoft pt-6">
          {abstained && (
            <Note title="Abstaining is a result, not a failure">
              Nothing reached the bar in either direction, so the system is
              saying nothing rather than guessing. Being wrong about a real
              notice costs more than being silent about a fake one.
            </Note>
          )}
          {data.withheld_confirmation && (
            <Note title="Confirmation withheld">
              The arithmetic pointed at genuine, but no agent found this on a
              source the institution controls. "No fraud rule fired" is not
              evidence of authenticity, so it was not confirmed.
            </Note>
          )}
          {data.deadline_exceeded && (
            <Note title="Deadline reached">
              The cascade ran out of its time budget and returned what it had.
              The verdict reflects the evidence actually gathered.
            </Note>
          )}
          {data.withheld_for_standing && (
            <Note title="Insufficient standing">
              This institution is not the authoritative source for this claim, so the system downgraded the verdict to avoid confirming third-party rumors.
            </Note>
          )}
          {data.clamped && (
            <Note title="Confidence clamped">
              Mathematical certainty hit a safety boundary. The probability was clamped to avoid declaring absolute truth about an uncertain world.
            </Note>
          )}
          {data.claim?.degraded && (
            <Note title="Degraded claim">
              The language model failed to extract the claim natively. The system fell back to raw heuristics to avoid dropping the report.
            </Note>
          )}
        </div>
      )}
      </div>
    </section>
  );
}

function Note({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-4 animate-fade-in" style={{ animationDelay: '0.6s' }}>
      <span className="mt-[7px] h-px w-6 shrink-0 bg-faint" />
      <p className="text-[13.5px] leading-relaxed text-muted">
        <span className="font-medium text-ink">{title}.</span> {children}
      </p>
    </div>
  );
}
