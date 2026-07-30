# Architecture Decision Records

Each record states the options that were genuinely considered, the tradeoff, the
decision, and the consequences accepted. Records are immutable — a changed mind
produces a new record that supersedes the old one.

## Index

### Ingestion
| # | Decision | Status |
|---|---|---|
| [0001](0001-report-driven-not-monitoring.md) | Report-driven, never group monitoring | Accepted |
| [0002](0002-screenshot-first-input.md) | Screenshot-first input modality | Accepted |
| [0003](0003-ingestion-channels.md) | Web+QR primary, Telegram secondary, no WhatsApp API in v1 | Accepted |
| [0004](0004-pseudonymous-reporters.md) | Rotating salted-hash reporter identity | Accepted |

### Perception
| # | Decision | Status |
|---|---|---|
| [0005](0005-multimodal-ocr.md) | Multimodal LLM for OCR + extraction in one pass | Accepted |
| [0006](0006-multilingual-embeddings.md) | Multilingual embeddings, not English MiniLM | Accepted — supersedes initial choice |

### Recognition
| # | Decision | Status |
|---|---|---|
| [0007](0007-incremental-strain-assignment.md) | Incremental assignment, not batch HDBSCAN | Accepted — supersedes initial choice |
| [0008](0008-strain-identity.md) | Strain identity = semantic similarity AND entity compatibility | Accepted |
| [0009](0009-mutation-detection.md) | Multi-signal mutation detection | Accepted |
| [0010](0010-vector-store.md) | Chroma behind a `VectorIndex` interface | Accepted |

### Investigation
| # | Decision | Status |
|---|---|---|
| [0011](0011-tiered-investigation-cascade.md) | Tiered cascade, not parallel broadcast | Accepted — supersedes initial choice |
| [0012](0012-evidence-not-verdicts.md) | Agents return evidence, never verdicts | Accepted |
| [0013](0013-deterministic-verdict-aggregation.md) | Deterministic aggregation sets the label; LLM writes prose | Accepted — supersedes initial choice |
| [0014](0014-calibrated-confidence-and-abstention.md) | Calibrated confidence with a wide abstention band | Accepted |
| [0015](0015-institutional-snapshot.md) | Pre-crawled institutional snapshot + RAG | Accepted |
| [0016](0016-rdap-over-whois.md) | RDAP over WHOIS | Accepted |
| [0017a](0017a-langgraph-orchestration.md) | LangGraph for orchestration | Accepted |
| [0027](0027-strength-is-a-confidence.md) | Evidence strength is a confidence, converted to log-odds by a calibrated scale | Accepted — fixes a bug in 0013 |
| [0028](0028-true-requires-confirmation.md) | TRUE requires a confirming source; absence of fraud indicators is not evidence of authenticity | Accepted |

### Spread
| # | Decision | Status |
|---|---|---|
| [0017](0017-tiered-spread-model.md) | Sample-size-tiered spread model | Accepted — supersedes initial choice |
| [0018](0018-report-process-bias.md) | Model the report process explicitly; use message time | Accepted |
| [0019](0019-expected-harm-alerting.md) | Expected-harm alert rule, not fixed thresholds | Accepted — supersedes initial choice |

### Intervention
| # | Decision | Status |
|---|---|---|
| [0020](0020-prebunk-framing.md) | Pre-bunk framing over debunk framing | Accepted |
| [0021](0021-intervention-channels.md) | Telegram + WebSocket primary; Web Push best-effort | Accepted — supersedes initial choice |

### System
| # | Decision | Status |
|---|---|---|
| [0022](0022-single-process-v1.md) | Single process + SQLite for v1 | Accepted — supersedes initial choice |
| [0023](0023-cassette-replay.md) | Cassette-based replay mode | Accepted |
| [0026](0026-institution-profiles.md) | Institution as a loaded profile; strain memory global, evidence scoped | Accepted — supersedes initial choice |

### Policy
| # | Decision | Status |
|---|---|---|
| [0024](0024-scope-guard.md) | Explicit scope guard with refusal as an outcome | Accepted |
| [0025](0025-wording-policy.md) | Evidence-only wording, never accusation | Accepted |
