# Saha — Product & Security Roadmap

> **2026-11-01 context:** This document preserves the earlier audit/plan and its recorded evidence. It is not a current host probe or completed-feature inventory. See [Current security boundaries](CURRENT-SECURITY.md), [release evidence](../docs/CURRENT-STATUS.md) and the [open-collaboration plan](../docs/OPEN-INNOVATION-PLAN.md). Use the current hosting runbook for deployments; retain the historical findings below.

**Version:** 1.0 · **Date:** 2026-08-05
**Companions:** [AUDIT.md](AUDIT.md) · [THREAT-MODEL.md](THREAT-MODEL.md) · [REMEDIATION-PLAN.md](REMEDIATION-PLAN.md) · [ARCHITECTURE-TARGET.md](ARCHITECTURE-TARGET.md)

Assessed against what a credible global IP trading platform must have. Status: **Absent** · **Partial** · **Present**.

Every proposed feature carries an explicit **security implication** section, because several of these *add* attack surface — tiered disclosure, data rooms, registry integrations and bulk import each open a new boundary that must be designed for up front rather than retrofitted.

**Framing.** Confirmed direction: global platform, lawyers own the handover, and the marketplace itself must be a safe place to trade, list, communicate, and find open information. That framing is load-bearing throughout — Saha is the **coordination, confidentiality and evidence layer**; it is not the legal source of truth and should not pretend to be. Features are prioritised accordingly: anything that makes the platform a more trustworthy *evidence and confidentiality* substrate outranks anything that makes it a more feature-rich marketplace.

---

## 1. Trust and verification

| Capability | Status | Evidence |
|---|---|---|
| Chain-of-title verification | **Absent** | `create_listing` records title/category/description only |
| Registry status monitoring | **Absent** | No registry integration of any kind |
| KYC (individuals) | **Partial** | Persona wired but `inquiry-template-id` is the literal placeholder; mock mode active ([SAHA-004](AUDIT.md)) |
| KYB (entities) | **Absent** | No organisation model exists |
| Sanctions / PEP screening | **Absent** | [SAHA-029](AUDIT.md) |
| Ownership attestation | **Absent** | [SAHA-037](AUDIT.md) |
| Encumbrance disclosure | **Absent** | No fields for licences, liens, litigation, SEP commitments |

### 1.1 Ownership attestation with evidence trail — **do first**
Cheapest credible control, and it must precede automated verification because it establishes the record automation later checks against.

**Design.** At publish, the seller affirms: they own or control the IP; identifies the registry and number where applicable; declares encumbrances; accepts liability for misrepresentation. Attestation text is versioned; the signed statement is hashed and written to the tamper-evident audit log ([SAHA-014](AUDIT.md)) with actor, timestamp and IP.

**Security implications.** Positive — creates the evidentiary basis for a fraud claim. New surface: attestation text becomes legally operative content, so the **versioning and integrity of the attestation template itself** must be protected; a mutable template is a repudiation vector. **Counsel drafts the wording.**

**Sequence:** Q1, 1 week. Depends on [REMEDIATION-PLAN 3.3](REMEDIATION-PLAN.md) phase (a).

### 1.2 Automated chain-of-title verification
**Design.** Before a listing goes live, resolve the identifier against USPTO Assignment Search / PatentsView, CIPO, EUIPO and WIPO where available. Compare the recorded assignee against the seller's verified KYB identity. Three outcomes: **verified** (badge), **mismatch** (blocked, routed to manual review), **unavailable** (listed with an explicit "unverified title" label). Cache with a TTL; re-check on state change.

**Security implications.** ⚠️ This is the roadmap's **first outbound-fetch-on-user-input surface** — Saha currently has none, which is why the SSRF category is clean. Preserve that: registry endpoints must be a hard-coded allow-list, never user-supplied URLs; identifiers must be validated against strict per-registry format patterns before use; responses must be parsed with a strict schema. **If any registry feed is XML, this also introduces the first XXE surface** — use `defusedxml`, never the stdlib parser. Timeouts, circuit breakers and rate limits are required so a slow registry cannot stall listing publication.

**Sequence:** Q1–Q2, 4 weeks. Depends on 1.1, 1.4.

