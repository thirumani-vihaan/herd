# ADR-0014 — Calibrated confidence with a wide abstention band

**Status:** Accepted

## Context

The system must decide not only what it believes, but how strongly, and when to
decline to answer.

## Options

**A. Binary true/false.** No abstention. Forces a call on every claim.

**B. Three labels with a narrow uncertain band.** Maximises the fraction of
claims answered.

**C. Four labels with a deliberately wide abstention band**, and confidence
calibrated against ground truth.

## Decision

**C.**

| Posterior probability of falsity | Label |
|---|---|
| > 0.90 | `FALSE` |
| 0.65 – 0.90 | `MISLEADING` |
| 0.20 – 0.65 | `UNVERIFIED` |
| < 0.20 | `TRUE` |

`UNVERIFIED` spans 45 points of the range — the widest band, on purpose.

## Reasoning

The band widths encode the error asymmetry rather than leaving it to be handled
elsewhere. A false `FALSE` on a genuine placement notice causes a student to miss
a real opportunity and publicly damages an organisation's reputation. A false
`UNVERIFIED` on an actual scam causes someone to be cautious for longer than
necessary. These costs differ by an order of magnitude, so the thresholds do too.

Option A is tempting because abstention feels like failure. It is the opposite:
a system that answers everything will be confidently wrong regularly, and one
confident public error costs more trust than a hundred correct calls earn.
`UNVERIFIED` with the evidence attached is genuinely useful output — "we checked
these five things and could not confirm it" is actionable.

**Calibration is what makes the number honest.** A stated confidence of 0.8 must
correspond to being right about 80% of the time, or the number is decoration that
users nonetheless act on. Calibration is measured with expected calibration error
and reported as a reliability diagram rather than a single scalar, because a good
ECE can hide systematic overconfidence in a specific range.

The target abstention rate is **0.15–0.35**. Below that range the system is
overconfident; above it, useless. This is monitored as a first-class metric, and
drift in either direction triggers recalibration rather than threshold-fiddling.

## Consequences

**Accepted costs:**
- Roughly a quarter of claims get no definitive answer.
- Recall on `FALSE` is lower than an aggressive system would report.
- Calibration requires labelled ground truth that must be actively maintained.

**Gained:**
- Precision on `FALSE` can be held above 0.97, which is the number that protects
  the project's credibility.
- Confidence values are meaningful enough to act on.
- Abstention is a designed, explained outcome rather than an apparent malfunction.
