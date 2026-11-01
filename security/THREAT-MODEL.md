# Saha — Threat Model

> **2026-11-01 context:** This document preserves the earlier audit/plan and its recorded evidence. It is not a current host probe or completed-feature inventory. See [Current security boundaries](CURRENT-SECURITY.md), [release evidence](../docs/CURRENT-STATUS.md) and the [open-collaboration plan](../docs/OPEN-INNOVATION-PLAN.md). Use the current hosting runbook for deployments; retain the historical findings below.

**Version:** 1.0 · **Date:** 2026-08-05 · **Scope:** `apps/backend`, `apps/frontend`, `apps/admin`, live Jetson deployment
**Companion documents:** [RECON.md](RECON.md) (system map) · [AUDIT.md](AUDIT.md) (findings) · [ARCHITECTURE-TARGET.md](ARCHITECTURE-TARGET.md)

---

## 1. What we are protecting, and why it is unusual

Most marketplaces protect *money* and *PII*. Saha protects something with a property neither of those has: **IP confidentiality is not recoverable.** A stolen credit card is cancelled. A leaked unfiled patent claim destroys novelty permanently and in every jurisdiction simultaneously — the disclosure *is* the loss, and no incident response undoes it.

Three consequences shape everything below:

1. **Read-only compromise is terminal.** For most systems, confidentiality breaches rank below integrity breaches. Here it inverts. An attacker who only *reads* the vault has already achieved maximum impact.
2. **The platform is not the source of legal truth.** Title transfers at USPTO/CIPO/EUIPO/WIPO, and per the product owner's direction, lawyers own the handover. Saha's job is to **record, evidence and facilitate** — which makes *evidentiary integrity* a primary security property, not a nice-to-have. If Saha's records can't be trusted in a dispute, the platform has no reason to exist.
3. **Global reach multiplies the legal surface.** Confirmed direction: worldwide platform. That means GDPR/UK GDPR, PIPEDA, CCPA/CPRA and US state law, LGPD, PIPL, APPI, PDPA, DPDP, POPIA — *simultaneously* — plus sanctions screening (OFAC/EU/UN), export control on dual-use technical data (EAR/ITAR, Wassenaar), and trade-secret regimes (DTSA, EU Trade Secrets Directive). Several of these are in direct tension with each other. See §6.

### Asset ranking

| Rank | Asset | Where it lives | Loss if disclosed |
|---|---|---|---|
| **A1** | Vault documents (unfiled claims, unpublished applications, process docs) | MinIO `vault/` (ciphertext), `ip_vault_assets` | Terminal — novelty destroyed, trade secret extinguished |
| **A2** | Bill of Materials + private listing description | `bom_items`, `ip_listings.description` | Terminal — the recipe *is* the invention |
| **A3** | AI authoring transcripts (creator describing the invention) | Redis `bom:session:*` **plaintext**, NVIDIA API | Terminal, and the least-defended asset in the system |
| **A4** | Negotiation content + deal terms | `messages` (ciphertext), `proposals`, `transactions` | Severe — reveals valuation, strategy, counterparties |
| **A5** | Evidentiary record | `audit_logs` | Severe — no disputes are winnable without it |
| **A6** | Identity & KYC state | `users` | Severe — the trust anchor for every other control |
| **A7** | Member PII (emails, names) | `users`, exposed via materials/community reads | Moderate — regulatory + competitive-intelligence value |

---

## 2. STRIDE per trust boundary

Boundary IDs match [RECON.md §2](RECON.md). ✅ mitigated · ⚠️ partial · 🔴 unmitigated. Finding IDs link to [AUDIT.md](AUDIT.md).

### TB-1 · Internet → application (Cloudflare → nginx :80 → uvicorn)

| STRIDE | Threat | Status |
|---|---|---|
| Spoofing | Client forges `X-Forwarded-For`; nginx *appends*, backend reads element `[0]` | 🔴 **SAHA-011** |
| Tampering | Request tampering in transit | ✅ TLS to Cloudflare edge |
| Repudiation | Attacker-controlled IP in audit records | 🔴 **SAHA-011** |
| Information disclosure | `/health` enumerates every backend component and echoes exception text | 🔴 **SAHA-019** |
| Denial of service | 1000/min default limit, per-IP key spoofable; uploads and downloads fully buffered in memory | ⚠️ **SAHA-011**, **SAHA-031** |
| Elevation | — | ✅ no path |