### 1.3 Registry status monitoring
**Design.** Scheduled re-check of maintenance-fee status, abandonment, opposition proceedings and renewal deadlines for every listed and in-deal asset. Alert both parties mid-deal when status changes — an asset lapsing during diligence is material.

**Security implications.** Alerts reveal deal existence, so notification targeting must respect the disclosure tier. Scheduler must not be in-process (the current `library_digest` pattern runs in every worker and serialises via an advisory lock — workable but not the right shape for this).

**Sequence:** Q2, 3 weeks. Depends on 1.2.

### 1.4 KYB and sanctions/PEP screening
**Design.** Organisation model (org, members, roles, beneficial owners); KYB provider integration; denied-party screening (OFAC SDN, EU consolidated, UN, HMT) at registration, at KYB, and re-screened per transaction; PEP screening; jurisdiction fields on user and listing; export classification with a disclosure gate. Screening results written to the evidentiary log.

**Security implications.** Introduces the **organisation boundary**, which is the tenancy model Saha currently lacks ([THREAT-MODEL TB-11](THREAT-MODEL.md)). Get it right on arrival: org-scoped authorization from day one, no implicit cross-org visibility, explicit delegation. Screening data is sensitive PII with its own retention rules.

**Security implications (negative, must be designed around):** false-positive screening results are defamatory if exposed — never surface another party's screening status.

**Sequence:** Q2, 6 weeks. **Counsel must scope obligations before build.**

### 1.5 Encumbrance disclosure
**Design.** Structured fields on the listing: existing licences (exclusive/non-exclusive, field, territory), security interests, pending litigation, standard-essential declarations, government-funding march-in rights. Required at publish; changes versioned and logged.

**Security implications.** Encumbrance detail is commercially sensitive — place it in the **NDA-gated tier** (§2), not the public teaser.

**Sequence:** Q1, 1 week (schema + form). Ships with 1.1.

---

## 2. Confidentiality architecture — the highest-priority section

| Capability | Status | Evidence |
|---|---|---|
| Tiered disclosure | **Absent** (worse: inverted) | [SAHA-003](AUDIT.md) — the "public" endpoint returns the confidential tier |
| Click-through NDA | **Absent** | Enum values and DB columns exist; **no code path sets them** |
| Dynamic watermarking | **Absent** | — |
| View-only rendering | **Absent** | Download hands over the original bytes |
| Per-deal data rooms | **Absent** | Access is all-or-nothing per listing, keyed on escrow state |
| Access analytics for sellers | **Absent** | Downloads audited but never surfaced to the seller |

### 2.1 Three-tier disclosure enforced at storage and API — **the single most important item on this roadmap**

**Design.**

| Tier | Contents | Gate | Storage |
|---|---|---|---|
| **T0 Teaser** | title, category, tags, `public_description`, verification badges | public | Postgres, indexed in Qdrant |
| **T1 NDA-gated summary** | technical summary, encumbrances, redacted BOM (materials without specs/quantities), document *inventory* | executed NDA + verified identity | Postgres, separate table |
| **T2 Data room** | full BOM, vault documents, unredacted filings | per-document grant within a deal | Encrypted object storage, per-deal keys |

Enforce at **three** layers, not one: distinct response models per tier ([REMEDIATION-PLAN 3.5](REMEDIATION-PLAN.md)); distinct storage locations so a query bug cannot cross tiers; a single audited document-access path ([REMEDIATION-PLAN 3.2](REMEDIATION-PLAN.md)).

Note the current schema already anticipates T0/T2 — `public_description` vs `description`, and the Qdrant payload correctly carries only teaser fields. **T1 does not exist at all**, and it is the tier where diligence actually happens. Today a buyer sees everything (via the SAHA-003 defect) or, once fixed, sees only a teaser until escrow — with no middle ground in which to decide whether to bid.

**Security implications.** The redacted-BOM generation in T1 is the delicate part: redaction must be **generative, not subtractive** — build T1 content from explicit fields the seller authors, never by stripping fields from T2. Subtractive redaction fails open on every new field added. This is a design rule worth writing into the code as a comment.

**Sequence:** Q1–Q2, 6 weeks. Depends on [REMEDIATION-PLAN 1.1, 3.2](REMEDIATION-PLAN.md).

