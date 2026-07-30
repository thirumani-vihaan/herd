# ADR-0016 — RDAP over WHOIS for domain forensics

**Status:** Accepted

## Context

Domain registration age is one of the most diagnostic cheap signals available: a
"campus placement drive" link on a domain registered four days ago is close to
conclusive. Getting that date requires querying registration data.

## Options

**A. WHOIS.** Universal, ancient, and returns unstructured free text whose format
varies by registrar. Aggressively rate-limited, and increasingly redacted since
GDPR.

**B. RDAP.** The IETF-standardised successor. Returns **JSON**, uses HTTPS, has a
bootstrap registry for finding the authoritative server, and is mandated for gTLDs.

**C. A paid domain-intelligence API.** Richer data, costs money, adds a
credential.

## Decision

**B — RDAP**, with WHOIS as a fallback only for TLDs lacking RDAP coverage.

## Reasoning

The deciding factor is that **WHOIS output is not parseable in general.** Every
registrar formats dates and field names differently, so a WHOIS-based agent is a
collection of registrar-specific regexes that break silently when a registrar
changes its template. Silent breakage is the worst failure mode for an evidence
source — the agent keeps returning `unavailable` and the signal quietly
disappears from the aggregation without anyone noticing.

RDAP returns structured JSON with standardised event types
(`registration`, `expiration`, `last changed`). Parsing is a dictionary lookup,
and a schema change is a loud failure rather than a quiet one.

RDAP is also HTTPS with ordinary HTTP semantics, so it works with the same
`httpx` client, timeout policy, retry logic, and cassette recording as every other
network dependency ([ADR-0023](0023-cassette-replay.md)). WHOIS speaks its own
protocol on port 43 and would need separate handling for all of that.

Option C is rejected for v1: it adds a credential and a cost for data RDAP
provides free, and the marginal signal is small relative to the other agents.

## Consequences

**Accepted costs:**
- A few ccTLDs lack full RDAP coverage; those fall back to WHOIS or return
  `unavailable`, which the aggregator handles by widening uncertainty.
- Registration dates may be redacted for privacy-protected registrations. The
  agent reports `unavailable` rather than inferring.

**Gained:**
- Structured, parseable, standardised responses.
- Same HTTP client, timeout, retry, and cassette machinery as everything else.
- Loud rather than silent failures when a response shape changes.

**Note on confounds:** a young domain is not suspicious for a genuinely new
startup. Strength is modulated by whether the claimed organisation is
established — the agent reports the fact, and the aggregator weights it in context.