### TB-2 · Unauthenticated → authenticated

| STRIDE | Threat | Status |
|---|---|---|
| Spoofing | JWT forgery | ✅ HS256 fixed-list, 64-hex-char `SECRET_KEY`, `type` claim checked |
| Spoofing | Credential stuffing | ✅ bcrypt-12, lockout after 5, timing-equalised enumeration defence |
| Tampering | Token replay after logout | ⚠️ access token valid to expiry (15 min); acceptable |
| Repudiation | — | ✅ login/logout audited |
| Information disclosure | **Trade-secret-tier data served with no authentication at all** | 🔴 **SAHA-003** |
| DoS | Registration flooding | ⚠️ 10/min, IP-keyed → spoofable |
| Elevation | Self-registration as `admin`/`legal` | ✅ blocked at schema (`_SELF_REGISTER_ROLES`) |

### TB-3 · Authenticated → KYC-verified

| STRIDE | Threat | Status |
|---|---|---|
| Spoofing | **Self-approval of KYC via mock endpoint; webhook signature check returns `True` unconditionally** | 🔴 **SAHA-004** |
| Elevation | Verified status unlocks listing creation, proposals, transactions, vault download | 🔴 gate is satisfiable by any anonymous registrant |
| Repudiation | No PEP/sanctions screening, no KYB for entities, no evidence trail behind verification | 🔴 **SAHA-029** |

### TB-4 · Member → member (horizontal)

| STRIDE | Threat | Status |
|---|---|---|
| Tampering | IDOR on vault assets | ✅ lookup scoped by `listing_id == transaction.listing_id` |
| Tampering | IDOR on listings/proposals/transactions/materials/communities | ✅ ownership checked in every handler |
| Elevation | **Seller releases escrow to self** (`_check_access` where `_check_buyer` belongs) | 🔴 **SAHA-007** |
| Elevation | **Either party unilaterally executes the contract** | 🔴 **SAHA-008** |
| Elevation | Self-acceptance of own offer | ✅ blocked (`proposals.py:150-160`) |
| Information disclosure | Bulk seller/member email harvesting | 🔴 **SAHA-016** |
| Information disclosure | Platform-wide demand intelligence to any verified member | ⚠️ **SAHA-033** |
| Repudiation | No record of *who* signed, no signature artefact | 🔴 **SAHA-008**, **SAHA-014** |

### TB-5 · Member → admin (vertical)

| STRIDE | Threat | Status |
|---|---|---|
| Elevation | Privilege escalation to admin | ✅ `require_admin` on all 24 routes; same authz model, no bypass |
| Tampering | Admin self-demotion / self-deactivation | ✅ guarded |
| Spoofing | **Admin refresh token persisted to `localStorage`** | 🔴 **SAHA-009** |
| Repudiation | Admin actions untraceable | ⚠️ all audited — into a mutable table (**SAHA-014**) |
| Elevation | Admin console reachable from internet | ✅ cloudflared 404s it; nginx :8080 LAN-only |

### TB-6 · Application → database

| STRIDE | Threat | Status |
|---|---|---|
| Tampering | SQL injection | ✅ fully parameterised — verified exhaustively |
| Tampering | **Operator rewrites `audit_logs` undetectably** | 🔴 **SAHA-014** |
| Information disclosure | Single role with full DML on every table; no RLS, no least privilege | 🔴 **SAHA-034** |
| DoS | Unbounded pagination `offset` | ⚠️ **SAHA-003** |

### TB-7 · Application → object storage

