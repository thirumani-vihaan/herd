import type { AppContext } from "../lib/api";

/**
 * The masthead.
 *
 * A record has a header, not a hero section. The ink bar is doing one job:
 * saying, before anything else loads, that this page is an instrument and its
 * whole point is the part below the line.
 */
export default function Masthead({ ctx }: { ctx: AppContext | null }) {
  return (
    <header className="border-b border-ink/15 bg-ink text-paper">
      <div className="mx-auto flex max-w-[1240px] flex-wrap items-end justify-between gap-x-10 gap-y-6 px-6 pb-7 pt-9 sm:px-10">
        <div className="min-w-0">
          <div className="flex items-baseline gap-4">
            <h1 className="font-display text-[3.1rem] leading-[0.85] tracking-tight">
              HERD
            </h1>
            <span className="hidden font-mono text-[10px] uppercase tracking-[0.22em] text-paper/45 sm:block">
              claim · cascade · verdict
            </span>
          </div>
          <p className="mt-3 max-w-lg text-[13.5px] leading-relaxed text-paper/60">
            An immune system for digital scams. It investigates a
            message the way a careful person would — cheapest checks first —
            and stops the moment it can honestly stop.
          </p>
          {ctx?.global_stats && (
            <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-false/30 bg-false/10 px-3 py-1.5 text-[12px] font-medium text-false">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-false opacity-75"></span>
                <span className="relative inline-flex h-2 w-2 rounded-full bg-false"></span>
              </span>
              Live Intercepts: {ctx.global_stats.total_intercepts.toLocaleString()} | Est. Fraud Prevented: ${ctx.global_stats.estimated_fraud_blocked.toLocaleString()}
            </div>
          )}
        </div>

        <dl className="flex flex-wrap gap-x-9 gap-y-3">
          <Stat k="watching" v={ctx?.institution.short_name ?? "—"} />
          <Stat k="tiers" v="4" />
          <Stat k="agents" v={ctx ? String(ctx.agent_count) : "—"} />
          <Stat k="community note by" v="HERD AI" />
        </dl>
      </div>
    </header>
  );
}

function Stat({ k, v }: { k: string; v: string }) {
  return (
    <div className="border-l border-paper/15 pl-4">
      <dt className="font-mono text-[9.5px] uppercase tracking-[0.16em] text-paper/40">
        {k}
      </dt>
      <dd className="font-mono mt-1.5 text-[15px] text-paper">{v}</dd>
    </div>
  );
}
