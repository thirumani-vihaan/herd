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
    <section className="section">
      <header className="flex items-baseline justify-between pb-4">
        <h3 className="text-[15px] font-semibold tracking-tight">
          The cascade
        </h3>
        <p className="text-[11px] text-faint">Cheapest evidence first</p>
      </header>

      <ol>
        {[0, 1, 2, 3].map((tier) => {
          const t = byTier.get(tier);
          const spent = Boolean(t);

          return (
            <li
              key={tier}
              className={`grid grid-cols-[2.4rem_1fr] gap-x-5 border-t border-rulesoft py-5 ${
                spent ? "" : "opacity-40"
              }`}
            >
              <div className="pt-[3px]">
                <div
                  className="num text-[12px]"
                  style={{ color: spent ? L.hex : "#8E9199" }}
                >
                  T{tier}
                </div>
              </div>

              <div className="min-w-0">
                <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
                  <h4 className="text-[15px] font-medium tracking-tight">
                    {TIER_NAMES[tier]}
                  </h4>
                  {spent ? (
                    <p className="label">
                      <span className="text-ink">{t!.elapsed_ms} ms</span> ·
                      belief {t!.posterior_after.toFixed(3)} ·{" "}
                      {t!.label_after}
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
                  <div className="mt-2.5 flex flex-wrap gap-2">
                    {t!.agents_run.map((a) => (
                      <span
                        key={a}
                        className="rounded bg-rulesoft px-2 py-1 font-mono text-[10.5px] text-muted"
                      >
                        {a}
                      </span>
                    ))}
                    {t!.agents_skipped.map((a) => (
                      <span
                        key={a}
                        className="rounded bg-rulesoft px-2 py-1 font-mono text-[10.5px] text-faint line-through decoration-faint/50"
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