### 2.2 Click-through NDA with per-document scope
**Design.** Versioned NDA templates per jurisdiction. Buyer executes before T1 access; scope, version hash, timestamp, IP and identity recorded in the evidentiary log. Per-document acknowledgement for T2. Seller may set NDA terms per listing. Expiry and revocation supported.

**Security implications.** The NDA record becomes legally operative evidence — it must live in the tamper-evident layer, not an ordinary table, or it is worthless in the dispute it exists for. Template versioning must be immutable. **Counsel drafts templates per jurisdiction; enforceability of click-through varies materially and this is a global platform.**

**Sequence:** Q2, 3 weeks. Depends on 2.1, [REMEDIATION-PLAN 3.3](REMEDIATION-PLAN.md).

### 2.3 Per-deal virtual data rooms
**Design.** A data room per deal with granular grants (document × party × permission), time-boxed, revocable, with an explicit grant ledger. Replaces today's "escrow funded ⇒ every file on the listing" rule, which is both too coarse and too late.

**Security implications.** Positive overall — replaces a binary gate with least privilege, and revocation becomes meaningful. New surface: the grant model is itself an authorization system and must run through the central policy module ([REMEDIATION-PLAN 3.1](REMEDIATION-PLAN.md)) rather than growing its own checks. Grant changes are security events requiring alerts.

**Sequence:** Q2–Q3, 5 weeks. Depends on 2.1, [REMEDIATION-PLAN 3.1, 3.2](REMEDIATION-PLAN.md).

### 2.4 Watermarking and view-only rendering
**Design.** Server-side render to image tiles or a locked-down viewer; per-viewer watermark (identity, timestamp, deal id) applied at render time; original bytes never leave the boundary for T2 preview. Download remains available where the deal terms require it, watermarked and logged.

**Security implications.** ⚠️ **This introduces the first document-processing pipeline** — currently absent, which is why the command-injection category is clean. Rendering PDFs and Office documents means parsing hostile input. Non-negotiable: run rendering in a **sandboxed, network-isolated, ephemeral worker** with strict resource limits; never `shell=True`; treat every document as hostile. Pair with malware scanning ([SAHA-018](AUDIT.md)) — this is where it becomes mandatory rather than advisable. Also: rendered tiles are a **new copy of the confidential content** and need the same encryption, access control and lifecycle as the original. Watermarking is attribution, not prevention — it deters, it does not stop a camera.

**Sequence:** Q3, 6 weeks. Depends on 2.3.

### 2.5 Seller access analytics
**Design.** Surface to the seller: who viewed which document, when, for how long, how many times. Drives negotiation ("three parties reviewed the claims twice") and provides leak-attribution context.

**Security implications.** Buyer-side privacy exposure — disclose the analytics clearly in the NDA and terms so buyers know their diligence behaviour is visible. Data derives from the audit log; expose a projection, never raw audit rows.

**Sequence:** Q3, 2 weeks. Depends on 2.3.

---

## 3. Evidentiary integrity

| Capability | Status |
|---|---|
| Canonical serialisation + hashing of material events | **Absent** |
| Append-only guarantee | **Absent** — [SAHA-014](AUDIT.md) |
| RFC 3161 timestamps | **Absent** |
| Confidential Ledger receipts | **Absent** |
| Public-chain Merkle anchoring | **Absent** |
| User-facing verification tool | **Absent** |
| Exportable evidence packages | **Absent** |

**This section is what makes Saha defensible as a product.** Given lawyers own the handover and will rely on Saha's record, an evidentiary layer any operator can rewrite is not a gap — it is a contradiction of the value proposition.

### 3.1 Canonical hashing of material events (Q1, 2 weeks)
Material events: listing published · attestation signed · NDA executed · document disclosed · offer submitted · counter-offer · acceptance · contract generated · signature · escrow funded · disbursement · closing.

Canonical serialisation (RFC 8785 / JCS-style: sorted keys, no insignificant whitespace, defined number and null handling, UTF-8) is **not optional** — non-canonical JSON hashing silently destroys verifiability, exactly as the directive warns, and `log_metadata` is currently free-form JSONB with no schema. Define an explicit event schema per event type. Hash **only** pseudonymous subject identifiers and content digests, never raw personal data, so immutability and erasure rights can coexist (§6).

