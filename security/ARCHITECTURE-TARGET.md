# Saha — Target Architecture

> **2026-11-01 context:** This document preserves the earlier audit/plan and its recorded evidence. It is not a current host probe or completed-feature inventory. See [Current security boundaries](CURRENT-SECURITY.md), [release evidence](../docs/CURRENT-STATUS.md) and the [open-collaboration plan](../docs/OPEN-INNOVATION-PLAN.md). Use the current hosting runbook for deployments; retain the historical findings below.

**Version:** 1.0 · **Date:** 2026-08-05
**Companions:** [RECON.md](RECON.md) (current state) · [THREAT-MODEL.md](THREAT-MODEL.md) · [AUDIT.md](AUDIT.md) · [ROADMAP.md](ROADMAP.md)

**Premise.** Saha is the **confidentiality, coordination and evidence layer** for IP transactions whose legal effect occurs at government registries and whose handover is owned by lawyers. The architecture must therefore optimise for three properties in this order:

1. **Confidential content is disclosed only to whom it should be, when it should be** — enforced at storage, not only at the API.
2. **Every material act is provable to a third party without trusting Saha.**
3. **Saha holds as little as possible** — because a global platform faces every legal demand regime at once, and the only reliable answer to a demand is not holding the data.

Everything below serves those three. Where a design choice trades operational convenience for one of them, it does — deliberately, and it is flagged.

---

## 1. Current state, summarised

Single Jetson Orin Nano on a shared network. Cloudflare Tunnel → nginx :80 → uvicorn (2 workers) → native Postgres + six Docker containers, **five of which listen on `0.0.0.0` with default or absent credentials**. No IaC, no CI, no secrets management, no backups, no monitoring alerts, no DR. Single global encryption key — currently the placeholder committed to the repository.

Genuine strengths worth preserving through migration: an explicit transaction state machine; provider-agnostic AI routing with per-function policy hooks; a strict middleware stack (CSP, nosniff, frame-deny, body-size guard, request-id propagation, universal rate limiting); AES-GCM used correctly via `cryptography`'s AEAD primitives; UUIDv4 identifiers throughout; refresh-token rotation with family reuse detection; teaser-only vector payloads. **The application-layer engineering is good. The failures are at the boundaries and in configuration.**

---

## 2. Target: trust boundaries and data flow

```
                          ┌─────────────────────────────────────────┐
                          │  PUBLIC INTERNET                        │
                          └──────────────────┬──────────────────────┘
                                             │ TLS 1.3
                          ┌──────────────────▼──────────────────────┐
        TB-1 ═════════════│  Azure Front Door + WAF                 │
                          │  DDoS, bot mgmt, geo/sanctions routing  │
                          └──────────────────┬──────────────────────┘
                                             │ private link
   ┌─────────────────────────────────────────▼──────────────────────────────────┐
   │  GLOBAL CONTROL PLANE  (single region, e.g. West Europe)                    │
   │  · Entra ID (auth, MFA, conditional access)                                 │
   │  · Key Vault Managed HSM — KEK custody                                      │
   │  · Evidence service — hash chain, Merkle roots, RFC 3161, Confidential      │
   │    Ledger digests                                                           │
   │  · Global directory: pseudonymous user ids, org ids, region assignment      │
   │    ── NO confidential content, NO document bytes, NO raw PII ──             │
   └───────────┬────────────────────────────┬────────────────────┬──────────────┘
               │                            │                    │
   ┌───────────▼──────────┐   ┌─────────────▼────────┐  ┌────────▼─────────────┐
   │ REGIONAL PLANE — EU  │   │ REGIONAL PLANE — NA  │  │ REGIONAL PLANE — APAC│
   │ (data residency)     │   │                      │  │                      │
   │ ┌──────────────────┐ │   │  identical topology  │  │  identical topology  │
   │ │ App (Container   │ │   │                      │  │                      │
   │ │ Apps, managed id)│ │   │                      │  │                      │
   │ └────┬──────┬──────┘ │   └──────────────────────┘  └──────────────────────┘
   │      │      │        │
   │ TB-6 │      │ TB-7   │   ══ all traffic below is private endpoint only ══
   │ ┌────▼───┐ ┌▼──────────────────┐ ┌──────────────┐ ┌────────────────────┐
   │ │Postgres│ │ Blob Storage      │ │ Cache/Redis  │ │ AI Inference       │
   │ │Flexible│ │ · vault/ (CMK)    │ │ (TLS, AAD)   │ │ (confidential VM,  │
   │ │(CMK,   │ │ · contracts/(CMK) │ │ ephemeral    │ │  self-hosted, no   │
   │ │ RLS)   │ │ · immutable/(WORM)│ │ ≤1h TTL      │ │  egress)   TB-9    │
   │ └────────┘ └───────────────────┘ └──────────────┘ └────────────────────┘
   │                                                                            │
   │  Per-tenant DEK, wrapped by regional KEK in Managed HSM                     │
   └────────────────────────────────────────────────────────────────────────────┘
                                             │
   ┌─────────────────────────────────────────▼──────────────────────────────────┐
   │  EXTERNAL (TB-8) — egress allow-list, no wildcards, per-destination policy  │
   │  Stripe/escrow · e-signature · Persona/KYB · sanctions screening ·          │
   │  USPTO/CIPO/EUIPO/WIPO (read-only, strict schema) · RFC 3161 TSA · SMTP     │
   └────────────────────────────────────────────────────────────────────────────┘
```

