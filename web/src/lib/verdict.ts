import type { Verdict } from "./api";

export interface VerdictLook {
  hex: string;
  text: string;
  bg: string;
  border: string;
  /** The word a person would actually say out loud. */
  plain: string;
  /** What the system is committing to, stated honestly. */
  meaning: string;
}

export const VERDICT: Record<Verdict, VerdictLook> = {
  FALSE: {
    hex: "#A32017",
    text: "text-false",
    bg: "bg-false",
    border: "border-false",
    plain: "Fabricated",
    meaning:
      "The evidence points hard enough to say this message is not what it claims to be.",
  },
  MISLEADING: {
    hex: "#A56A00",
    text: "text-misleading",
    bg: "bg-misleading",
    border: "border-misleading",
    plain: "Distorted",
    meaning:
      "Something here is real, but the message bends it. Enough to warn about, not enough to call fabricated.",
  },
  TRUE: {
    hex: "#14624A",
    text: "text-true",
    bg: "bg-true",
    border: "border-true",
    plain: "Confirmed",
    meaning:
      "Found on a source the institution actually controls. Nothing else is allowed to confirm a claim.",
  },
  UNVERIFIED: {
    hex: "#55524A",
    text: "text-unverified",
    bg: "bg-unverified",
    border: "border-unverified",
    plain: "Unverified",
    meaning:
      "No strong evidence was found to prove this claim true or false. Proceed with caution.",
  },
  OUT_OF_SCOPE: {
    hex: "#55524A",
    text: "text-unverified",
    bg: "bg-unverified",
    border: "border-unverified",
    plain: "Out of scope",
    meaning: "This is not a claim about this institution.",
  },
};

export function look(v: Verdict | null | undefined): VerdictLook {
  return VERDICT[(v ?? "UNVERIFIED") as Verdict] ?? VERDICT.UNVERIFIED;
}

export const SIGNAL_GLYPH: Record<string, string> = {
  supports: "+",
  contradicts: "−",
  neutral: "·",
};
