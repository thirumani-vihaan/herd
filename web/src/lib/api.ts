export type Verdict =
  | "TRUE"
  | "MISLEADING"
  | "FALSE"
  | "UNVERIFIED"
  | "OUT_OF_SCOPE";

export interface SourceRef {
  url: string;
  title: string;
  excerpt: string;
  kind: string;
}

export interface EvidenceItem {
  agent: string;
  tier: number;
  status: "ok" | "unavailable" | string;
  signal: "supports" | "contradicts" | "neutral" | string;
  strength: number;
  finding: string;
  elapsed_ms: number;
  error: string | null;
  sources: SourceRef[];
}

export interface TierTrace {
  tier: number;
  agents_run: string[];
  agents_skipped: string[];
  elapsed_ms: number;
  posterior_after: number;
  label_after: string;
  exited: boolean;
}

export interface Investigation {
  verdict: Verdict;
  summary: string;
  bands: {
    false_above: number;
    misleading_above: number;
    unverified_above: number;
  };
  posterior_false: number;
  prior: number;
  confidence: number;
  clamped: boolean;
  withheld_confirmation: boolean;
  withheld_for_standing: boolean;
  elapsed_ms: number;
  deadline_exceeded: boolean;
  highest_tier_reached: number;
  tiers_skipped: number;
  claim: {
    text: string;
    type: string;
    language: string;
    degraded: boolean;
  };
  strain: {
    id: string;
    report_count: number;
    velocity: "low" | "medium" | "high" | string;
    first_seen: string | null;
  };
  trace: TierTrace[];
  evidence: EvidenceItem[];
  tracking_id?: string;
  inoculation_html?: string;
}

export interface IngestResult {
  tracking_id: string;
  status: string;
  verdict: Verdict | null;
  summary: string | null;
  result: Investigation | null;
}

export const TIER_NAMES: Record<number, string> = {
  0: "Wording",
  1: "Infrastructure",
  2: "Official record",
  3: "Open web",
};

export const TIER_BLURB: Record<number, string> = {
  0: "Costs nothing. Reads the message itself — pressure, payment shape, template lineage.",
  1: "Cheap probes. Domains, links and contact details against what the institution actually publishes.",
  2: "Retrieval. The only tier permitted to confirm a claim is genuine.",
  3: "Terminal. Open-web research, bought only when everything cheaper abstained.",
};

export interface Sample {
  label: string;
  text: string;
  forwarded: boolean;
}

export interface AppContext {
  institution: {
    id: string;
    short_name: string;
    display_name: string;
    official_domain: string;
  };
  agent_count: number;
  global_stats?: {
    total_intercepts: number;
    estimated_fraud_blocked: number;
  };
  samples: Sample[];
}

/**
 * The interface holds no institutional string of its own (ADR-0026) — not even
 * in its demo samples. Point HERD at another campus and this changes with it.
 */
const API_URL = import.meta.env.VITE_API_URL || "";

export async function loadContext(): Promise<AppContext> {
  const res = await fetch(`${API_URL}/context`);
  if (!res.ok) throw new Error(`context unavailable (${res.status})`);
  return (await res.json()) as AppContext;
}

export async function investigate(input: {
  text: string;
  isForwarded: boolean;
  isFrequentlyForwarded: boolean;
  reporterHash: string;
  image?: File | null;
}): Promise<IngestResult> {
  const body = new FormData();
  body.append("text", input.text);
  body.append("reporter_hash", input.reporterHash);
  body.append("is_forwarded", String(input.isForwarded));
  body.append("is_frequently_forwarded", String(input.isFrequentlyForwarded));
  if (input.image) {
    body.append("image", input.image);
  }

  const res = await fetch(`${API_URL}/ingest`, { method: "POST", body });
  if (!res.ok) {
    // Surface what the service actually said. A bare status code sends the
    // reader hunting through logs for something the server already knows.
    let detail = "";
    try {
      const body = (await res.json()) as { detail?: string };
      detail = typeof body.detail === "string" ? body.detail : "";
    } catch {
      detail = "";
    }
    throw new Error(
      detail || `The investigation service returned ${res.status}.`
    );
  }
  return (await res.json()) as IngestResult;
}

export async function checkHealth(): Promise<number> {
  const start = performance.now();
  try {
    const res = await fetch(`${API_URL}/health`);
    if (!res.ok) return -1;
    await res.json();
    return Math.round(performance.now() - start);
  } catch {
    return -1;
  }
}