### Boundary-by-boundary changes

| Boundary | Today | Target |
|---|---|---|
| **TB-1** Internet → app | Cloudflare Tunnel → nginx :80, no WAF rules | Front Door + WAF, managed rules + custom rules for enumeration patterns, geo routing for sanctions and residency |
| **TB-2** Unauth → auth | Per-handler `Depends`, scattered | Router-level default-deny; central policy module; route-inventory test in CI |
| **TB-3** Auth → verified | Self-serve mock KYC | Real KYC/KYB + sanctions/PEP, evidence-recorded, mock impossible outside `development` |
| **TB-4** Member → member | Six hand-rolled predicates | One `authorize(actor, action, resource)` decision table; org-scoped from the start |
| **TB-5** Member → admin | Correct, but token in `localStorage` | MFA-enforced, step-up for destructive actions, conditional access, memory-only tokens |
| **TB-6** App → DB | One role, full DML, no RLS | Managed identity; separate app / audit-writer (INSERT-only) / reporting (read-only) roles; RLS on owner-scoped tables; CMK encryption; private endpoint |
| **TB-7** App → storage | Root credentials, one bucket, one global key | Managed identity; per-prefix scoped access; per-tenant DEKs wrapped by Managed HSM KEK; versioning + immutability policy on `immutable/`; private endpoint |
| **TB-8** App → third party | Unrestricted egress, `.env` secrets | Egress allow-list; secrets from Key Vault via managed identity; no long-lived credentials anywhere |
| **TB-9** Content → inference | Trade secrets to NVIDIA/Anthropic | Self-hosted inference on confidential-computing VMs, **no egress**; external providers only for tier 🟢/🟡 with a DPA |
| **TB-10** LAN → data plane | Five services on `0.0.0.0`, defaults | Does not exist — no public IPs, private endpoints only, no LAN concept |
| **TB-11** Tenant → tenant | No tenancy | Organisation model with per-tenant key isolation and org-scoped authorization |

---

## 3. Tenancy and isolation

Introduce the organisation as a first-class entity — required by KYB ([ROADMAP §1.4](ROADMAP.md)) and by broker/portfolio features, and cheaper to build now than to retrofit.

**Model.** Org → members (with roles) → assets. Every confidential resource carries an `org_id`. Authorization is `(actor_org, actor_role, resource_org, resource_type, action)`. Users may belong to multiple orgs with an explicit active-org context; cross-org visibility is never implicit.

**Isolation strategy — deliberate choice:** *shared database, shared schema, row-level security + per-tenant encryption keys.*