### 3.2 Append-only enforcement (Q1, 1 week)
`REVOKE UPDATE, DELETE`; `BEFORE UPDATE OR DELETE` trigger raising an exception; a separate INSERT-only database role for the audit writer ([SAHA-034](AUDIT.md)).

### 3.3 RFC 3161 timestamps (Q2, 2 weeks) — **before any chain anchoring**
Daily Merkle root over the hash chain, timestamped by an accredited TSA. Cheap, standardised, and with **far more court precedent** than any blockchain anchor. Store tokens alongside the roots. This is the highest evidentiary value per unit of effort in the entire roadmap.

### 3.4 Azure Confidential Ledger (Q3, 3 weeks)
Write daily digests for enclave-backed, tamper-evident receipts that exclude even the cloud operator from the trusted computing base. Complements, not replaces, 3.3.

### 3.5 Optional public-chain anchoring (Q4, 2 weeks)
Daily Merkle root only — **batched, never per-transaction**. Per-transaction anchoring leaks transaction volume and timing, costs disproportionately, and adds nothing 3.3 does not already provide. Anchor the root, never any content-derived value that could be correlated.

### 3.6 Verification tool and evidence packages (Q3, 3 weeks)
A tool letting any party verify a receipt **without trusting Saha**: given a receipt, recompute the hash, verify chain inclusion, verify the Merkle path to the timestamped root, verify the TSA token. Publish the algorithm and make it runnable offline. Evidence packages: a signed bundle of all events for a transaction, with documents, hashes, timestamps and a verification script — suitable for litigation or diligence.

**Security implications.** ⚠️ The verification tool must not become a disclosure channel: it verifies **hashes and metadata**, never content, and must not confirm the existence of transactions to non-parties. Design the receipt format so verification is possible without revealing counterparty identity to third parties.

---

## 4. Transaction mechanics

| Capability | Status | Evidence |
|---|---|---|
| Formal deal state machine | **Present** ✅ | `_VALID_TRANSITIONS` + `_SYSTEM_ONLY_TARGETS` — genuinely well built |
| Licensed escrow provider | **Partial** | Stripe scaffolding in mock mode; Stripe is a payment processor, **not a licensed escrow agent** |
| E-signature | **Absent** | DocuSign is a `logger.info` stub — [SAHA-008](AUDIT.md) |
| Registry recordation | **Absent** | — |
| Structured deal terms | **Partial** | `license_type`, `territory`, `duration_months` only |
| Negotiation history | **Partial** | `proposal_versions` exists ✅ but is mutably logged |

### 4.1 Dual-signature execution → real e-signature (Q1 interim, Q2 full)
Interim in [REMEDIATION-PLAN 2.1](REMEDIATION-PLAN.md). Full: DocuSign/Adobe/Dropbox Sign, with the **executed document as the operative artefact** — not a status flag. Store the executed PDF encrypted, hash it into the evidentiary chain, expose it to both parties.

**Security implications.** E-signature webhooks are a new signature-verified boundary — apply the Stripe pattern (HMAC, `compare_digest`, replay window), which is already correct and worth copying verbatim. Envelope ids are sensitive. **Counsel confirms what constitutes execution per jurisdiction** (eIDAS, ESIGN/UETA and equivalents differ materially).

### 4.2 Licensed escrow (Q2, 4 weeks)
Stripe alone is insufficient for holding funds pending contractual conditions in most jurisdictions. Integrate a licensed escrow provider (Escrow.com or regional equivalents) or partner with the law firms already modelled in `law_firm_partners` for trust-account handling — which fits the lawyer-led handover model well and may be the better path.

**Security implications.** Release conditions become a legally binding state machine; every release must be evidentially recorded. Fixes [SAHA-007](AUDIT.md) structurally rather than by predicate correction. **Counsel must confirm the escrow model per jurisdiction — this is a licensing question.**

### 4.3 Structured deal terms (Q2, 3 weeks)
Royalty structures (fixed, running, tiered, minimum guarantees), field-of-use restrictions, territory as structured jurisdiction codes rather than free text, exclusivity type, milestone payments, sublicensing rights, improvement/grant-back terms, termination triggers.

