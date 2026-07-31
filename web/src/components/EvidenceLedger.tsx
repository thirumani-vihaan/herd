import type { EvidenceItem, Investigation } from "../lib/api";

const SIGNAL_COLOR: Record<string, string> = {
  contradicts: "#C0322A",
  supports: "#0E7150",
  neutral: "#8E9199",
};

const SIGNAL_WORD: Record<string, string> = {
  contradicts: "against",
  supports: "for",
  neutral: "no opinion",
};

/**
 * Every agent that spoke, and every agent that could not — including the ones
 * that found nothing. Showing the silent ones is deliberate: an interface that
 * only lists hits is an interface you cannot audit.
 */
export default function EvidenceLedger({ data }: { data: Investigation }) {
  const spoke = data.evidence.filter(
    (e) => e.status === "ok" && e.signal !== "neutral"
  );
  const silent = data.evidence.filter(
    (e) => e.status !== "ok" || e.signal === "neutral"
  );
  const citations = spoke.reduce((n, e) => n + e.sources.length, 0);

  return (
    <section className="section">
      <header className="flex items-baseline justify-between pb-4">
        <h3 className="text-[15px] font-semibold tracking-tight">Evidence</h3>
        <p className="text-[11px] text-faint">
          {spoke.length} spoke · {citations} citation
          {citations === 1 ? "" : "s"} · {silent.length} silent
        </p>
      </header>

      <ul>
        {spoke.map((e) => (
          <Row key={e.agent} e={e} />
        ))}
      </ul>

      {silent.length > 0 && (
        <div className="border-t border-rulesoft pt-5">
          <p className="label">silent</p>
          <ul className="mt-3 space-y-1.5">
            {silent.map((e) => (
              <li
                key={e.agent}
                className="flex flex-wrap items-baseline gap-x-3 text-[13px] text-faint"
              >
                <span className="num text-ink/60">{e.agent}</span>
                <span>
                  {e.status !== "ok"
                    ? e.error
                      ? `unavailable — ${e.error}`
                      : "unavailable"
                    : e.finding || "found nothing either way"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function Row({ e }: { e: EvidenceItem }) {
  const color = SIGNAL_COLOR[e.signal] ?? "#8E9199";

  return (
    <li className="border-t border-rulesoft py-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <div className="flex items-baseline gap-3">
          <span
            className="num text-[15px] font-medium"
            style={{ color }}
            aria-hidden
          >
            {e.signal === "supports" ? "+" : e.signal === "contradicts" ? "−" : "·"}
          </span>
          <h4 className="text-[14px] font-medium text-ink">{e.agent}</h4>
          <span className="label">
            tier {e.tier} · {SIGNAL_WORD[e.signal] ?? e.signal}
          </span>
        </div>
        <span className="label">{e.elapsed_ms} ms</span>
      </div>

      <p className="mt-2 max-w-3xl text-[14.5px] leading-relaxed text-ink">
        {e.finding}
      </p>

      {/* Strength, drawn rather than described. */}
      <div className="mt-3 flex items-center gap-3">
        <div className="h-[3px] w-40 bg-rulesoft">
          <div
            className="h-full origin-left animate-sweep"
            style={{
              width: `${Math.min(100, Math.max(0, e.strength * 100))}%`,
              background: color,
            }}
          />
        </div>
        <span className="label">strength {e.strength.toFixed(2)}</span>
      </div>

      {e.sources.length > 0 && (
        <ul className="mt-4 space-y-1.5 border-l border-rule pl-4">
          {e.sources.map((s, i) => (
            <li key={i} className="text-[12.5px] leading-snug">
              <a
                href={s.url}
                target="_blank"
                rel="noreferrer"
                className="text-muted underline decoration-rule underline-offset-2 hover:text-ink hover:decoration-ink"
              >
                {s.title || s.url}
              </a>
              {s.excerpt && (
                <span className="text-faint"> — {s.excerpt}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}