Rejected alternatives and why: database-per-tenant is operationally disproportionate at expected scale; schema-per-tenant complicates migrations without materially improving isolation given RLS. The chosen model gets most of the isolation benefit at a fraction of the cost — **and the per-tenant DEK is what actually contains a breach**, since a query-layer bug that crosses tenants still yields ciphertext the attacker cannot decrypt. RLS is defence in depth; the key boundary is the real one.

---

## 4. Key management

The current design — one global key derived from an env var that is the repo's published placeholder ([SAHA-001](AUDIT.md)) — must not survive migration.

**Hierarchy.**
```
Azure Key Vault Managed HSM (FIPS 140-3 Level 3)
└── Regional KEK (per data plane; non-exportable; HSM-backed)
    └── Tenant DEK (per organisation; wrapped by KEK; stored wrapped in DB)
        └── Object keys (per document; derived or wrapped by tenant DEK)
```

**Properties.**
- Application **never** sees the KEK. It requests unwrap operations via managed identity; every operation is logged in Key Vault.
- Object key ids and versions are recorded per object (`encryption_key_id` already exists on `IPVaultAsset` — the field is right, only its use is wrong).
- **Rotation:** KEK annually or on incident, via HSM rotation with no re-encryption of data. Tenant DEK on tenant request or incident, requiring re-wrap only (cheap). Object keys never rotate — objects are re-encrypted only on key compromise.
- **Access to unwrap** is itself an auditable, alertable event. Bulk unwrap requests are a mass-exfiltration signal and should page.

**The escrow question — decide explicitly, with counsel.** If tenant DEKs are wrapped by a customer-managed KEK and the customer loses it, their documents are unrecoverable. Three options, in order of preference:

| Option | Saha can decrypt? | Trade-off |
|---|---|---|
| **A. Saha-managed KEK** (recommended to start) | Yes | Recovery possible; Saha is compelled-disclosure-capable and inside the TCB. Simplest and honest — say so plainly in the privacy notice |
| **B. Customer-managed KEK, no escrow** | No | Strongest posture; permanent loss on customer key loss; enterprise buyers may still demand it |
| **C. Customer-managed KEK with split-knowledge escrow** (M-of-N shares across independent custodians) | Only via quorum | Best balance; meaningfully more operational complexity |

**Recommendation:** ship A; offer B as an enterprise option once tenancy exists; build C only if a customer requires it. **Do not default to B without a documented recovery conversation** — silent permanent data loss is a worse outcome than a documented disclosure posture.

---

## 5. Zero-trust networking

- **No public IPs on any data service.** Postgres, Blob, Redis, Qdrant/AI Search, inference — private endpoints only, public network access disabled at the resource level (not just by firewall rule).
- **Service-to-service auth via managed identity.** No connection strings, no access keys, no `.env` secrets in the compute layer. This eliminates [SAHA-002](AUDIT.md) as a *category*, not as an instance.
- **Egress allow-list** per destination. Today egress is unrestricted, which is why [SAHA-013](AUDIT.md) is invisible at the network layer — an allow-list makes such a flow a deployment-time decision rather than a code-time accident.
- **Network segmentation:** app subnet → data subnet with explicit NSG rules; the inference subnet has **no egress at all**.
- **Admin plane** behind Entra ID conditional access — device compliance, named locations, MFA — not merely LAN-only.
- Cloudflare Tunnel is a reasonable interim while on-premises; it should not survive migration.

---

## 6. Secrets management

No long-lived credential anywhere in the pipeline.

| Where | Today | Target |
|---|---|---|
| App → DB / storage / cache | `.env` credentials | Managed identity, no secret |
| Third-party API keys | `.env` | Key Vault references, rotated, access-audited |
| CI → cloud | n/a (no CI) | OIDC federated credentials — no stored cloud secret |
| Local development | `.env` | `.env` with **development-only** values; CI-enforced check that no dev default appears in any deployed config |

