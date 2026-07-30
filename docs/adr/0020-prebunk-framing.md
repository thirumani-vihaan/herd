# ADR-0020 — Pre-bunk framing over debunk framing

**Status:** Accepted

## Context

When HERD reaches a user, what does the message say?

## Options

**A. Debunk.** "That message about the Amazon drive is fake." Addresses people who
already saw it.

**B. Pre-bunk / inoculation.** "You may soon receive a message about an Amazon
drive asking for a fee. Here is the technique it uses."

**C. Both, selected by whether the user reported it.**

## Decision

**B as the default frame**, with C's targeting where a user is known to have
already been exposed.

## Reasoning

This is not a copywriting choice. It determines what the rest of the system must
be good at.

Inoculation theory (McGuire, 1961; Roozenbeek & van der Linden, 2019 onward) finds
consistently that **pre-exposure warning plus a weakened form of the manipulation
technique confers durable resistance**, while post-hoc correction is weak and can
entrench belief in some populations.

The architectural consequence: if correction worked well, HERD would only need to
be *accurate*, and the entire spread-modelling layer would be unnecessary — a good
classifier plus a search box would suffice. Because inoculation works and
correction largely does not, HERD must be **early**, which is why lead time is the
system's scorecard and why an epidemiological layer exists at all.
[ADR-0019](0019-expected-harm-alerting.md)'s `efficacy(t)` term is this finding
expressed as arithmetic.

The second consequence is the card's content. Inoculation transfers only if the
**technique** is named, not just the instance. "Real employers never charge
candidates — a fee request is the tell" generalises to the next scam with a
different company name. "This Amazon message is fake" blocks exactly one attack.
Naming the technique is what converts a single verdict into durable immunity, and
it is therefore a mandatory field of the card rather than a nice-to-have.

For the minority of recipients who *have* already seen the message, the pre-bunk
frame is mildly awkward but not harmful, and they are handled by the "already
paid?" action path — which exists because the already-harmed are both the most
motivated readers and the most effective amplifiers.

## Consequences

**Accepted costs:**
- The frame reads slightly oddly to someone who has already seen the message.
- Requires firing before the peak, which is a much harder engineering target than
  responding after it — the entire spread model exists to meet it.
- The message must be written well; a badly worded pre-bunk is just noise.

**Gained:**
- Intervention efficacy where the evidence says it is highest.
- Immunity that transfers to future variants rather than blocking one instance.
- A clear, measurable objective for the whole system: maximise the number of
  people warned *before* exposure.
