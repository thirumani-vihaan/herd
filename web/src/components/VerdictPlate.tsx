import type { Investigation } from "../lib/api";
import { look } from "../lib/verdict";
import BeliefAxis from "./BeliefAxis";

export default function VerdictPlate({ data }: { data: Investigation }) {
  const L = look(data.verdict);
  const abstained =
    data.verdict === "UNVERIFIED" || data.verdict === "OUT_OF_SCOPE";

  return (
    <section
      className="animate-rise"
      style={{ borderTop: `2px solid ${L.hex}` }}
    >
      <div className="pt-9 sm:pt-10">
      <div className="flex items-start justify-between gap-8">
        <div className="min-w-0">
          <p className="text-[12px] font-medium text-faint">Verdict</p>
          <h2
            className="mt-2 text-[clamp(2.8rem,7.5vw,5rem)] font-semibold leading-[0.9] tracking-[-0.035em]"
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