Add `gitleaks` in CI over full history ([REMEDIATION-PLAN §5](REMEDIATION-PLAN.md)). History is clean today; keep it that way.

---

## 7. Confidential computing

The directive asks which workloads warrant enclave-backed execution beyond the ledger. Honest answer: **two, and only two.**

1. **AI inference over confidential content.** This is the strongest case. Today trade secrets are POSTed to a third-party API ([SAHA-013](AUDIT.md)). Target: self-hosted models on confidential VMs (AMD SEV-SNP / Intel TDX), memory encrypted, no egress, attestation verified before any confidential prompt is dispatched. This removes an entire class of disclosure rather than mitigating it.
2. **Evidence digest signing.** Azure Confidential Ledger for tamper-evident receipts that exclude the cloud operator from the TCB ([ROADMAP §3.4](ROADMAP.md)).

**Not warranted:** the general application tier. Confidential computing protects against a malicious *host*; Saha's realistic adversaries are network-adjacent attackers, application flaws, and insiders with legitimate credentials. Enclaves address none of those, and the operational cost is real. Say no to it for the app tier and spend the effort on §4 and §9 instead.

---

## 8. Multi-region and disaster recovery

**Today: no backups exist.** Nothing on the host or in the repo configures them. This is the largest unaddressed operational risk in the system and it is not in the findings list because it is not a *security* finding — it is an existential one.

**Targets** (proposed; confirm against business tolerance):

| Metric | Target | Mechanism |
|---|---|---|
| RPO — transactional data | 5 min | Postgres Flexible Server PITR + geo-redundant backup |
| RPO — documents | 15 min | Blob GRS with versioning |
| RTO — regional outage | 4 h | Warm standby in the paired region; documented failover runbook |
| RTO — full loss | 24 h | IaC redeploy + restore from geo-redundant backup |
| Evidence chain | **Zero loss tolerance** | Append-only + immutable storage + external RFC 3161 anchors — the chain is independently verifiable even if the database is lost |

**Restore testing quarterly, with evidence retained** — an untested backup is a hypothesis, and SOC 2 will ask for the test results.

---

## 9. Observability

Today: Prometheus + Loki + Grafana are deployed with **no security metrics and no alerts** ([SAHA-024](AUDIT.md)). Nothing in this entire audit would have been noticed.

**Target.**
- **Structured logging with PII scrubbing** — JSON in every internet-facing environment (blocked today by [SAHA-005](AUDIT.md)); a scrubbing processor with an allow-list of loggable fields, never a denylist; request-id correlation already exists and is good.
- **Distributed tracing** — OpenTelemetry to Application Insights, sampled, with document content and tokens excluded from span attributes by policy.
- **Security event pipeline** — audit events → Microsoft Sentinel with these detections as a minimum:

| Detection | Signal | Severity |
|---|---|---|
| Mass document download | >N downloads per actor per hour, or >N distinct documents | Page |
| Enumeration | High 403/404 rate per actor or IP | Alert |
| Privilege change | Any role or KYC-status change | Page |
| Failed-authorization spike | 403 rate above baseline | Alert |
| Bulk key unwrap | Key Vault unwrap volume above baseline | **Page** |
| Audit-chain break | Verification failure | **Page** |
| Admin action outside hours / new location | Conditional-access signal | Alert |
| Disclosure without NDA | Document access with no matching NDA record | **Page** |

- **Retention:** security events 1 year hot, 7 years cold (align with SOC 2 and evidentiary needs); application logs 90 days; **evidence chain forever**.
- **Alert routing to a channel a human actually reads.** A dashboard nobody opens is not detection.

---

## 10. SOC 2 Type II readiness

Type II requires an observation window (typically 3–12 months) during which controls **operate** — so the timeline is dominated by the window, not the build.

**Control gaps by Trust Services Criterion:**

