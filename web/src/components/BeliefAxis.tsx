import type { Investigation } from "../lib/api";
import { look } from "../lib/verdict";
import { TIER_NAMES } from "../lib/api";

/**
 * The descent.
 *
 * One drawing that answers the two questions a wrapper cannot: *how far* did
 * belief move, and *what did each step cost to buy*. The horizontal axis is
 * the entire decision space, banded. The vertical axis is the cascade going
 * deeper. The line is the investigation itself, falling through the tiers and
 * sliding toward a verdict.
 *
 * Flat segments matter as much as steep ones: a tier that ran and moved
 * nothing is a tier that honestly found nothing.
 */
export default function BeliefAxis({ data }: { data: Investigation }) {
  const { bands, prior, posterior_false, trace } = data;
  const L = look(data.verdict);

  const rows = [
    { key: "prior", label: "PRIOR", note: "before evidence", p: prior, ms: null as number | null },
    ...trace.map((t) => ({
      key: `t${t.tier}`,
      label: `TIER ${t.tier}`,
      note: (TIER_NAMES[t.tier] ?? "").toLowerCase(),
      p: t.posterior_after,
      ms: t.elapsed_ms,
    })),
  ];

  const W = 720;
  const padL = 104;
  const padR = 58;
  const top = 42;
  const rowH = 44;
  const axisY = top + rows.length * rowH + 16;
  const H = axisY + 46;

  // The axis is in log-odds, not probability.
  //
  // This is not a stylistic choice. The aggregator adds evidence in log-odds —
  // one unit of agent strength is worth a fixed number of them — so log-odds is
  // the only scale on which each tier's contribution is drawn at its true size.
  // On a linear probability axis, 0.94 → 0.998 looks like a rounding error when
  // it is in fact more evidence than everything before it.
  const LO = -5;
  const HI = 7;
  const logit = (p: number) => {
    const c = Math.min(Math.max(p, 1e-6), 1 - 1e-6);
    return Math.log(c / (1 - c));
  };
  const x = (p: number) => {
    const t = (Math.min(Math.max(logit(p), LO), HI) - LO) / (HI - LO);
    return padL + t * (W - padL - padR);
  };

  const segments = [
    { from: 0, to: bands.unverified_above, hex: "#14624A", name: "confirmed" },
    { from: bands.unverified_above, to: bands.misleading_above, hex: "#55524A", name: "no claim" },
    { from: bands.misleading_above, to: bands.false_above, hex: "#A56A00", name: "distorted" },
    { from: bands.false_above, to: 1, hex: "#A32017", name: "fabricated" },
  ];

  const landed = segments.find(
    (s) => posterior_false >= s.from && posterior_false <= s.to
  );

  return (
    <figure className="mt-9">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full overflow-visible"
        role="img"
        aria-label={`Belief moved from a prior of ${prior} to ${posterior_false} across ${trace.length} tiers`}
      >
        {/* the decision space, standing behind everything */}
        {segments.map((s) => (
          <rect
            key={`zone-${s.name}`}
            x={x(s.from)}
            y={top - 14}
            width={x(s.to) - x(s.from)}
            height={axisY - top + 14}
            fill={s.hex}
            opacity={landed && landed.name === s.name ? 0.075 : 0.028}
          />
        ))}
        {segments.slice(1).map((s) => (
          <line
            key={`edge-${s.name}`}
            x1={x(s.from)}
            x2={x(s.from)}
            y1={top - 14}
            y2={axisY + 6}
            stroke="#12110C"
            strokeWidth="1"
            opacity="0.09"
          />
        ))}
        {[0.01, 0.05, 0.2, 0.5, 0.8, 0.95, 0.99, 0.998].map((v) => (
          <g key={`tickmark-${v}`}>
            <line
              x1={x(v)}
              x2={x(v)}
              y1={axisY - 3}
              y2={axisY + 1}
              stroke="#12110C"
              strokeWidth="1"
              opacity="0.25"
            />
            <text
              x={x(v)}
              y={axisY + 36}
              textAnchor="middle"
              className="font-mono"
              fontSize="8.5"
              fill="#BEB9A9"
            >
              {v}
            </text>
          </g>
        ))}

        {/* rows: one per step the investigation actually took */}
        {rows.map((r, i) => {
          const y = top + i * rowH;
          const prev = i > 0 ? rows[i - 1] : null;
          const delta = prev ? r.p - prev.p : 0;
          const moved = Math.abs(delta) >= 0.001;
          const isPrior = i === 0;
          return (
            <g key={r.key}>
              <line
                x1={padL}
                x2={W - padR}
                y1={y}
                y2={y}
                stroke="#12110C"
                strokeWidth="1"
                opacity="0.05"
              />
              <text
                x={padL - 14}
                y={y + 4}
                textAnchor="end"
                className="font-mono"
                fontSize="10.5"
                letterSpacing="1.1"
                fill={isPrior ? "#8B8779" : "#12110C"}
              >
                {r.label}
              </text>
              <text
                x={padL - 14}
                y={y + 17}
                textAnchor="end"
                className="font-mono"
                fontSize="9"
                letterSpacing="0.6"
                fill="#8B8779"
              >
                {r.note}
              </text>

              {/* the value this step arrived at */}
              <text
                x={W - padR + 12}
                y={y + 4}
                className="font-mono"
                fontSize="11"
                fill={moved || isPrior ? "#12110C" : "#8B8779"}
              >
                {r.p.toFixed(3)}
              </text>

              {/* what the step bought */}
              {prev && (
                <text
                  x={x(r.p) + (delta >= 0 ? -10 : 10)}
                  y={y - 9}
                  textAnchor={delta >= 0 ? "end" : "start"}
                  className="font-mono"
                  fontSize="9.5"
                  fill={moved ? L.hex : "#8B8779"}
                  opacity={moved ? 0.9 : 0.6}
                >
                  {moved
                    ? `${delta > 0 ? "+" : "−"}${Math.abs(delta).toFixed(3)}`
                    : "no change"}
                </text>
              )}
            </g>
          );
        })}

        {/* the descent itself */}
        <polyline
          points={rows.map((r, i) => `${x(r.p)},${top + i * rowH}`).join(" ")}
          fill="none"
          stroke={L.hex}
          strokeWidth="1.6"
          opacity="0.55"
        />
        {rows.map((r, i) => {
          const y = top + i * rowH;
          const last = i === rows.length - 1;
          return last ? (
            <circle key={r.key} cx={x(r.p)} cy={y} r="7" fill={L.hex} />
          ) : (
            <circle
              key={r.key}
              cx={x(r.p)}
              cy={y}
              r="4.5"
              fill="#FCFBF8"
              stroke={i === 0 ? "#8B8779" : L.hex}
              strokeWidth="1.6"
              strokeDasharray={i === 0 ? "2 2" : undefined}
            />
          );
        })}

        {/* the needle that lands the verdict on the scale */}
        <line
          x1={x(posterior_false)}
          x2={x(posterior_false)}
          y1={top + (rows.length - 1) * rowH}
          y2={axisY - 4}
          stroke={L.hex}
          strokeWidth="1.8"
        />
        <polygon
          points={`${x(posterior_false)},${axisY + 1} ${x(posterior_false) - 5},${axisY - 7} ${x(posterior_false) + 5},${axisY - 7}`}
          fill={L.hex}
        />

        {/* the scale */}
        {segments.map((s) => (
          <rect
            key={`band-${s.name}`}
            x={x(s.from)}
            y={axisY + 4}
            width={x(s.to) - x(s.from) - 2}
            height="6"
            fill={s.hex}
            opacity={landed && landed.name === s.name ? 0.92 : 0.2}
          />
        ))}
        {segments.map((s) => (
          <text
            key={`name-${s.name}`}
            x={x((s.from + s.to) / 2)}
            y={axisY + 25}
            textAnchor="middle"
            className="font-mono"
            fontSize="9.5"
            letterSpacing="1.1"
            fill={landed && landed.name === s.name ? "#12110C" : "#8B8779"}
          >
            {s.name.toUpperCase()}
          </text>
        ))}
        {[0, 1].map((v) => (
          <text
            key={`tick-${v}`}
            x={v === 0 ? padL : W - padR}
            y={top - 18}
            textAnchor={v === 0 ? "start" : "end"}
            className="font-mono"
            fontSize="8.5"
            letterSpacing="0.8"
            fill="#C4BFAF"
          >
            {v === 0 ? "CERTAINLY GENUINE" : "CERTAINLY FAKE"}
          </text>
        ))}
      </svg>

      <figcaption className="mt-5 flex flex-wrap items-baseline justify-between gap-x-8 gap-y-1 border-t border-rulesoft pt-3">
        <span className="label">
          probability the message is fabricated · plotted in log-odds, the scale
          the aggregator actually reasons in
        </span>
        <span className="label">
          {trace.length} tier{trace.length === 1 ? "" : "s"} purchased ·{" "}
          {data.tiers_skipped} left unbought · confidence{" "}
          <span className="text-ink">{data.confidence.toFixed(2)}</span>
        </span>
      </figcaption>
    </figure>
  );
}
