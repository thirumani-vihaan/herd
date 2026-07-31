import type { Investigation } from "../lib/api";
import { look } from "../lib/verdict";
import BeliefAxis from "./BeliefAxis";

export default function VerdictPlate({ data }: { data: Investigation }) {
  const L = look(data.verdict);
  const abstained =
    data.verdict === "UNVERIFIED" || data.verdict === "OUT_OF_SCOPE";

  return (
    <section
      className="animate-rise border border-rule bg-card shadow-plate"
      style={{ borderTop: `3px solid ${L.hex}` }}
    >
      <div className="px-8 py-10 sm:px-14 sm:py-12">
      <div className="flex items-start justify-between gap-8">
        <div className="min-w-0">
          <p className="label">the verdict</p>
          <h2
            className="font-display mt-3 text-[clamp(3.2rem,8.5vw,6rem)] leading-[0.86] tracking-tight"
            style={{ color: L.hex }}
          >
            {L.plain}
          </h2>
          <p className="mt-5 max-w-xl text-[15.5px] leading-relaxed text-muted">
            {L.meaning}
          </p>
        </div>

        <dl className="hidden shrink-0 gap-y-4 text-right sm:grid">
          <div>
            <dt className="label">label</dt>
            <dd className="num text-[15px] text-ink">{data.verdict}</dd>
          </div>
          <div>
            <dt className="label">investigated in</dt>
            <dd className="num text-[15px] text-ink">{data.elapsed_ms} ms</dd>
          </div>
          <div>
            <dt className="label">deepest tier</dt>
            <dd className="num text-[15px] text-ink">
              {data.highest_tier_reached}
            </dd>
          </div>
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

      {(abstained || data.withheld_confirmation || data.deadline_exceeded) && (
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
    <div className="flex gap-4">
      <span className="mt-[7px] h-px w-6 shrink-0 bg-faint" />
      <p className="text-[13.5px] leading-relaxed text-muted">
        <span className="font-medium text-ink">{title}.</span> {children}
      </p>
    </div>
  );
}
