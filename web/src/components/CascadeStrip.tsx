import type { Investigation } from "../lib/api";
import { TIER_BLURB, TIER_NAMES } from "../lib/api";
import { look } from "../lib/verdict";

/**
 * The cascade, shown as something that was *spent* rather than something that
 * ran. Tiers the investigation never had to buy are drawn as unspent, because
 * not needing them is the point of the design.
 */
export default function CascadeStrip({ data }: { data: Investigation }) {
  const L = look(data.verdict);
  const byTier = new Map(data.trace.map((t) => [t.tier, t]));

  return (
    <section className="relative overflow-hidden border-2 border-rule bg-card shadow-plate animate-rise" style={{ animationDelay: '0.1s' }}>
      <div className="absolute inset-0 pointer-events-none overflow-hidden mix-blend-multiply opacity-20">
        <div className="h-24 w-full bg-gradient-to-b from-transparent via-[#8B8779] to-transparent blur-md animate-scan"></div>
      </div>
      <header className="flex items-baseline justify-between border-b border-rule px-7 py-5">
        <h3 className="font-display text-[19px] tracking-tight">
          The cascade
        </h3>
        <p className="label">
          {data.tiers_skipped > 0 
            ? `${data.tiers_skipped} tier${data.tiers_skipped > 1 ? 's' : ''} skipped` 
            : "0 tiers skipped"} · cheapest evidence first
        </p>
      </header>

      <ol>
        {[0, 1, 2, 3].map((tier) => {
          const t = byTier.get(tier);
          const spent = Boolean(t);

          return (
            <li
              key={tier}
              className={`grid grid-cols-[3.2rem_1fr] gap-x-5 border-b border-rulesoft px-7 py-6 last:border-0 animate-fade-in transition-colors hover:bg-rulesoft/30 ${
                spent ? "animate-pulse-soft" : "opacity-45"
              }`}
              style={{ animationDelay: `${0.2 + tier * 0.15}s` }}
            >
              <div className="pt-[2px]">
                <div
                  className="num flex h-9 w-9 items-center justify-center border text-[13px]"
                  style={{
                    borderColor: spent ? L.hex : "#E5E2D6",
                    color: spent ? L.hex : "#8C887A",
                  }}
                >
                  {tier}
                </div>
              </div>

              <div className="min-w-0">
                <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
                  <h4 className="text-[15px] font-medium tracking-tight">
                    {TIER_NAMES[tier]}
                  </h4>
                  {spent ? (
                    <p className="label flex items-center gap-1.5">
                      <span className="text-ink font-mono">{t!.elapsed_ms} ms</span> ·
                      belief {t!.posterior_after.toFixed(3)} ·{" "}
                      <span className="animate-stamp-in text-xs font-bold" style={{ color: L.hex, animationDelay: `${0.4 + tier * 0.15}s` }}>
                        {t!.label_after}
                      </span>
                      {t!.exited && " · exited here"}
                    </p>
                  ) : (
                    <p className="label">not purchased</p>
                  )}
                </div>

                <p className="mt-1.5 max-w-2xl text-[13.5px] leading-relaxed text-muted">
                  {TIER_BLURB[tier]}
                </p>

                {spent && (
                  <div className="mt-3 flex flex-wrap gap-1.5 animate-type-reveal" style={{ animationDelay: `${0.3 + tier * 0.15}s` }}>
                    {t!.agents_run.map((a) => (
                      <span
                        key={a}
                        className="num border border-rule px-2 py-[3px] text-[11px] text-ink"
                      >
                        {a}
                      </span>
                    ))}
                    {t!.agents_skipped.map((a) => (
                      <span
                        key={a}
                        className="num border border-dashed border-rule px-2 py-[3px] text-[11px] text-faint line-through decoration-faint/50"
                        title="did not apply to this claim"
                      >
                        {a}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
