# Saha — Remediation Plan

> **2026-11-01 context:** This document preserves the earlier audit/plan and its recorded evidence. It is not a current host probe or completed-feature inventory. See [Current security boundaries](CURRENT-SECURITY.md), [release evidence](../docs/CURRENT-STATUS.md) and the [open-collaboration plan](../docs/OPEN-INNOVATION-PLAN.md). Use the current hosting runbook for deployments; retain the historical findings below.

**Version:** 1.1 · **Date:** 2026-08-05 · **Execution status added same day**
**Companions:** [AUDIT.md](AUDIT.md) (findings) · [THREAT-MODEL.md](THREAT-MODEL.md) · [ROADMAP.md](ROADMAP.md) · [ARCHITECTURE-TARGET.md](ARCHITECTURE-TARGET.md) · [DEPLOY-2026-08-05.md](DEPLOY-2026-08-05.md)

---

## Execution status — 2026-08-05

**Tiers 0, 1 and 2 are complete in code.** Two Tier 0 items are live on the host;
everything else is staged behind one blocked step.

| Tier | Planned | Built | Live |
|---|---|---|---|
| **Tier 0** — today, config only | 7 items | 7 | **5** (loopback bindings, Grafana rotation, prod env, cookie flags, host/CORS lists — the last three take effect at restart) |
| **Tier 1** — this week | 10 items | 10 | 0 — awaiting migration |
| **Tier 2** — two weeks | 10 items | 10 | 0 — awaiting migration |
| **Tier 3** — structural | 7 workstreams | 2 partial (3.1 guard, 3.3 phases a–b) | — |

**The blocker:** the schema migration alters six `postgres`-owned tables and there
is no passwordless path to that role on this host. The backend was deliberately
**not** restarted — the new ORM models reference columns the migration adds, so
restarting first would have taken the live site down. Full sequence and rollback
in [DEPLOY-2026-08-05.md](DEPLOY-2026-08-05.md).

**Delivered alongside the fixes:**
- Test suite **141 → 274** passing, including the integration harness (`conftest.py`) whose absence is why SAHA-003 and SAHA-007 survived the previous suite.
- CI pipeline with six audit-derived invariants that generic scanners would not catch.
- `scripts/rotate_vault_key.py` for the SAHA-001 backfill.
- Both web apps typecheck clean against the changed API surface.

**Two fixes came from the tooling rather than the plan.** The frontend
typechecker surfaced a second instance of SAHA-003 — the discover page rendered
BOM counts from search results — and writing `test_contact_detect.py` exposed two
real bugs in the new classifier (`at` matching inside "WhatsApp" and "patent")
before it ever ran against a message.

---

**Owner column** reflects a solo-founder-plus-agent team: **You** = decisions, credentials, infrastructure, counsel engagement. **Eng** = implementation (you directing Claude Code). **Counsel** = external legal review — the item cannot be closed by engineering alone.

Effort estimates assume the current working pattern (agent-assisted implementation) and are wall-clock, not idealised.

---

## Tier 0 — Today (≤ 2 hours, all configuration)

These are exploitable now by an unauthenticated or low-privilege actor, and every one is a config change with no code risk. Do them in this order; each is independently safe to roll back.