| Criterion | Gap | Fixed by |
|---|---|---|
| CC6.1 Logical access | Scattered authorization; no default-deny | [REMEDIATION-PLAN 3.1](REMEDIATION-PLAN.md) |
| CC6.1 | MFA not enforced for privileged access | 2.4 |
| CC6.6 Boundary protection | Data services on `0.0.0.0` with defaults | Tier 0, §5 |
| CC6.7 Encryption | Key is a repo-published default; no rotation | 1.2, §4 |
| CC7.2 Monitoring | No security alerting | 3.7, §9 |
| CC7.3 Incident response | No runbook, no tested process | 3.7 |
| CC8.1 Change management | No CI, no review gate, no deployment record | 2.5 |
| A1.2 Availability | No backups, no DR, no restore testing | §8 |
| C1.1 Confidentiality | No tiered disclosure; no NDA enforcement | [ROADMAP §2](ROADMAP.md) |
| P-series Privacy | No retention, deletion, or export | 3.6 |

**Evidence collection to automate** (manual evidence is what makes audits expensive): access reviews from Entra ID; change management from GitHub (PR approvals, CI results, deployment records); vulnerability management from CI scanner output; backup/restore test results; security-alert response times; onboarding/offboarding records.

**Realistic timeline:** Q1–Q3 build controls → Q4 begin observation → **Type II report ~Q3 of the following year**. A Type I (design-only, point-in-time) is achievable ~6 months earlier and is often enough to unblock the first enterprise deals — worth considering as an interim.

---

## 11. Penetration testing

**Do not test the current state.** An engagement now would rediscover this document at consulting rates. Complete [REMEDIATION-PLAN](REMEDIATION-PLAN.md) Tiers 0–2 first.

**First engagement — after Tier 2 (target Q2):** authenticated grey-box against the API. Scope: authorization boundaries (the [SAHA-007](AUDIT.md) class), the document-access path, the transaction state machine and business logic, tenant isolation once it exists, and the auth/session model. Explicitly out of scope: Azure platform controls.

**Second — after Q3 features:** full black-box including the disclosure tiers, data rooms, watermarking and the document-rendering pipeline. That pipeline ([ROADMAP §2.4](ROADMAP.md)) will be the newest and most dangerous code in the system — it parses hostile documents — and deserves dedicated fuzzing.

**Cadence thereafter:** annual full-scope, plus targeted testing on any new trust boundary (escrow provider, e-signature, registry integration, new region).

**Fix before the first engagement,** or the report is padded with what you already knew: everything in Tiers 0–2, plus the CI pipeline so fixes hold.

---

## 12. Migration sequencing

Ordered to avoid building anything twice, and to avoid a migration that carries the current defects into a more expensive environment.

| Phase | Work | Notes |
|---|---|---|
| **M0** | [REMEDIATION-PLAN](REMEDIATION-PLAN.md) Tiers 0–1 **on the current host** | Do not migrate a compromisable system. Tier 0 is two hours |
| **M1** | IaC from day one (Bicep or Terraform), CI/CD with OIDC, no click-ops | The current infrastructure has no IaC; the migration is the only cheap moment to fix that |
| **M2** | Data plane: Postgres Flexible Server (CMK, private endpoint), Blob (CMK, versioning, immutability), Key Vault Managed HSM, Cache | §4 key hierarchy from the start — **do not migrate the single global key** |
| **M3** | App tier: Container Apps with managed identity; zero stored credentials | §5, §6 |
| **M4** | Self-hosted inference on confidential VMs; cut over from NVIDIA/Anthropic for confidential tiers | Closes [SAHA-013](AUDIT.md) structurally |
| **M5** | Observability, Sentinel, alert routing, backup and restore testing | §8, §9 |
| **M6** | Regional data planes as markets require | §2, [ROADMAP §6](ROADMAP.md) |

**Two rules for the migration.** First: **fix Tier 0 before migrating** — a lift-and-shift of the current configuration would place default credentials and a published encryption key onto infrastructure that costs money to run and is harder to reason about. Second: **the migration is the one cheap moment for key management, IaC and managed identity.** Retrofitting any of the three afterwards costs multiples. Do them as part of the move, not after it.