| STRIDE | Threat | Status |
|---|---|---|
| Spoofing | **MinIO reachable on `0.0.0.0` with `minioadmin`/`minioadmin` on a shared network** | 🔴 **SAHA-002** |
| Information disclosure | **`VAULT_ENCRYPTION_KEY` is the placeholder committed to the repo** | 🔴 **SAHA-001** |
| Information disclosure | Contracts stored unencrypted alongside encrypted vault objects | 🔴 **SAHA-021** |
| Tampering | No object lock, no versioning, no integrity verification on read | 🔴 **SAHA-021** |
| Elevation | Application holds storage root credentials | 🔴 **SAHA-002** |

### TB-8/TB-9 · Application → third parties, and → LLM inference

| STRIDE | Threat | Status |
|---|---|---|
| Information disclosure | **A3/A4 plaintext POSTed to NVIDIA and Anthropic** — no DPA, no disclosure, no opt-out, no residency control | 🔴 **SAHA-013** |
| Spoofing | Persona webhook accepts anything in mock mode | 🔴 **SAHA-004** |
| Spoofing | Stripe webhook | ✅ HMAC + `compare_digest` + 300s replay window |
| Tampering | Prompt injection via listing/message content steering the classifier or contract draft | ⚠️ **SAHA-035** |
| Information disclosure | SMTP `start_tls=False` hardcoded | 🔴 **SAHA-027** |

### TB-10 · Shared network → data plane

| STRIDE | Threat | Status |
|---|---|---|
| Spoofing | Redis, Qdrant, Prometheus, Loki — **no authentication whatsoever** | 🔴 **SAHA-012**, **SAHA-028** |
| Information disclosure | **Mailpit UI on `0.0.0.0:8025` — every platform email readable** | 🔴 **SAHA-006** |
| Information disclosure | **Redis holds A3 (invention transcripts) in plaintext** | 🔴 **SAHA-012** |
| Elevation | Grafana `admin`/`admin` | 🔴 **SAHA-028** |
| Tampering | Anyone on the network can write to Redis/Qdrant/MinIO | 🔴 **SAHA-002**, **SAHA-012** |

### TB-11 · Tenant → tenant
**Not applicable.** No tenancy model exists; Saha is single-tenant with per-user ownership. This is a roadmap gap (enterprise/portfolio sellers, law-firm workspaces, broker orgs) rather than a vulnerability. Flagged because a global platform with corporate sellers *will* need it, and retrofitting tenancy onto per-user ownership is expensive — see [ARCHITECTURE-TARGET.md §3](ARCHITECTURE-TARGET.md).

---

## 3. Adversaries — attack paths through the actual code

> Paths are described precisely enough to reproduce locally. No weaponised tooling is provided, and none is needed: every path below is a sequence of ordinary API calls or standard client connections.

### ADV-1 · Authenticated buyer reading a seller's confidential filings without an NDA

**Verdict: succeeds trivially — and does not need to be a buyer, or authenticated.**

There is no NDA in the system. `ProposalStatus.NDA_PENDING`/`NDA_SIGNED`, `nda_docusign_envelope_id`, and `nda_signed_at` exist in the schema; **no code path writes any of them** (grep-confirmed across the backend). Disclosure is gated on *escrow funded*, not on NDA execution.

But the buyer needn't get that far. `ListingResponse` (`app/api/schemas/listing.py:52-70`) embeds `description`, `bom_items[]`, `equipment_requirements`, `batch_size_definition`, and `vault_assets[]`. `GET /api/v1/listings/{id}` (`app/api/listings.py:84-107`) uses `get_optional_user`, and nginx proxies `/api/` to the internet.

```
GET https://sahasolutions.com/api/v1/listings/{id}     # no Authorization header
→ 200, full BOM with specifications, quantities, criticality flags,
        plus the creator's private `description`
```

Verified empirically against the running instance during recon. Only the *file bytes* are protected; the recipe is public. → **SAHA-003**

For the file bytes, the path is longer but open: register → self-verify KYC (**SAHA-004**) → propose → seller accepts → `/escrow/create` → `/escrow/confirm`. Because Stripe is in mock mode (confirmed), `confirm_escrow_funded` marks escrow funded with **no money moving** (`app/services/settlement.py:60-62`), and `_assert_vault_access` then admits the buyer to every vault file. → **SAHA-004** + **SAHA-036**

