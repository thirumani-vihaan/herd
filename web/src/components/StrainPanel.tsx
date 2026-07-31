import type { Investigation } from "../lib/api";

const LEVEL: Record<string, { bars: number; word: string; note: string }> = {
  low: {
    bars: 1,
    word: "Contained",
    note: "Few reports of this exact message so far.",
  },
  medium: {
    bars: 2,
    word: "Moving",
    note: "Reports are arriving faster than a one-off would.",
  },
  high: {
    bars: 3,
    word: "Spreading",
    note: "Enough reports in a short window to treat this as circulating.",
  },
};

/**
 * The strain: what the system remembers about this message across everyone who
 * reported it. This is the part a per-message classifier cannot have.
 */
export default function StrainPanel({ data }: { data: Investigation }) {
  const s = data.strain;
  const level = LEVEL[s.velocity] ?? LEVEL.low;
  const repeat = s.report_count > 1;

  return (
    <section className="border border-rule bg-card px-7 py-6 shadow-plate">
      <div className="flex items-baseline justify-between">
        <h3 className="font-display text-[19px] tracking-tight">Strain</h3>
        <span className="num text-[11px] text-faint">{s.id}</span>
      </div>

      <p className="mt-3 text-[14.5px] leading-relaxed text-ink">
        {repeat ? (
          <>
            This message has been reported{" "}
            <span className="num font-medium">{s.report_count}</span> times.
            They were recognised as the same thing, so it was investigated once.
          </>
        ) : (
          <>First time this message has been seen here.</>
        )}
      </p>

      <div className="mt-5 flex items-center gap-4">
        <div className="flex items-end gap-1" aria-hidden>
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="w-3 bg-ink transition-all"
              style={{
                height: `${8 + i * 7}px`,
                opacity: i < level.bars ? 1 : 0.14,
              }}
            />
          ))}
        </div>
        <div>
          <p className="text-[14px] font-medium leading-none text-ink">
            {level.word}
          </p>
          <p className="mt-1 text-[12.5px] leading-snug text-faint">
            {level.note}
          </p>
        </div>
      </div>

      <p className="mt-5 border-t border-rulesoft pt-4 text-[12px] leading-relaxed text-faint">
        Counted from real reports that were stored, never from an assumption
        about how far something has travelled.
      </p>
    </section>
  );
}