| # | Action | Finding | Effort | Rollback | If deferred |
|---|---|---|---|---|---|
| 0.1 | Bind every data-plane container to loopback: `127.0.0.1:` prefix on all `ports:` in `docker-compose.yml` (Redis, MinIO ×2, Qdrant ×2, Mailpit ×2, Grafana, Prometheus, Loki), then `docker compose up -d` | 002, 006, 012, 028 | 15 min | Revert the file, recompose | Anyone on the shared network reads the vault, all platform email, and every invention transcript |
| 0.2 | Rotate MinIO credentials and Grafana admin password out of `.env`; restart backend | 002, 028 | 15 min | Restore previous values | Default credentials remain the front door |
| 0.3 | `APP_ENV=production`, `COOKIE_SECURE=true`, `KYC_MOCK_MODE=false` in `apps/backend/.env`; restart backend | 004, 005, 010 | 10 min | Revert `.env`, restart | Boot guards stay off, KYC stays self-serve, refresh cookie stays insecure |
| 0.4 | **Expected:** the app now refuses to boot. Fix what it names — `ALLOWED_HOSTS=["sahasolutions.com","www.sahasolutions.com"]`, drop the two `http://10.0.0.228` CORS origins, drop localhost origins | 005, 010 | 20 min | — | — |
| 0.5 | Set `FRONTEND_URL=https://sahasolutions.com` (currently defaults to `http://localhost:3000`, so **every verification email link is broken**) | operational | 2 min | — | Email verification cannot work at all |
| 0.6 | Host firewall: default-deny inbound except 80/443 and your management path | 002, 006, 012, 028 | 20 min | `ufw disable` | Defence-in-depth for 0.1 |
| 0.7 | Confirm mock mode is now actually off end-to-end: `POST /api/v1/users/me/kyc/complete` returns 404; `POST /api/v1/webhooks/kyc` with a bad signature returns 401 | 004 | 10 min | — | — |

> **Note on 0.3/0.7:** turning off `KYC_MOCK_MODE` means **no user can become verified** until real Persona is wired (Tier 2, item 2.6). For a demo-data environment with no real users that is the correct trade — it fails closed. If you need working demo flows in the interim, use the admin KYC override (`POST /api/v1/admin/users/{id}/kyc`), which is audited, rather than re-enabling the self-serve mock. **Flagged explicitly as a functionality trade-off**, per the rules of engagement.

---

## Tier 1 — This week (the two that change the security posture)

