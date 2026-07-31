import { useState } from "react";
import type { Sample } from "../lib/api";

export default function ReportSlip({
  onSubmit,
  busy,
  samples,
}: {
  onSubmit: (v: {
    text: string;
    isForwarded: boolean;
    isFrequentlyForwarded: boolean;
  }) => void;
  busy: boolean;
  samples: Sample[];
}) {
  const [text, setText] = useState("");
  const [fwd, setFwd] = useState(false);
  const [freq, setFreq] = useState(false);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (text.trim() && !busy)
          onSubmit({
            text: text.trim(),
            isForwarded: fwd,
            isFrequentlyForwarded: freq,
          });
      }}
      className="border border-rule bg-card shadow-plate"
    >
      <header className="flex items-baseline justify-between border-b border-rule px-7 py-5">
        <h3 className="font-display shrink-0 text-[19px] tracking-tight">
          Report a message
        </h3>
        <p className="label">nothing here identifies you</p>
      </header>

      <div className="px-7 py-6">
        <label htmlFor="msg" className="label">
          what did you receive
        </label>
        <textarea
          id="msg"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={9}
          spellCheck={false}
          placeholder="Paste the message exactly as it arrived. Phone numbers, UPI handles and links are stripped before anything is stored."
          className="mt-2 w-full resize-none border border-rule bg-paper px-4 py-3 font-mono text-[13.5px] leading-relaxed text-ink outline-none placeholder:text-faint focus:border-ink"
        />

        <div className="mt-5 space-y-3">
          <Toggle
            checked={fwd}
            onChange={setFwd}
            label="It was forwarded to me"
            hint="Provenance, not content — it changes what the template agent looks for."
          />
          <Toggle
            checked={freq}
            onChange={setFreq}
            label="WhatsApp marked it forwarded many times"
            hint="A strong signal that this is circulating rather than personal."
          />
        </div>

        <button
          type="submit"
          disabled={!text.trim() || busy}
          className="mt-7 w-full bg-ink px-5 py-3.5 text-[14px] font-medium tracking-tight text-paper transition-opacity disabled:cursor-not-allowed disabled:opacity-30"
        >
          {busy ? "Investigating…" : "Run the investigation"}
        </button>

        <div className="mt-6 border-t border-rulesoft pt-5">
          <p className="label">
            {samples.length ? "or try one" : "samples load with the service"}
          </p>
          <div className="mt-2.5 flex flex-wrap gap-2">
            {samples.map((s) => (
              <button
                key={s.label}
                type="button"
                onClick={() => {
                  setText(s.text);
                  setFwd(s.forwarded);
                  setFreq(s.forwarded);
                }}
                className="border border-rule px-3 py-1.5 text-[12.5px] text-muted transition-colors hover:border-ink hover:text-ink"
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </form>
  );
}

function Toggle({
  checked,
  onChange,
  label,
  hint,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  hint: string;
}) {
  return (
    <label className="flex cursor-pointer gap-3">
      <span
        className={`mt-[3px] flex h-[15px] w-[15px] shrink-0 items-center justify-center border transition-colors ${
          checked ? "border-ink bg-ink" : "border-rule bg-paper"
        }`}
      >
        {checked && (
          <svg viewBox="0 0 10 8" className="h-[7px] w-[9px]" aria-hidden>
            <path
              d="M1 4.2 3.5 6.7 9 1.2"
              fill="none"
              stroke="#FBFAF7"
              strokeWidth="1.8"
            />
          </svg>
        )}
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="sr-only"
      />
      <span>
        <span className="block text-[13.5px] leading-snug text-ink">
          {label}
        </span>
        <span className="mt-0.5 block text-[12px] leading-snug text-faint">
          {hint}
        </span>
      </span>
    </label>
  );
}