**Security implications.** Larger structured surface = more validation. Every monetary and percentage field must be server-computed or server-validated; never trust a client-supplied fee or royalty. The current fee computation is correctly server-side (`SAHA_COMMISSION_RATE` etc.) — preserve that property as the model grows.

### 4.4 Immutable negotiation history (Q2, 1 week)
`proposal_versions` already captures each version ✅. Hash each into the evidentiary chain so terms cannot be retroactively altered. Small change, high value.

### 4.5 Registry recordation assistance (Q4, 4 weeks)
Post-closing: generate assignment documents in registry-required form, guide or automate filing (USPTO ETAS, CIPO, EUIPO), track recordation status, close the loop by confirming the registry reflects the transfer.

**Security implications.** Filing on a user's behalf means holding registry credentials or acting under power of attorney — a **significant new trust boundary** requiring its own key custody design. Prefer generating documents for the user's counsel to file over holding credentials. This aligns with the lawyer-led model and avoids the boundary entirely.

---

## 5. Platform maturity

| Capability | Status | Notes |
|---|---|---|
| Metadata-only search indexing | **Present** ✅ | Qdrant payload carries only teaser fields — correctly done |
| Comparable transaction data | **Absent** | |
| Broker/agent roles with commissions | **Absent** | Roles are labels; no commission model |
| Portfolio management | **Absent** | No multi-asset grouping |
| FTO / citation-graph flagging | **Absent** | |
| Bulk import from portfolio systems | **Absent** | |
| Open Innovation Library | **Present** ✅ | Curated, moderated, with member submissions — a genuine differentiator |
| Communities | **Present** ✅ | Topic communities with group chat |
| Reviews / reputation | **Present** ✅ | One review per party per completed transaction |
| Demand intelligence | **Present** ✅ | Though over-shared — [SAHA-033](AUDIT.md) |

### 5.1 Comparable transaction data (Q3, 4 weeks)
Anonymised, aggregated comparables to support valuation.

**Security implications.** ⚠️ The **highest re-identification risk in the roadmap.** With few transactions, "average deal value for biotech patents in Q3" identifies specific deals. Enforce k-anonymity (minimum cohort size, ≥5 and probably higher), differential-privacy noise on small cohorts, and suppression rather than approximation below threshold. Never expose per-transaction values. The same discipline is already needed for `/demand/overview` ([SAHA-033](AUDIT.md)) — build one aggregation-safety primitive and use it for both.

### 5.2 Broker and agent roles (Q3, 4 weeks)
Brokers acting on behalf of sellers or buyers, with commission splits and disclosed representation.

**Security implications.** ⚠️ **Delegation is a new privilege-escalation surface.** A broker acting for a seller must not thereby see other sellers' data. Requires explicit, scoped, revocable, time-boxed delegation running through the central policy module — not a role flag. Commission handling touches money movement and must be server-computed. Disclosed representation must be visible to counterparties (undisclosed dual agency is a legal problem in many jurisdictions).

### 5.3 Portfolio management (Q3, 3 weeks)
Group assets into portfolios; bulk operations; portfolio-level deals.

**Security implications.** Bulk operations amplify blast radius — a mis-scoped bulk publish exposes an entire portfolio at once. Require explicit confirmation, per-asset preview, and rate limits on bulk actions. Portfolio-level NDAs must not implicitly grant per-asset T2 access.

### 5.4 FTO and citation-graph flagging (Q4, 6 weeks)
Surface citation relationships, potentially blocking patents, and litigation history.

**Security implications.** ⚠️ **Liability, not confidentiality.** FTO analysis is legal advice in most jurisdictions. Present as informational data with prominent disclaimers, never as an opinion. **Counsel must review the framing before launch** — this is the roadmap item most likely to create liability from a feature intended to add value.

### 5.5 Bulk import (Q4, 4 weeks)
Import from Anaqua, IPfolio, CPA Global, or CSV.