### ADV-2 · Competitor harvesting the corpus to map unfiled IP positions

**Verdict: succeeds, unauthenticated, at machine speed.**

```
GET /api/v1/listings/public?limit=100&offset=0,100,200…
```
`limit` is capped at 100 (`app/api/listings.py:81`); `offset` is **unbounded and unvalidated**. The only throttle is the 1000/min default limit, keyed on a spoofable `X-Forwarded-For` (**SAHA-011**). Each row carries the complete BOM. A competitor reconstructs every listed invention's material set, supplier requirements, and equipment needs — then cross-references `POST /api/v1/search` (also `get_optional_user`) and `GET /api/v1/demand/overview` (any verified member) to learn *what buyers are hunting for and failing to find*: a direct readout of unmet market demand and, by inference, where unfiled positions are being staked.

Add `GET /api/v1/materials` (seller emails) and `GET /api/v1/communities/{id}/members` (member emails) and the same actor walks away with a targeted outreach list. → **SAHA-003**, **SAHA-016**, **SAHA-033**

### ADV-3 · Malicious seller listing IP they do not own, or double-listing

**Verdict: succeeds — nothing prevents it.**

`create_listing` (`app/services/listings.py:26-42`) records `title`, `product_category`, `description` and nothing else. There is:
- no chain-of-title check against USPTO/CIPO assignment records,
- no ownership attestation, no evidence trail,
- no encumbrance disclosure (existing licences, security interests, litigation, SEP commitments),
- no duplicate detection across listings,
- no exclusivity lock — `_VALID_TRANSITIONS` (`app/services/transactions.py:29-41`) permits *N* concurrent transactions on one `listing_id`, and `create_proposal` blocks only a *second proposal by the same buyer*.

A seller can run parallel deals to `ESCROW_FUNDED` on the same asset and collect from several buyers. With mock Stripe there is no money, but the **vault is released to every one of them**. This is the highest-impact business-logic gap in the system. → **SAHA-037**, **SAHA-038**

### ADV-4 · Insider with database or storage access

**Verdict: succeeds completely, and leaves no evidence.**

Encryption at rest is defeated by design today. `_derive_key()` = `SHA-256(settings.VAULT_ENCRYPTION_KEY)` (`app/services/vault.py:18-19`), and that setting is **the placeholder string from `.env.example`, which is committed to git** (confirmed by non-disclosing comparison). The same key encrypts negotiation messages (`app/services/messages.py:16`). So:

- DB access alone → all deal terms, PII, KYC status, offer history in cleartext.
- Storage access alone → all vault ciphertext, decryptable with a key published in the repo; contracts are not even encrypted.
- Either → `audit_logs` is an ordinary table owned by the same role the app uses. `UPDATE`/`DELETE` succeed. No hash chain, no WORM, no signatures, no external anchor. **History is rewritable without detection.**

There is no separation between the application identity and the storage-root identity, no per-tenant key isolation, no HSM, no key rotation (`KEY_VERSION = "v1"` is a constant that has never changed). → **SAHA-001**, **SAHA-002**, **SAHA-014**

### ADV-5 · Repudiating a transaction, or forging evidence that one occurred

**Verdict: succeeds — the evidentiary layer does not exist.**

Repudiation is easy because nothing binds a party to an act:
- `POST /{id}/sign` (`app/api/transactions.py:107-124`) flips `CONTRACT_REVIEW → SIGNED` when **either** party calls it. The transaction records `contract_docusign_envelope_id` — always `NULL`, because DocuSign is a `logger.info` stub (`app/services/transactions.py:200-207`). Nothing records who signed, when, from where, or *what they signed*.
- The contract is an **LLM-generated text file** in MinIO, unencrypted, unhashed, unsigned, with no canonical serialisation and no integrity check on read. It can be replaced in place with no trace.
- `audit_logs` entries are written via `BackgroundTasks` *after the response is sent* — a mid-task failure silently loses the record, and nothing reconciles.

Forging is equally easy for anyone with DB access: insert an `audit_logs` row with any `action`, `user_id`, `resource_id` and `created_at`. There is no signature to forge and no chain to break.