| # | Action | Finding | Effort | Depends on | Rollback | If deferred |
|---|---|---|---|---|---|---|
| 1.1 | **Split `ListingResponse` into `PublicListingResponse` / `OwnerListingResponse`.** Apply to `/listings/public`, `/listings/{id}`, and `SearchResult.listing`. Bound `offset` (`le=10_000`). Patch in [AUDIT.md SAHA-003](AUDIT.md) | **003** | 3–4 h | none | Revert commit; response shape is additive-safe for the owner path | The listing corpus stays world-readable — the finding that ranks #1 on exploitability × impact |
| 1.2 | **Rotate `VAULT_ENCRYPTION_KEY` with versioned key support.** Implement `_derive_key(version)`, read `encryption_key_id` from the asset row, write new objects as `v2`, backfill re-encryption, then retire `v1`. Patch in [AUDIT.md SAHA-001](AUDIT.md) | **001** | 1 day | 0.1 (don't rotate while storage is exposed) | Keep `v1` decryption path; revert `KEY_VERSION` | Every vault object and negotiation message stays decryptable with a key published in your repo |
| 1.3 | Make the boot guard fire in **all** environments for key material — `validate_security_critical()` called unconditionally in `lifespan` | 001, 005 | 1 h | 1.2 | Revert | The same class recurs on the next environment |
| 1.4 | Fix `_check_access` → `_check_buyer` on `/disburse` (one line) | **007** | 15 min | none | Revert | Seller self-release ships to production with real money |
| 1.5 | Admin console: drop `refreshToken` from `partialize` | **009** | 15 min | none | Revert | Control-plane XSS yields 7-day admin persistence |
| 1.6 | Replace the LLM contact-info classifier with deterministic regex; route any remaining confidential-tier AI to Ollama | **013** | 3 h | none | Feature flag back to the LLM path | Negotiation plaintext keeps leaving the trust boundary on every message |
| 1.7 | Trusted-proxy handling: use `X-Real-IP`, or last-XFF-element, or `CF-Connecting-IP` validated against Cloudflare ranges | **011** | 2 h | none | Revert | Rate limits stay bypassable; audit IPs stay forgeable |
| 1.8 | Remove `seller_email` from materials browse and `email` from community member lists | **016** | 1 h | none | Revert | The member directory stays effectively public |
| 1.9 | Per-route limits: KYC 5/h, vault download 30/h, anonymous listing reads 60/min | 020 | 1 h | none | Revert | Bulk extraction stays unthrottled |
| 1.10 | `/health` → auth-gated or loopback-only; never return exception text | 019 | 1 h | none | Revert | Stack enumeration + error disclosure to anonymous callers |

**Tier 1 exit criteria:** an unauthenticated attacker gets nothing above 🟢 public; a network-adjacent attacker gets nothing without credentials; no single party can move money or execute a contract alone.

---

## Tier 2 — Two weeks (high-severity, modest refactoring)

| # | Action | Finding | Effort | Depends on | Rollback | If deferred |
|---|---|---|---|---|---|---|
| 2.1 | **Dual-signature execution.** `contract_signatures` table (`transaction_id`, `signer_id`, `contract_sha256`, `ip_address`, `signed_at`, unique per pair); `SIGNED` only when both parties have matching rows. Migration + service change | **008** | 2 days | 1.4 | Migration is additive; feature-flag the both-parties requirement | Unilateral execution and full repudiation remain |
| 2.2 | **Encrypt contracts; record and verify `contract_sha256`;** drop `contract_storage_key` from `TransactionResponse`; enable versioning + object lock on `vault/` and `contracts/` | **021** | 1 day | 1.2 | Keep plaintext read fallback during backfill | Contracts remain readable and silently replaceable |
| 2.3 | **Mock-mode gating on `APP_ENV is DEVELOPMENT`,** not on empty keys; remove import-time `MOCK_MODE`; assert `escrow_funded_at` in `_assert_vault_access` | **036** | 4 h | 0.3 | Revert | Vault release without payment stays reachable |
| 2.4 | **Enforce MFA for admins;** step-up re-auth for `disburse`, `sign`, vault download, KYC/role changes | **015** | 2 days | 1.5 | Feature flag per role | One stolen admin password = full platform control |
| 2.5 | **CI pipeline** — see §5. Non-negotiable prerequisite for everything after this point | **023** | 1 day | none | Disable workflow | Every fix above can regress silently |
| 2.6 | **Real Persona KYC** — configure `inquiry-template-id`, verify webhook signatures, remove the mock path entirely | 004 | 2 days | 0.3 | Admin override remains the fallback | Nobody can verify (fails closed, but blocks the product) |
| 2.7 | **Exclusivity lock + row locking.** `SELECT … FOR UPDATE` on transaction state changes; unique partial index preventing two live transactions past `SIGNED` per `listing_id`; idempotency keys on `disburse`/`escrow/*` | 032, 037 | 2 days | 2.1 | Migration additive | Double-sale and double-disbursement stay possible |
| 2.8 | **Upload hardening** — magic-byte allow-list, streaming with incremental size cap, metadata stripping on ingest | 018, 031 | 2 days | none | Revert; keep old path behind a flag | Polyglots stored; EXIF/authorship leaked to counterparties; memory DoS |
| 2.9 | SSE ticket exchange replacing the query-param token | 017 | 1 day | none | Revert | Live tokens keep landing in nginx logs |
| 2.10 | Migrate `python-jose` → `PyJWT`; TOTP counter replay guard; SMTP TLS | 026, 030, 027 | 1 day | 2.5 | Revert | Unmaintained crypto in the auth path |

---

## Tier 3 — Structural (1–2 quarters)

Ordered so each eliminates a **class** of vulnerability rather than an instance. This is where the durable value is.

### 3.1 Centralised authorization (eliminates the SAHA-007 class) — 3 weeks
**Problem:** six hand-rolled predicate shapes across eight modules; SAHA-007 was a wrong-helper bug that nothing caught.
**Design:** one policy module with a single decision table — `authorize(actor, action, resource) -> Decision` — covering every `(role, resource_type, action)` triple. Router-level `dependencies=[Depends(require_auth)]` as default-deny, with an explicit public allow-list. A route-inventory test that **fails when any route lacks an explicit guard**.
**Breaks if deferred:** every new endpoint is a fresh chance to repeat SAHA-007, and the roadmap adds many.
**Rollback:** land the policy module alongside existing checks, assert agreement in tests for one release, then remove the old checks.

### 3.2 Single audited document-access path (eliminates the disclosure class) — 4 weeks
**Problem:** disclosure rules are spread across `_assert_vault_access`, response models, and implicit assumptions.
**Design:** every document read goes through one service function taking `(actor, document, purpose)` and returning bytes or raising — enforcing NDA state, deal state, per-document grant, expiry, revocation, watermarking and audit **in one place**. No other code path may call `decrypt_file`. Enforce with an import-lint rule.
**Depends on:** 3.1, plus the NDA/data-room model in [ROADMAP.md §2](ROADMAP.md).
**Breaks if deferred:** tiered disclosure cannot be implemented correctly, because there is no single place to implement it.

### 3.3 Tamper-evident evidentiary layer (eliminates the repudiation class) — 6 weeks
**Phases** (detail in [AUDIT.md SAHA-014](AUDIT.md) and [ROADMAP.md §3](ROADMAP.md)): (a) canonical serialisation + hash chain; (b) `REVOKE UPDATE, DELETE` + append-only trigger + separate INSERT-only role; (c) daily Merkle root + RFC 3161 timestamp; (d) user-facing verification tool and exportable evidence packages.
**Note:** RFC 3161 first — it is cheap and has far more court precedent than any chain anchor. Confidential Ledger and public-chain anchoring are refinements, not the foundation.
**Breaks if deferred:** the platform's core claim — that it evidences transactions lawyers rely on — remains unsupportable.

### 3.4 Key management and data-holding minimisation — 4 weeks (concurrent with Azure migration)
Per-tenant DEKs wrapped by a customer-managed KEK in Key Vault Managed HSM; managed identity replacing every stored credential; documented rotation; the **escrow question** (who can decrypt if the customer loses their key — and whether Saha *should* be able to) decided explicitly with **counsel**, not by default. See [ARCHITECTURE-TARGET.md §4](ARCHITECTURE-TARGET.md).

### 3.5 Typed, validated request boundaries with response-tier enforcement — 2 weeks
Generalise the SAHA-003 fix: every response model carries an explicit data tier; a test asserts no model above 🟡 internal is reachable from a route whose guard is weaker than the tier requires. Makes the whole finding class mechanically impossible to reintroduce.

### 3.6 Privacy and retention infrastructure — 4 weeks
Retention schedule per table; account deletion with pseudonymisation (not erasure) of evidentiary rows; data export; `demand_signals` aggregation after 30 days with `user_id` dropped. **Counsel sets the periods**; engineering builds the machinery.

### 3.7 Detection and response — 3 weeks
Security metrics and alert rules (§5); audit events to a SIEM; a documented incident-response runbook; quarterly restore testing.

---

## 4. Sequencing constraints

```
Tier 0 (config, today)
   └─→ 1.2 key rotation ── requires storage no longer LAN-exposed
   └─→ 2.3 mock gating  ── requires APP_ENV=production
   └─→ 2.6 real KYC     ── requires mock off

1.1 response split ──→ 3.5 tier enforcement (generalises it)
1.4 disburse fix   ──→ 3.1 central authz (generalises it)
2.1 dual signature ──→ 2.7 exclusivity lock ──→ 3.3 evidentiary layer
2.5 CI ──→ everything after (nothing lands unverified without it)
3.1 central authz ──→ 3.2 single document path
3.4 key management ─── concurrent with Azure migration; do not build twice
```

**Critical path to "safe to onboard a real seller":** Tier 0 → 1.1 → 1.2 → 1.4 → 2.1 → 2.5 → 2.6. Roughly **three weeks**. Everything else can follow onboarding; nothing on that path can.

---

## 5. CI enforcement — making these classes unable to reappear

No CI exists today ([AUDIT.md SAHA-023](AUDIT.md)), so no fix in this document is currently protected against regression. This is the highest-leverage process change available.

```yaml
# .github/workflows/ci.yml
name: ci
on: [push, pull_request]
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }          # full history for secret scanning
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --all-extras
      - run: uv run pytest -q                    # 129 tests + the new regression suite
      - run: uv run ruff check .
      - run: uv run bandit -r app -ll            # SAST
      - run: uv run pip-audit --strict            # dependency CVEs
      - run: uv run semgrep --config=p/python --config=p/security-audit --error
  secrets:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2         # working tree AND history
  frontend:
    strategy: { matrix: { app: [frontend, admin] } }
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with: { version: 9.15.4 }
      - run: pnpm --dir apps/${{ matrix.app }} install --frozen-lockfile
      - run: pnpm --dir apps/${{ matrix.app }} audit --audit-level=high
      - run: pnpm --dir apps/${{ matrix.app }} exec tsc --noEmit
      - run: pnpm --dir apps/${{ matrix.app }} build
  compose-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |                                    # SAHA-002/006/012/028 can never recur
          ! grep -nE '^\s+- "[0-9]+:[0-9]+"' saha-dev-infra/docker-compose.yml \
            || (echo "::error::container port published on 0.0.0.0 — prefix 127.0.0.1:"; exit 1)
```

Branch protection: require all jobs green before merge to `main`; no direct pushes.

**Custom checks that encode this audit's lessons** — these are the ones that matter most, because generic scanners will not catch them:

| Check | Prevents recurrence of |
|---|---|
| Route inventory: every route declares an auth dependency or is on an explicit public allow-list | 022 — the SAHA-007 class |
| Response-tier assertion: no model containing tier-🔴/🟠 fields is reachable from a route weaker than the tier | 003 |
| Config assertion: no known dev-default value for any secret, in any environment | 001, 005 |
| Compose lint: no `0.0.0.0` published ports | 002, 006, 012, 028 |
| AI-routing assertion: no confidential-tier function may resolve to an external provider | 013 |
| Grep gate: no credential accepted via query parameter | 017 |

Later additions once IaC exists: `checkov`/`tfsec` on Bicep/Terraform, and SBOM generation with `syft` + `grype`.

---

## 6. Regression test suite

129 tests exist and are genuinely good — MFA, lockout, Stripe signatures, transaction policy, vault crypto, communities, materials, profile. **Two structural gaps:**

1. **There is no `conftest.py`** — no shared fixtures, no test database, no HTTP client. Every test is a unit test against pure functions; **not one exercises a route end-to-end with authentication.** That is precisely why SAHA-003 (a response-model defect) and SAHA-007 (a wrong-dependency defect) went unnoticed: both are invisible to unit tests and unmissable in an integration test.
2. **`tests/test_persona_webhook.py` asserts the vulnerability as intended behaviour** — that mock mode accepts unsigned webhooks. Invert it as part of 2.6.

### Prerequisite: integration test harness (2 days, do this first)
`conftest.py` providing an ephemeral Postgres (testcontainers or a template database), an `AsyncClient` against the ASGI app, and fixtures: `anon_client`, `unverified_client`, `verified_client`, `second_verified_client`, `admin_client`, `published_listing`, `funded_transaction`.

### Test cases per finding

| Finding | Test | Must fail against current code |
|---|---|---|
| 001 | Vault key is not a known default; boot refuses defaults in **any** env; `v1` objects still decrypt after rotation | ✅ |
| 002 | Compose lint: no published `0.0.0.0` ports | ✅ |
| **003** | Anonymous `/listings/public` omits `bom_items`, `description`, `vault_assets`, `equipment_requirements`, `batch_size_definition`; same for `/search`; owner still sees all | ✅ |
| 004 | `/me/kyc/complete` 404s outside development; Persona signature never auto-passes outside development | ✅ |
| 005 | Unknown `APP_ENV` rejected; hardening applies to staging **and** production | ✅ |
| **007** | Seller `POST /disburse` → 403; buyer → 200 | ✅ |
| **008** | One signature does not reach `SIGNED`; two do; altering the contract invalidates the signature hash | ✅ |
| 009 | Persisted admin state contains no refresh token | ✅ |
| 010 | Login `Set-Cookie` includes `Secure` and `HttpOnly`; no `http://` CORS origins when internet-facing | ✅ |
| 011 | Spoofed `X-Forwarded-For` does not change the rate-limit key; audit records the real peer | ✅ |
| 013 | Confidential-tier functions never resolve to an external provider; contact detection works with the network stubbed out | ✅ |
| **014** | Chain verification detects a mutated row; `UPDATE audit_logs` raises; canonical serialisation is key-order independent | ✅ |
| 016 | Materials browse omits `seller_email`; member list omits `email` for non-managers | ✅ |
| 018 | Content-type/magic-byte mismatch rejected; oversized upload rejected without full buffering; EXIF stripped | ✅ |
| 021 | Contract bytes at rest are ciphertext; post-write tampering detected on read | ✅ |
| 032 | 20 concurrent `/disburse` → exactly one `Disbursement` row; same for `accept` and `escrow/confirm` | ⚠️ verify first |
| 036 | Mock Stripe unavailable outside development; vault access requires `escrow_funded_at` | ✅ |
| 037 | Second transaction on the same listing cannot pass `SIGNED` while another is live | ✅ |

### Standing suites (run every CI build)
- **Authorization matrix** — for each `(actor_role, resource_ownership, action)`, assert the expected allow/deny. Catches the SAHA-007 class by construction.
- **Anonymous exposure sweep** — walk every route with no credentials; assert no response contains any tier-🔴/🟠 field name. Catches the SAHA-003 class by construction.
- **Boundary sweep** — for each two-party resource, assert party B cannot read or mutate party A's.

---

## 7. What breaks if each tier is deferred

| Deferred | Consequence |
|---|---|
| **Tier 0** | The platform is compromisable from the shared network with no account, and the trust model is self-serve. Do not onboard anyone. |
| **Tier 1** | The listing corpus stays world-readable and at-rest encryption stays decorative. Any real IP listed before this is disclosed on arrival — and, under DTSA / EU Trade Secrets Directive, arguably loses trade-secret protection as a matter of law because reasonable measures were not taken. |
| **Tier 2** | Deals can be executed by one party, escrow released without payment, and the same asset sold twice. Fine for demo data; unacceptable the moment money or real IP moves. |
| **Tier 3** | The platform works but cannot prove anything. Every dispute becomes your word against theirs, SOC 2 is unreachable, and the lawyer-led handover model has no evidentiary substrate to rest on. |

---

## 8. Items requiring counsel, not engineering

Flagged per the rules of engagement. Engineering can build the machinery; it must not decide the policy.

| Item | Question for counsel |
|---|---|
| 001 | Does key exposure require breach notification (GDPR Art. 34, PIPEDA, US state laws) given the corpus is synthetic? |
| 007 | What release conditions are lawful and enforceable for escrow across target jurisdictions? |
| 008 | What constitutes valid execution per jurisdiction (eIDAS, ESIGN/UETA, and equivalents)? |
| 013 | What transfer basis covers sending confidential content to US inference providers from each market? |
| 025 | Retention periods per data class; how erasure interacts with evidentiary immutability |
| 029 | Sanctions, PEP and export-control obligations — scope, screening standard, and record-keeping |
| 037 | Saha's liability posture as intermediary for title defects and double-sales |
| — | Whether publishing BOMs (003) or using a repo-published key (001) prejudices sellers' trade-secret status |