**Security implications.** ⚠️ Bulk untrusted input: CSV injection (formula injection into exported spreadsheets), zip bombs, XXE if XML formats are supported (**use `defusedxml`**), and mass-assignment risk if import maps directly to models. Import must go through the same validated schemas as the API, never a bypass path. Rate-limit and size-cap. Imported assets default to **draft**, never auto-published.

---

## 6. Global compliance — build once, correctly

Confirmed: global platform. The regimes below apply simultaneously, and some conflict. Details in [THREAT-MODEL §6](THREAT-MODEL.md).

| Workstream | Sequence | Notes |
|---|---|---|
| Retention schedule + deletion + export | Q1–Q2, 4 weeks | [SAHA-025](AUDIT.md). **Counsel sets periods**; engineering builds machinery |
| Erasure vs. immutability resolution | Q1, design | Hash **only** salted pseudonymous ids and content digests; keep personal data in erasable storage keyed by those ids. Decide this **before** 3.1 hashes anything — retrofitting is close to impossible |
| Region-pinned data planes | Q3–Q4 | PIPL and others require in-country storage. Global control plane, regional data planes. Accept some markets are out of scope until a local plane exists |
| Processor inventory + DPAs | Q1 | NVIDIA, Anthropic, Stripe, Persona, Cloudflare, Azure. **Best answer for the LLM providers is to stop sending them confidential content** ([SAHA-013](AUDIT.md)) |
| Consent and transparency | Q2 | Disclose AI processing, access analytics, screening, and cross-border transfers |
| Breach response | Q2 | Runbook with jurisdiction-specific notification timelines (GDPR 72h, others vary) |

---

## 7. Suggested sequence

**Q1 — Make it safe and honest.** [REMEDIATION-PLAN](REMEDIATION-PLAN.md) Tiers 0–2 · ownership attestation (1.1) · encumbrance fields (1.5) · canonical hashing (3.1) · append-only enforcement (3.2) · dual-signature interim (4.1) · erasure-vs-immutability decision (§6) · retention design.
*Exit: safe to onboard a real seller with real IP.*

**Q2 — Make it credible.** Tiered disclosure (2.1) · click-through NDA (2.2) · chain-of-title (1.2) · KYB + sanctions (1.4) · RFC 3161 (3.3) · real e-signature and licensed escrow (4.1, 4.2) · structured terms (4.3) · registry monitoring (1.3).
*Exit: a buyer's counsel can complete diligence on the platform and rely on its record.*

**Q3 — Make it defensible.** Data rooms (2.3) · watermarking and view-only (2.4) · access analytics (2.5) · Confidential Ledger (3.4) · verification tool and evidence packages (3.6) · comparables (5.1) · brokers (5.2) · portfolios (5.3) · region-pinned planes.
*Exit: SOC 2 Type II observation window can begin.*

**Q4 — Make it complete.** Registry recordation (4.5) · FTO and citation graph (5.4) · bulk import (5.5) · public-chain anchoring (3.5) · SOC 2 audit.

---

## 8. What to deliberately not build

Scope discipline matters as much as scope.

- **Per-transaction blockchain anchoring.** Daily batched Merkle roots (3.5) provide the same third-party verifiability at a fraction of the cost, without leaking transaction volume and timing. Per-transaction anchoring is a marketing feature, not a security one.
- **Custom cryptography of any kind.** The current AES-256-GCM usage is correct precisely because it uses `cryptography`'s AEAD primitives directly. Keep it that way. The one place a bespoke construction is emerging — chunked encryption for streaming ([SAHA-031](AUDIT.md)) — should use an established streaming AEAD framing, not an invented one.
- **Holding registry filing credentials** (4.5). Generate documents for counsel to file. Avoids an entire trust boundary and fits the lawyer-led model.
- **Client-side E2E encryption for vault documents — for now.** Attractive for the subpoena posture ([THREAT-MODEL ADV-8](THREAT-MODEL.md)), but it breaks server-side watermarking, malware scanning and view-only rendering, all of which are higher-value today. Revisit after 2.4, as a per-deal option rather than a default.
- **Direct off-platform contact features.** The contact-info blocking in negotiation is a deliberate product decision; note that [SAHA-016](AUDIT.md) currently undermines it by publishing the same emails elsewhere. Resolve the contradiction in favour of blocking.