A party saying *"I never agreed to those terms"* cannot be contradicted by anything Saha holds. Given that lawyers own the handover and will rely on Saha's record as the evidentiary substrate, this is a **product-existential** gap, not merely a security one. → **SAHA-008**, **SAHA-014**, **SAHA-021**

### ADV-6 · Automated scraper enumerating IDs

**Verdict: partially blocked — the one place IDs are actually protected.**

All identifiers are UUIDv4 (`default=uuid.uuid4` on every model), so blind enumeration of listing, document, transaction, proposal and user IDs is infeasible. Ownership checks are present on every ID-addressed resource, and vault assets are additionally scoped to the transaction's listing. Credit where due.

The scraper does not need enumeration, though: `/api/v1/listings/public` **hands over the corpus with an index**. And `GET /api/v1/users/{user_id}/avatar` plus `GET /api/v1/users/{user_id}/reputation` accept any UUID — harmless alone, but they turn UUIDs harvested from listing/community/materials responses into a member profile graph. → **SAHA-003**, **SAHA-016**

### ADV-7 · Compromised dependency or CI/CD credential

**Verdict: CI/CD risk is nil (no CI exists). Dependency risk is unmanaged.**

There is no `.github/`, no pipeline definition anywhere in the repo — so there is no pipeline to compromise and no privileged CI identity to steal. That is a real reduction in attack surface, and also why **no fix is currently enforced anywhere**: 129 tests exist and nothing runs them.

Dependency exposure: lockfiles are present and complete (`uv.lock`, pnpm lockfiles), pinning transitive versions. But no scanner has ever run, and `pyproject.toml` uses floating `>=` lower bounds, so any unlocked rebuild pulls newer code silently. `python-jose` — the JWT implementation for the entire auth system — has been effectively unmaintained since 2021. Deployment is `git pull` + manual `systemctl restart`, so a malicious dependency reaches production without review. **No CVE is asserted here; none has been verified.** → **SAHA-023**, **SAHA-026**

### ADV-8 · Subpoena or law-enforcement demand

**Verdict: Saha is currently obliged to produce almost everything, because it holds almost everything in a readable form.**

A lawful demand today compels production of: every vault document (Saha holds the key), every negotiation message (same key), all deal terms, all identity and KYC state, complete search history per user (`demand_signals` retains `query_text` + `user_id` with **no expiry**), all AI transcripts still in Redis, and — via NVIDIA and Anthropic — content already transmitted to processors in other jurisdictions.

**What Saha should have designed itself out of holding:**

| Currently held | Should be | Why |
|---|---|---|
| Vault decryption keys | Customer-managed keys in Managed HSM; per-tenant isolation | Removes Saha from the disclosure path for the highest-value asset |
| Negotiation plaintext (server-decryptable) | Per-deal keys; consider client-side E2E for pre-contract exchange | Same |
| Indefinite per-user search history | Aggregate-only after 30 days; drop `user_id` | Behavioural profile with no retention justification |
| AI transcripts in Redis | Ephemeral, ≤1h TTL, never third-party | Contains the invention description |
| Content sent to third-party LLMs | Self-hosted inference for anything above 🟡 internal | Removes an entire class of cross-border disclosure |

Because the platform is **global**, a single demand may originate under any of a dozen regimes, and the conflicts are real: a PIPL data-localisation obligation and a US demand can be mutually unsatisfiable for the same record. The design answer is to **hold less**, not to arbitrate between regimes. → **SAHA-013**, **SAHA-025**, **SAHA-001**

---

## 4. Attack trees

### AT-1 · Obtain the plaintext of a target's vault documents (A1)

