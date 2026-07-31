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
    <header className="border-b border-rule bg-card">
      <div className="mx-auto flex max-w-[1240px] flex-wrap items-center justify-between gap-x-10 gap-y-5 px-6 py-6 sm:px-10">
        <div className="min-w-0">
          <div className="flex items-baseline gap-4">
            <h1 className="text-[1.55rem] font-semibold leading-none tracking-[-0.04em]">
              HERD
            </h1>
            <span className="hidden text-[11px] text-faint sm:block">
              claim · cascade · verdict
            </span>
          </div>
          <p className="mt-2 max-w-lg text-[13px] leading-relaxed text-muted">
            An immune system for campus misinformation. It investigates a
            message the way a careful person would — cheapest checks first —
            and stops the moment it can honestly stop.
          </p>
        </div>

        <dl className="flex flex-wrap gap-x-9 gap-y-3">
          <Stat k="watching" v={ctx?.institution.short_name ?? "—"} />
          <Stat k="tiers" v="4" />
          <Stat k="agents" v={ctx ? String(ctx.agent_count) : "—"} />
          <Stat k="verdict written by an llm" v="no" />
        </dl>
      </div>
    </header>
  );
}

function Stat({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-[0.08em] text-faint">
        {k}
      </dt>
      <dd className="mt-1 text-[13px] font-medium text-ink">{v}</dd>
    </div>
  );
}
