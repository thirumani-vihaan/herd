import type { Investigation } from "../lib/api";
import { look } from "../lib/verdict";
import { useState } from "react";

export interface FeedEntry {
  seq: number;
  at: number;
  verdict: Investigation["verdict"];
  claim: string;
  strainId: string;
  count: number;
  velocity: string;
}

const VEL: Record<string, { word: string; hex: string }> = {
  low: { word: "contained", hex: "#8B8779" },
  medium: { word: "moving", hex: "#A56A00" },
  high: { word: "spreading", hex: "#A32017" },
};

/**
 * The outbreak feed.
 *
 * A single verdict is a checker; a stream of them is an epidemic. This is the
 * component that makes the thesis visible: as the same scam is reported again
 * and again, its strain surfaces here with a rising count, and the whole feed
 * tilts red when something starts to spread. It is the difference between
 * "is this true?" and "how far has this already travelled?"
 */
export default function FeedPanel({ entries }: { entries: FeedEntry[] }) {
  const isAdmin = typeof window !== 'undefined' && window.location.search.includes('admin=true');
  const [overrideBusy, setOverrideBusy] = useState<string | null>(null);

  async function handleOverride(strainId: string, label: string) {
    if (!confirm(`Are you sure you want to forcefully override this verdict to ${label}?`)) return;
    setOverrideBusy(strainId);
    try {
      const API_URL = import.meta.env.VITE_API_URL || "";
      const res = await fetch(`${API_URL}/override/${strainId}?label=${label}&secret=admin_secret`, { method: "POST" });
      if (res.ok) {
        alert("Verdict overridden successfully! The Live Feed will update shortly.");
      } else {
        alert("Failed to override verdict. Check server logs.");
      }
    } catch (e) {
      alert("Error overriding verdict");
    }
    setOverrideBusy(null);
  }

  if (entries.length === 0) return null;

  // How many distinct strains, and is anything actually spreading right now.
  const strains = new Map<string, FeedEntry>();
  for (const e of entries) {
    const prev = strains.get(e.strainId);
    if (!prev || e.count > prev.count) strains.set(e.strainId, e);
  }
  const hottest = [...strains.values()].sort((a, b) => b.count - a.count)[0];
  const spreading = [...strains.values()].some((e) => e.velocity === "high");

  return (
    <section className="mt-8 border-t border-rule pt-6">
      <div className="flex items-baseline justify-between">
        <h3 className="font-display text-[19px] tracking-tight">Live feed</h3>
        <span className="num text-[11px] text-faint">
          {entries.length} report{entries.length === 1 ? "" : "s"} ·{" "}
          {strains.size} strain{strains.size === 1 ? "" : "s"}
        </span>
      </div>

      <p className="mt-2 text-[12.5px] leading-relaxed text-faint">
        {spreading ? (
          <span className="text-false">
            A strain is spreading — {hottest.count} reports of the same message.
          </span>
        ) : (
          <>Each report that arrives, judged and folded into its strain.</>
        )}
      </p>

      <ol className="mt-4">
        {entries.map((e) => {
          const L = look(e.verdict);
          const vel = VEL[e.velocity] ?? VEL.low;
          const repeat = e.count > 1;
          return (
            <li
              key={e.seq}
              className="group animate-rise grid grid-cols-[auto_1fr_auto] items-baseline gap-x-3 border-t border-rulesoft py-2.5 relative hover:bg-rulesoft/30 transition-colors px-2 -mx-2 rounded cursor-pointer"
            >
              <span
                className="mt-[5px] h-2 w-2 shrink-0 rounded-full"
                style={{ background: L.hex }}
                aria-hidden
              />
              <div className="min-w-0">
                <p className="truncate text-[12.5px] leading-snug text-ink">
                  {e.claim}
                </p>
                <p className="mt-0.5 num text-[10.5px] text-faint">
                  {e.strainId.replace("str_", "").slice(0, 8)}
                  {repeat && (
                    <>
                      {" · "}
                      <span className="text-ink">×{e.count}</span>
                    </>
                  )}
                  {" · "}
                  <span style={{ color: vel.hex }}>{vel.word}</span>
                </p>
              </div>
              <span
                className="num text-[10px] font-medium uppercase tracking-wide group-hover:opacity-0 transition-opacity"
                style={{ color: L.hex }}
              >
                {e.verdict}
              </span>
              {isAdmin && (
                <div className="absolute right-0 top-1/2 -translate-y-1/2 hidden group-hover:flex items-center gap-1.5 bg-card pl-2">
                   <button 
                     onClick={() => handleOverride(e.strainId, "FALSE")}
                     disabled={overrideBusy === e.strainId}
                     className="text-[9.5px] px-1.5 py-0.5 bg-[#2a1a1a] text-[#f87171] rounded border border-[#451a1a] hover:bg-[#3f1c1c] uppercase disabled:opacity-50"
                   >
                     False
                   </button>
                   <button 
                     onClick={() => handleOverride(e.strainId, "TRUE")}
                     disabled={overrideBusy === e.strainId}
                     className="text-[9.5px] px-1.5 py-0.5 bg-[#14261c] text-[#4ade80] rounded border border-[#1b3d2b] hover:bg-[#1a3826] uppercase disabled:opacity-50"
                   >
                     True
                   </button>
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