```
GOAL: read A1 plaintext
├── [1] Via the shared network  ── ★ CHEAPEST, NO ACCOUNT REQUIRED
│   ├── 1.1 Reach MinIO :9000/:9001 on 0.0.0.0            [SAHA-002]
│   ├── 1.2 Authenticate minioadmin/minioadmin            [SAHA-002]
│   ├── 1.3 Download all objects under vault/
│   └── 1.4 Decrypt: key = SHA-256("<placeholder from .env.example>")
│           — the string is committed to the repository   [SAHA-001]
│       ⇒ TOTAL COMPROMISE. Cost: minutes. Detection: none.
│
├── [2] Via the application (needs seller cooperation)
│   ├── 2.1 Register (open)
│   ├── 2.2 Self-verify KYC via mock endpoint             [SAHA-004]
│   ├── 2.3 Propose on target listing
│   ├── 2.4 ⟨seller accepts⟩                              ← only real obstacle
│   ├── 2.5 assign-law-firm → draft-contract → sign (unilateral) [SAHA-008]
│   ├── 2.6 escrow/create → escrow/confirm (mock: no money) [SAHA-036]
│   └── 2.7 GET /vault-access/{asset}/download (unthrottled) [SAHA-020]
│       ⇒ Full vault. Audited ✅ — into a mutable log      [SAHA-014]
│
├── [3] Via database access
│   └── 3.1 storage_key from ip_vault_assets → then [1.3]+[1.4]
│
└── [4] Without the files at all  ── ★ HIGHEST VALUE / LOWEST COST
    └── 4.1 GET /api/v1/listings/public — unauthenticated  [SAHA-003]
        ⇒ Full BOM + private description for every listing.
          For most assets the recipe IS the invention; the PDF is a formality.
```

**Reading of this tree:** branch [1] is a complete compromise requiring no account and no application interaction; branch [4] yields most of the value with a single unauthenticated HTTP GET. The application-layer controls in branch [2] — which is where all the engineering effort went — are the *least* efficient route an attacker would take.

### AT-2 · Become a trusted party without being one

```
GOAL: reach `verified` and transact
├── [1] KYC mock self-approval
│   └── register → /me/kyc/initiate → /me/kyc/complete    [SAHA-004]
│       ⇒ VERIFIED. Cost: 3 API calls. No rate limit on either endpoint. [SAHA-020]
├── [2] Forge the Persona webhook
│   └── verify_persona_webhook_signature() returns True unconditionally
│       when KYC_MOCK_MODE=true (integrations/kyc.py:55-56) [SAHA-004]
├── [3] Compromise an existing verified account
│   ├── 3.1 Steal the refresh cookie — no Secure flag; two http:// origins
│   │       whitelisted with allow_credentials=True        [SAHA-010]
│   ├── 3.2 XSS the admin console → refreshToken from localStorage → 7 days [SAHA-009]
│   └── 3.3 Credential stuffing → ✅ BLOCKED (bcrypt-12, lockout, MFA available)
└── [4] Self-register as admin → ✅ BLOCKED at schema
```

Note that **branch [4] — the one that was hardened — is the only one that fails.** Branches [1] and [2] exist because a single environment variable (`APP_ENV=staging`) disabled the boot guard that would have refused this configuration. → **SAHA-005**

### AT-3 · Repudiate or forge a transaction record

```
GOAL: deny an act, or fabricate one
├── [1] Deny signing
│   └── Nothing records WHO signed. Either party can flip CONTRACT_REVIEW→SIGNED.
│       DocuSign envelope id is always NULL.               [SAHA-008]
│       ⇒ Repudiation succeeds. Nothing contradicts it.
├── [2] Deny agreed terms
│   └── Contract is an unsigned, unhashed .txt in MinIO; replaceable in place. [SAHA-021]
├── [3] Fabricate an act
│   └── INSERT into audit_logs with arbitrary user_id/action/created_at.
│       No signature, no chain, no anchor.                 [SAHA-014]
└── [4] Erase an act
    ├── 4.1 DELETE from audit_logs — succeeds silently.    [SAHA-014]
    └── 4.2 Suppress the write: audit entries run in BackgroundTasks;
            `ip_address` is Postgres INET and takes the client-supplied
            X-Forwarded-For[0]. A non-IP value plausibly aborts the write.
            ⚠️ REQUIRES RUNTIME VERIFICATION — not asserted as fact. [SAHA-011]
```

---

## 5. Residual-risk ranking

Exploitability × business impact, per the directive — not CVSS order.

| # | Scenario | Likelihood | Impact | Composite |
|---|---|---|---|---|
| 1 | Corpus harvested unauthenticated (AT-1 [4]) | **Certain** — no barrier at all | Terminal | 🔴 **Critical** |
| 2 | Vault decrypted via LAN + committed key (AT-1 [1]) | **High** — shared network, published key | Terminal | 🔴 **Critical** |
| 3 | Trust chain bypassed via mock KYC (AT-2 [1]) | **Certain** | Severe | 🔴 **Critical** |
| 4 | Insider/operator rewrites history (ADV-4/5) | Medium | Severe — product-existential | 🔴 **Critical** |
| 5 | Seller self-releases escrow (ADV-3) | High once real money flows | Severe | 🟠 **High** |
| 6 | Double-sale of one asset (ADV-3) | High | Severe | 🟠 **High** |
| 7 | A3/A4 disclosed to third-party LLM (TB-9) | **Certain — happening now** | Severe | 🟠 **High** |
| 8 | Admin session theft via `localStorage` (AT-2 [3.2]) | Low (requires XSS; none found) | Total | 🟠 **High** |
| 9 | Member PII harvested in bulk (ADV-2) | Certain | Moderate + regulatory | 🟡 **Medium** |
| 10 | Compromised dependency reaches prod (ADV-7) | Low-medium | Severe | 🟡 **Medium** |

**Note on #1 and #3:** the product owner has confirmed the current corpus is *synthetic demo data derived from public-domain IP*, so there is **no live breach today**. Both remain Critical because they are unmitigated design flaws standing directly in the path of the first real listing.

---

## 6. Global compliance tensions to design for now

Confirmed direction is a worldwide platform with lawyer-owned handover. These conflicts must be resolved in architecture, not in policy documents:

1. **Erasure vs. evidence.** GDPR Art. 17 / LGPD / DPDP erasure rights against an immutable evidentiary record. **Resolution:** make permanent *only* salted hashes and pseudonymous identifiers; keep all personal data in erasable storage referenced by those identifiers. Today `audit_logs` stores raw `ip_address`, `user_agent` and free-form `metadata` — including emails (`admin.py:224`) — permanently. That combination is not compliant anywhere.
2. **Data localisation vs. single-region.** PIPL (China) and several others require in-country storage. A single deployment cannot satisfy them. **Resolution:** region-pinned data planes with a global control plane; accept that some markets are out of scope until a local plane exists. Decide this before the first enterprise contract, not after.
3. **Sanctions and export control.** A global IP marketplace transferring technical data is squarely within EAR/Wassenaar and OFAC/EU/UN scope. There is **no screening of any kind** today — no denied-party check, no jurisdiction gate on disclosure, no dual-use classification. **Counsel must scope this; it is not an engineering judgement call.** → **SAHA-029**
4. **Third-party processors.** Sending A3/A4 to NVIDIA and Anthropic requires DPAs, SCCs/adequacy analysis per jurisdiction, and disclosure to users. None exists. **Resolution:** self-host inference for anything above 🟡 internal. → **SAHA-013**
5. **Trade-secret status is contingent on your own controls.** Under DTSA and the EU Trade Secrets Directive, protection requires "reasonable measures to maintain secrecy." Publishing BOMs unauthenticated (**SAHA-003**) and encrypting with a key published in your public repository (**SAHA-001**) would both be argued as a failure of reasonable measures — potentially **extinguishing the seller's trade-secret protection as a matter of law**, independent of any breach. This is the sharpest legal edge in the entire report and warrants counsel review.

---

## 7. Recurring practice

This model is a snapshot. To stay accurate it needs: re-modelling on every new trust boundary (payments provider, e-signature, registry integration, tenancy, region); a lightweight STRIDE pass in design review for any feature touching A1–A5; annual third-party penetration testing scoped to the boundaries above — **after** the Immediate and Short-term tiers in [REMEDIATION-PLAN.md](REMEDIATION-PLAN.md), since testing against the current state would only rediscover what is already documented here.
