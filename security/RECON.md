# Phase 1 — Reconnaissance Map

> **2026-11-01 context:** This document preserves the earlier audit/plan and its recorded evidence. It is not a current host probe or completed-feature inventory. See [Current security boundaries](CURRENT-SECURITY.md), [release evidence](../docs/CURRENT-STATUS.md) and the [open-collaboration plan](../docs/OPEN-INNOVATION-PLAN.md). Use the current hosting runbook for deployments; retain the historical findings below.

**Repo:** `/home/hitarth/Downloads/saha` · branch `master` · HEAD `3fa6203`
**Date of review:** 2026-08-05
**Reviewer:** automated code audit (Claude Opus 5), read-only pass
**Scope covered:** 100% of `apps/backend` Python (108 files), `apps/frontend` + `apps/admin` auth/API layers, `saha-dev-infra`, plus the *live host configuration* (nginx, cloudflared, systemd, listening sockets) because this deployment is internet-facing today.

> **Codebase size verdict:** the backend is small enough to review exhaustively and was. The two Next.js apps were reviewed for auth, token handling, and XSS sinks — not exhaustively for UI logic. See §8 for what remains uncovered.

---

## 0. Project context (placeholders resolved from the repo + running host)

The directive's Section 0 placeholders were left unfilled. Resolved from evidence:

| Field | Resolved value | Source |
|---|---|---|
| Jurisdictions | **Undetermined — must be confirmed by you.** Deployment is Canada-resident (host on a home/office LAN, `.com` via Cloudflare). Demo users, listings and law-firm records reference Delaware/US governing law (`services/transactions.py:161`). Assume PIPEDA + US state law at minimum; GDPR if any EU user registers. | `app/services/transactions.py`, seed data |
| Stack | Python 3.11 / FastAPI 0.115 / SQLAlchemy 2 async / asyncpg / Postgres 16 (native, not containerised) / Redis 7 / MinIO / Qdrant / Next.js 15.5.18 + React 19 (×2 apps) / structlog / Prometheus | `pyproject.toml`, `package.json` ×2, `docker-compose.yml` |
| IaC tooling | **None.** No Terraform/Bicep/Pulumi/Helm. Infra is a hand-written `docker-compose.yml` (6 services), three systemd units, two nginx site files, one cloudflared config, and hand-run `.sql` migrations. | `saha-dev-infra/`, `/etc/nginx/sites-enabled/`, `/etc/cloudflared/config.yml` |
| Cloud provider | **None today.** Runs on a single NVIDIA Jetson Orin Nano (ARM64, Linux 5.15 Tegra), root on NVMe. Azure migration is planned but unexecuted. | `uname`, memory: `cloud_migration_runbook` |
| Deployment target | Currently: bare-metal Jetson + Cloudflare Tunnel. Planned: Azure (AKS/App Service, Postgres Flexible Server, Blob). | `/etc/cloudflared/config.yml` |
| Current stage | **In production, publicly reachable at `https://sahasolutions.com`**, seeded with 10 demo accounts and 100 demo listings. `APP_ENV=staging`. Real user count unknown; treat as pre-launch-but-live. | `ss -ltnp`, cloudflared ingress, `.env` |
| Compliance goals | Unstated. Assumed SOC 2 Type II ambition per the directive. | — |

**The single most consequential fact in this table:** `APP_ENV=staging`, not `production`. `Settings.is_production` (`app/core/config.py:106-108`) only returns `True` for `"production"`/`"prod"`. Therefore, on the live internet-facing deployment, **every production safety guard is inert**: the boot-time misconfiguration validator, HSTS, and JSON logging. Details in §7.

---

## 1. Repository structure, entry points, deployment units

```
saha/
├── apps/
│   ├── backend/          FastAPI API — the only trust-enforcing component
│   │   ├── app/
│   │   │   ├── main.py           ← ASGI entry point; middleware stack; 17 routers
│   │   │   ├── api/              17 route modules + 2 webhook handlers + schemas/
│   │   │   ├── core/             security, config, audit, ratelimit, mfa, passwords, logging, metrics
│   │   │   ├── services/         business logic (17 modules)
│   │   │   ├── db/               SQLAlchemy models (11) + async session factory
│   │   │   ├── integrations/     storage(S3), vector(Qdrant), email(SMTP), stripe, kyc(Persona)
│   │   │   ├── ai/               provider-agnostic LLM client + 3 providers + routing
│   │   │   └── tasks/            library_digest (in-process scheduler)
│   │   └── tests/                129 tests across 16 files
│   ├── frontend/         Next.js marketplace (:3000) — public UI
│   └── admin/            Next.js admin console (:3002) — control plane
├── packages/shared/      (near-empty)
├── saha-dev-infra/       docker-compose, init-scripts/01-schema.sql, migrations/*.sql, seed/
└── docs/architecture/    HTML + draw.io system maps
```

### Deployment units (live, verified via `systemctl` and `ss`)

| Unit | Bind | Public? | Notes |
|---|---|---|---|
| `saha-backend.service` (uvicorn, 2 workers) | `127.0.0.1:8000` | via nginx `/api/`, `/health` | The API |
| `saha-frontend.service` (next start) | `127.0.0.1:3000` | via nginx `/` | Marketplace |
| `saha-admin.service` (next start) | `127.0.0.1:3002` | **LAN only** (nginx :8080; cloudflared 404s it) | Control plane |
| `nginx` | `0.0.0.0:80` (public), `0.0.0.0:8080` (LAN) | yes | Reverse proxy |
| `cloudflared.service` | outbound tunnel | yes | `sahasolutions.com`, `www.` → `localhost:80`; everything else → HTTP 404 |
| Postgres 16 (native) | `127.0.0.1:5432` | no | ✅ correctly bound |
| Redis 7 (docker) | **`0.0.0.0:6379`** | LAN | ⚠ no password |
| MinIO (docker) | **`0.0.0.0:9000`, `0.0.0.0:9001`** | LAN | ⚠ `minioadmin`/`minioadmin` |
| Qdrant (docker) | **`0.0.0.0:6333`, `0.0.0.0:6334`** | LAN | ⚠ no API key |
| Mailpit (docker) | **`0.0.0.0:1025`, `0.0.0.0:8025`** | LAN | ⚠ web UI shows every sent email |
| Grafana (docker) | **`0.0.0.0:3001`** | LAN | ⚠ `admin`/`admin` |
| Prometheus / Loki | **`0.0.0.0:9091` / `0.0.0.0:3100`** | LAN | ⚠ unauthenticated |

**Confidence: high** — verified directly against the running host, not inferred.

---

## 2. Trust boundaries

| # | Boundary | Enforcement point | Assessment |
|---|---|---|---|
| **TB-1** | Internet → app | Cloudflare Tunnel → nginx :80 → uvicorn. TLS terminates at Cloudflare; **the tunnel-to-nginx and nginx-to-app hops are plaintext HTTP on loopback**. | Adequate for loopback. No mTLS, no WAF rules, no Cloudflare Access on the admin path (mitigated by the 404 ingress rule). |
| **TB-2** | Unauthenticated → authenticated | `HTTPBearer` + `decode_access_token` (`core/security.py:78-92`). Deny-by-default *per handler*, not per router — every route names its own dependency. | **Enforcement is scattered, not centralised.** 89 route handlers each declare their own guard. No router-level `dependencies=[...]`, no default-deny middleware. A new route added without a `Depends` is silently public. This is itself a finding. |
| **TB-3** | Authenticated → KYC-verified | `require_verified_user` (`core/security.py:107-115`). | Correct, but the KYC oracle behind it is in **mock mode** on the live host (§7). |
| **TB-4** | Member → member (horizontal) | Per-resource ownership checks: `_require_owner` (listings), `_check_access`/`_require_participant` (proposals), `_check_access` (transactions/settlement), `require_seller` (materials), `get_membership` (communities). | Consistently present and correct where applied. **However** the checks are hand-rolled in 6 different shapes across 8 modules; there is no shared authorization primitive. One of them (settlement `disburse`) applies the wrong predicate — see §7. |
| **TB-5** | Member → admin (vertical) | `require_admin` (`core/security.py:129-137`) on all 24 `/api/v1/admin/*` routes. Self-registration as ADMIN is blocked at the schema layer (`schemas/auth.py:_SELF_REGISTER_ROLES`). | Correct and complete. Admin tooling uses the **same** authorization model — no bypass. Self-demotion and self-deactivation are guarded (`services/admin.py:122-147`). |
| **TB-6** | App → database | Single Postgres role `saha`, full DML on all tables, loopback only, credentials in `.env`. | No row-level security, no read-only replica role, no separate role for the audit table. An app-level SQLi or an operator with the `.env` gets everything. |
| **TB-7** | App → object storage | boto3/aioboto3 → MinIO with **root credentials** (`minioadmin`). Single bucket `saha-vault` holds vault ciphertext, contracts (**plaintext**), and avatars (plaintext). | No bucket policy, no per-prefix scoped credentials, no object lock, no versioning, no server-side encryption. Application holds root keys. |
| **TB-8** | App → third-party APIs | Outbound HTTPS to `api.stripe.com`, `withpersona.com`, `integrate.api.nvidia.com` (chat + embeddings), `api.anthropic.com`. All secrets in `.env`. | No egress allow-list, no proxy, no secret rotation. See TB-9. |
| **TB-9** | **Confidential content → external LLM inference** | *None.* | **This boundary is not modelled at all.** Negotiation message plaintext, BOM-authoring dialogue (i.e. the creator describing their invention), search queries, and contract terms are POSTed to NVIDIA and Anthropic. See §5 and §6. |
| **TB-10** | LAN → data plane | *None.* Redis, MinIO, Qdrant, Mailpit, Grafana all listen on `0.0.0.0` with default or absent credentials. | Anyone on the LAN reaches the vault bucket, the mail spool (which carries email-verification tokens), and the AI session cache (which carries invention descriptions in plaintext). |
| **TB-11** | Tenant → tenant | **N/A — there is no tenancy model.** Saha is single-tenant with per-user ownership. Enterprises/orgs do not exist. Noted as a roadmap gap, not a vulnerability. | — |

---

## 3. API route inventory (89 handlers, 100% classified)

Legend — **PUB** no auth · **OPT** `get_optional_user` · **AUTH** `get_current_user` · **VER** `require_verified_user` (auth + KYC=verified) · **ADM** `require_admin` · **SIG** webhook HMAC · **+own** resource-ownership check in handler/service.

> **No route in this codebase has an undeterminable control.** Every handler declares its dependency explicitly. That is a genuine strength and is stated as such.

### Ops (`app/api/health.py`) — mounted at root
| Method | Path | Guard | Rate limit | Note |
|---|---|---|---|---|
| GET | `/health/live` | **PUB** | default | fine |
| GET | `/health/ready` | **PUB** | default | postgres/redis status |
| GET | `/health` | **PUB** | default | ⚠ enumerates every backend component **and echoes exception text** — currently returns a Pydantic validation traceback fragment. Publicly proxied by nginx. |
| any | `/metrics/*` | **PUB at app level** | — | ✅ blocked by `deny all` in the public nginx site; not exposed on :8080 either (that path routes to Next.js). |

### Auth (`/api/v1/auth`, `app/api/auth.py`)
| Method | Path | Guard | Limit |
|---|---|---|---|
| POST | `/register` | PUB | 10/min |
| POST | `/login` | PUB | 10/min + account lockout |
| POST | `/refresh` | PUB (cookie or body token) | 60/min |
| POST | `/logout` | AUTH | default |
| POST | `/mfa/setup` | AUTH | 60/min |
| POST | `/mfa/enable` | AUTH | 60/min |
| POST | `/mfa/disable` | AUTH | 60/min |
| GET | `/mfa/status` | AUTH | default |
| POST | `/verify-email/request` | AUTH | 10/min |
| POST | `/verify-email/confirm` | PUB (signed JWT) | 10/min |

**Absent:** password reset / forgot-password. There is *no* recovery flow — confirmed by grep across the whole backend. A user who forgets their password is locked out permanently. (Security-positive in one sense: the classic account-takeover chain doesn't exist. Product-negative, and it will be built eventually — design it correctly then.)

### Users (`/api/v1/users`, `app/api/users.py`)
| Method | Path | Guard | Limit | Note |
|---|---|---|---|---|
| GET | `/me` | AUTH | default | |
| PATCH | `/me` | AUTH | 60/min | name/email frozen post-KYC |
| POST | `/me/password` | AUTH | 10/min | revokes all other refresh tokens ✅ |
| POST | `/me/avatar` | AUTH | 60/min | ⚠ content-type trusted, no magic-byte check |
| GET | `/me/avatar` | AUTH | default | |
| GET | `/{user_id}/avatar` | AUTH | default | any member → any member |
| POST | `/me/kyc/initiate` | AUTH | **none** | ⚠ no `@limiter.limit` decorator |
| POST | `/me/kyc/complete` | AUTH | **none** | ⚠ **mock self-approval; live on the public host** |

### Webhooks (`/api/v1/webhooks`)
| Method | Path | Guard | Note |
|---|---|---|---|
| POST | `/kyc` | SIG (Persona HMAC + `t=`) | ⚠ `verify_persona_webhook_signature` returns `True` unconditionally when `KYC_MOCK_MODE=true` (`integrations/kyc.py:55-56`) |
| POST | `/stripe` | SIG (HMAC-SHA256 + 300s replay window, `hmac.compare_digest`) | ✅ correct; refuses everything when the secret is unset |

### Listings (`/api/v1/listings`, `app/api/listings.py`)
| Method | Path | Guard | Limit | Note |
|---|---|---|---|---|
| POST | `""` | VER | default | |
| GET | `/me` | VER | default | |
| GET | `/public` | **PUB** | default (1000/min) | 🔴 returns full `ListingResponse` incl. **BOM + private description** — see §7 |
| GET | `/{id}` | **OPT** | default | 🔴 same payload, unauthenticated, for any published listing |
| POST | `/{id}/dialogue/start` | VER **+own** | 20/min | |
| POST | `/{id}/dialogue` | VER **+own** | 20/min | |
| GET | `/{id}/dialogue` | VER **+own** | default | |
| POST | `/{id}/finalize-bom` | VER **+own** | 20/min | |
| POST | `/{id}/files` | VER **+own** | 20/min | vault upload |
| POST | `/{id}/publish` | VER **+own** | default | |

### Proposals / negotiation (`/api/v1/proposals`)
All 10 routes: **VER + participant check** (`_check_access` in the router, `_require_participant`/`_require_buyer` in the service). Correct throughout. `accept` additionally blocks self-acceptance of one's own latest offer (`services/proposals.py:150-160`) ✅.

### Transactions / legal (`/api/v1/transactions`, `app/api/transactions.py`)
| Method | Path | Guard | Note |
|---|---|---|---|
| GET | `""` | VER (own only) | |
| GET | `/law-firms` | VER | |
| GET | `/{id}` | VER + party | |
| POST | `/{id}/assign-law-firm` | VER + party | |
| POST | `/{id}/draft-contract` | VER + party, 20/min | invokes Anthropic |
| POST | `/{id}/sign` | VER + party | ⚠ **either party alone** flips `CONTRACT_REVIEW → SIGNED` |
| POST | `/{id}/status` | VER + party | state machine + `_SYSTEM_ONLY_TARGETS` guard ✅ |

### Settlement (`/api/v1/transactions/...`, `app/api/settlement.py`)
| Method | Path | Guard | Limit | Note |
|---|---|---|---|---|
| POST | `/{id}/escrow/create` | VER + **buyer** | 10/min | |
| POST | `/{id}/escrow/confirm` | VER + **buyer** | 10/min | refuses in live-Stripe mode ✅ |
| POST | `/{id}/disburse` | VER + **either party** | 10/min | ⚠ seller can release escrow to themselves |
| GET | `/{id}/vault-access` | VER + party + escrow-funded gate | default | |
| GET | `/{id}/vault-access/{asset}/download` | VER + party + escrow-funded gate | **none** | audited ✅; no rate limit on bulk download |

### Others
- **Materials** (`/api/v1/materials`, 5 routes): all **VER**; `require_seller` on mutations. ⚠ browse/detail responses embed `seller_email`.
- **Communities** (`/api/v1/communities`, 11 routes): reads **AUTH**, writes **VER**; message-read requires membership ✅. ⚠ `GET /{id}/members` returns every member's **email** to any authenticated user for public communities.
- **Open resources** (`/api/v1/open-resources`, 6 routes): reads AUTH, writes VER, curation is ADM-only ✅.
- **Reviews** (3 routes): VER; `GET /users/{id}/reputation` accepts any user id.
- **Demand** (`GET /api/v1/demand/overview`): VER — ⚠ any verified member sees **platform-wide** search-demand intelligence including unmet-demand queries.
- **Search** (`POST /api/v1/search`): **OPT**, 30/min.
- **Notifications** (5 routes): AUTH; `GET /stream` takes the **access token as a query parameter** (`api/notifications.py:55`) → written to nginx access logs.
- **Admin** (24 routes): **ADM** on every one, each audited via `_audit()` ✅.

---

## 4. Data model & classification

11 SQLAlchemy models / 17 tables. Classification uses the directive's four tiers.

| Table | Tier | Rationale |
|---|---|---|
| `ip_vault_assets` (+ MinIO `vault/`) | 🔴 **trade-secret** | Uploaded IP documents: unpublished claims, unfiled applications, process docs. Encrypted at rest. |
| `bom_items` | 🔴 **trade-secret** | The manufacturing recipe: material names, specifications, quantities per unit, criticality, notes. **Currently served to unauthenticated callers.** |
| `ip_listings.description`, `.equipment_requirements`, `.batch_size_definition` | 🔴 **trade-secret** | Creator's private authoring fields, distinct from `public_description`. **Currently served to unauthenticated callers.** |
| Redis `bom:session:*` | 🔴 **trade-secret** | Full LLM transcript in which the creator describes the invention. Plaintext, no auth on Redis, 24h TTL. |
| `messages.encrypted_content` | 🟠 **confidential** | Negotiation content. AES-256-GCM at rest ✅ — but the **plaintext is sent to NVIDIA** for contact-info classification before encryption. |
| `proposals`, `proposal_versions` | 🟠 confidential | Offer amounts, licence type, territory, duration, notes. Cleartext columns. |
| `transactions`, `disbursements` | 🟠 confidential | Deal value, fees, Stripe intent/transfer ids, timestamps. Cleartext. |
| MinIO `contracts/{txn}/draft.txt` | 🟠 confidential | **Stored unencrypted** while vault assets are encrypted — an inconsistency, not a rule. |
| `users.hashed_password` | 🟠 confidential | bcrypt cost 12 ✅ |
| `users.mfa_secret` | 🟠 confidential | AES-256-GCM, key = SHA-256("mfa:" + SECRET_KEY) ✅ |
| `users` (email, full_name, kyc_status, kyc_inquiry_id) | 🟠 confidential PII | Emails leak via materials browse + community member lists. |
| `refresh_tokens` | 🟠 confidential | SHA-256 hashes only ✅, with family-based reuse detection ✅ |
| `audit_logs` | 🟠 confidential | Ordinary table. **Append-only by convention only** — no DB grants, no triggers, no WORM, no hash chain. |
| `demand_signals` | 🟡 internal | Raw search queries + parsed intent + user_id. Reveals what buyers are hunting for. |
| `raw_material_listings` | 🟡 internal | Marketed content, but joined with seller email on read. |
| `communities`, `community_memberships` | 🟡 internal | |
| `community_messages` | 🟡 internal | Explicitly plaintext by design. |
| `notifications` | 🟡 internal | Titles/bodies can quote deal facts. |
| `reviews` | 🟢 public-ish | Intended to be visible. |
| `open_resources`, `open_resource_builds` | 🟢 **public** | The whole point is openness. |
| `law_firm_partners` | 🟢 public | |
| MinIO `avatars/` | 🟢 public-ish | Plaintext, auth-gated endpoint. |
| Qdrant `ip_listings` collection | 🟡 internal | Payload = title, `public_description`, tags, category, `creator_id`. Correctly holds **only** teaser-tier fields ✅ — no BOM, no private description. This is the one place staged disclosure was implemented properly. |

**Classification confidence: high.** Derived from column definitions plus the code paths that populate them.

---

## 5. Lifecycle of one uploaded IP document

Every component that touches the bytes **in plaintext** is marked ⚠.

**Upload** — `POST /api/v1/listings/{id}/files`
1. ⚠ Browser → Cloudflare edge (TLS terminates here; Cloudflare sees plaintext)
2. ⚠ Cloudflare Tunnel → `nginx:80` (plaintext HTTP over loopback)
3. ⚠ nginx buffers the multipart body to disk (`client_max_body_size 60M`; nginx temp files under `/var/lib/nginx/body/`)
4. ⚠ uvicorn → Starlette `UploadFile` — `python-multipart` spools to a `SpooledTemporaryFile`, which **rolls over to `/tmp` above 1 MB**
5. ⚠ `api/listings.py:217` — `data = await file.read()` — the **entire file is held in process memory**, then size-checked *after* reading
6. `services/vault.py:22-26` — AES-256-GCM encrypt, key = `SHA-256(VAULT_ENCRYPTION_KEY)`, fresh 12-byte `os.urandom` nonce, no AAD
7. Ciphertext → MinIO, key `vault/{listing_id}/{asset_id}/{original_filename}.enc`
8. Row inserted into `ip_vault_assets` (filename, size, content-type, `encryption_key_id="v1"`)
9. Audit entry `vault.file_uploaded` written in a background task

**Retrieval** — `GET /api/v1/transactions/{txn}/vault-access/{asset}/download`
1. `require_verified_user` → `_assert_vault_access` (`services/settlement.py:157-167`): must be buyer or seller; if buyer, transaction must be in `{ESCROW_FUNDED, DISBURSEMENT_PENDING, COMPLETED}`
2. Asset lookup is scoped by `listing_id == transaction.listing_id` — ✅ **no IDOR**: you cannot pull another listing's asset through your own transaction
3. `decrypt_file` → MinIO `get_object` → ⚠ full ciphertext into memory → ⚠ decrypt → full plaintext into memory
4. ⚠ Returned as a single non-streaming `Response` body through uvicorn → nginx → Cloudflare → browser
5. Audit entry `vault.file_downloaded` (asset id + filename) written in a background task
6. `Content-Disposition` filename is sanitised against CR/LF header injection with an RFC 5987 `filename*` fallback ✅

**Plaintext-touching components:** Cloudflare edge, nginx (+ its on-disk request body temp files), `/tmp` spool files, the uvicorn worker's heap, MinIO only-for-avatars-and-contracts (vault objects are ciphertext ✅).

**Deliberately absent, all confirmed by grep:** no presigned URLs for vault objects (a documented, correct decision — `services/vault.py:49-51`); no thumbnails, previews, OCR, or text extraction; no malware scanning; no metadata/EXIF stripping; no watermarking; no view-only rendering; no per-document access grants; no deletion path at all (there is **no** vault-asset delete endpoint, so "is deleted data really gone" is moot — nothing can be deleted).

**Confidence: high.**

---

## 6. Third-party dependencies & external services

### Backend (`pyproject.toml`) — floating lower bounds (`>=`), pinned by `uv.lock` (2,864 lines)
`fastapi>=0.115` · `uvicorn[standard]>=0.30` · `pydantic>=2.7` · `pydantic-settings>=2.3` · `sqlalchemy[asyncio]>=2.0` · `alembic>=1.13` · `asyncpg>=0.29` · `redis[asyncio]>=5.0` · `celery[redis]>=5.4` *(declared, never imported)* · `aioboto3>=13.0` · `qdrant-client>=1.9` · `anthropic>=0.28` *(declared; providers use raw `httpx`)* · `httpx>=0.27` · **`python-jose[cryptography]>=3.3`** · `bcrypt>=4.0` · `python-multipart>=0.0.9` · `aiosmtplib>=3.0` · `structlog>=24.1` · `prometheus-client>=0.20` · `slowapi>=0.1.9` · `email-validator>=2.3`

Two supply-chain observations worth flagging now, both requiring version verification against the lockfile before being asserted as findings:
- **`python-jose` is effectively unmaintained** (last meaningful release 2021). It is the JWT implementation for the entire auth system. A migration to `PyJWT` or `joserfc` is the durable fix regardless of any specific CVE.
- **`celery` is a declared dependency with zero imports** — dead weight and needless attack surface.

I have not asserted any CVE. A proper `pip-audit`/`osv-scanner` run against `uv.lock` is required and is listed as a Phase 3 task.

### Frontend / admin
`next@15.5.18` · `react@19.1.0` · `zustand@5` · `@tanstack/react-query@5` · `react-hook-form@7` · `zod@4` · `tailwindcss@4` — pinned to exact majors, `pnpm@9.15.4` via `packageManager`. Lockfiles present. No CI, so no automated dependency review.

### External services called
| Service | Endpoint | Data sent | Guard |
|---|---|---|---|
| NVIDIA NIM (chat) | `integrate.api.nvidia.com` | 🔴 BOM dialogue (invention description), 🟠 negotiation message plaintext, 🟡 search queries | API key only |
| NVIDIA (embeddings) | `integrate.api.nvidia.com/v1/embeddings` | 🟢 title + `public_description` + tags only ✅ | API key |
| Anthropic | `api.anthropic.com` | 🟠 deal terms, party names, fee amounts (contract drafting) | API key |
| Stripe | `api.stripe.com` | payment intents, transfers | secret key; webhook HMAC verified ✅ |
| Persona | `withpersona.com` | user email as `reference-id` | API key; webhook HMAC ⚠ bypassed in mock mode |
| SMTP | configurable | verification links, digests | ⚠ `start_tls=False` hardcoded (`integrations/email.py:31`) |
| Cloudflare | tunnel | all traffic, TLS-terminated | — |

**No SSRF surface exists.** Every outbound URL is a module constant or a settings value. `source_url` on library resources is validated to `http(s)` and **stored only, never fetched** (`schemas/open_resource.py:_check_url`; grep confirms no fetch of it). No XML parsing anywhere (no XXE surface). No `pickle`/`yaml.load`/`eval`/`exec`/`subprocess` in the backend. No document conversion, OCR, or PDF pipeline — so no command-injection surface.

---

## 7. What is missing that should exist (absent controls are findings)

These surfaced during recon and are already confirmed against the code and the running host. Full write-ups with CVSS, attack paths, and patches come in Phase 3 — recorded here so nothing is lost, and because two of them are live right now.

### 🔴 Confirmed, live, exploitable today

**R-1 — Tiered disclosure does not exist at the API layer.** `ListingResponse` (`api/schemas/listing.py:52-70`) embeds `description`, `bom_items[]`, `equipment_requirements`, `batch_size_definition`, and `vault_assets[]` filenames. `GET /api/v1/listings/public` is unauthenticated (`api/listings.py:75-81`) and `GET /api/v1/listings/{id}` accepts `get_optional_user` (`:84-107`). nginx proxies `/api/` to the internet. **Verified empirically** against the running instance: one unauthenticated GET returned the private `description` plus a complete 4-item BOM with specifications and criticality flags. The `public_description` field — the intended teaser — exists and is *also* returned, alongside everything it was meant to replace. Pagination `offset` is unbounded and the default rate limit is 1000/min, so the entire corpus is scrapable in seconds by an anonymous client. This is the competitor-harvesting adversary from the directive, and it needs no account.

**R-2 — KYC is in mock mode on the public deployment.** `.env` has `KYC_MOCK_MODE=true`. Because `APP_ENV=staging`, `validate_production_settings` (`core/config.py:117-135`) returns `[]` and the boot guard that would have refused this never fires. Consequence chain: (a) `POST /me/kyc/complete` self-approves any account to `VERIFIED` (`api/users.py:172-204`); (b) `verify_persona_webhook_signature` returns `True` for **any** request (`integrations/kyc.py:55-56`), so the unauthenticated `/api/v1/webhooks/kyc` endpoint will set a matching user's status. `require_verified_user` — the gate on listing creation, proposals, transactions, and vault download — is therefore satisfiable by any anonymous registrant in three API calls.

**R-3 — `APP_ENV=staging` disables every production guard.** One string. It nullifies the insecure-default validator (SECRET_KEY / VAULT_ENCRYPTION_KEY dev values would boot silently), suppresses the HSTS header (`main.py:171`), and keeps logs in dev console format instead of JSON (`core/logging.py:24`). I could not read `.env` secret values (correctly blocked), so **I cannot confirm whether SECRET_KEY and VAULT_ENCRYPTION_KEY are still development defaults** — and neither can the application, because the check that would tell you is switched off. This needs a manual answer from you.

**R-4 — Refresh cookie lacks `Secure` on an HTTPS site.** `COOKIE_SECURE` is absent from `.env` → defaults `False` (`core/config.py:78`), while `COOKIE_AUTH_ENABLED` defaults `True`. The 7-day `saha_refresh` cookie is set without the `Secure` attribute on `https://sahasolutions.com`. `CORS_ORIGINS` additionally whitelists two plaintext origins (`http://10.0.0.228`, `:8080`) with `allow_credentials=True`.

**R-5 — Data-plane services are open to the LAN.** MinIO `minioadmin:minioadmin` on `0.0.0.0:9000/9001` (the vault bucket, plus **unencrypted contracts** and avatars); Redis unauthenticated on `0.0.0.0:6379` (**plaintext invention descriptions** in `bom:session:*`); Qdrant unauthenticated on `0.0.0.0:6333`; Mailpit UI on `0.0.0.0:8025` (**every email, including email-verification JWTs**); Grafana `admin:admin` on `0.0.0.0:3001`. All confirmed via `ss -ltnp`.

**R-6 — Admin console persists the refresh token to `localStorage`.** `apps/admin/store/auth.ts:26` — `partialize: (s) => ({ accessToken, refreshToken, user })`. The marketplace app deliberately excludes it and documents why (`apps/frontend/store/auth.ts:39-43`). The higher-privilege application has the weaker token store: one XSS in the console yields 7 days of admin persistence.

**R-7 — `X-Forwarded-For` is attacker-controlled.** nginx uses `$proxy_add_x_forwarded_for`, which *appends*; the backend reads `forwarded.split(",")[0]` — the **first**, client-supplied element — in both `_rate_limit_key` (`core/ratelimit.py:48-50`) and `_client_ip` (`api/auth.py:31-32`, `api/users.py:31-32`). IP-based rate limiting is therefore bypassable by header rotation, and `audit_logs.ip_address` is forgeable. That column is Postgres `INET`; a non-IP header value plausibly aborts the audit write — **needs runtime verification before I state it as fact.**

### 🟠 Confirmed design gaps

**R-8 — The escrow release predicate is wrong.** `POST /{id}/disburse` uses `_check_access` (either party) rather than `_check_buyer` (`api/settlement.py:95`). The **seller can release escrow to themselves** the moment it is funded, with no buyer approval, inspection period, or dispute window.

**R-9 — Contracts are executed unilaterally.** `POST /{id}/sign` moves `CONTRACT_REVIEW → SIGNED` when **either** party calls it (`api/transactions.py:107-124`, `services/transactions.py:185-210`). Nothing records *who* signed, nothing requires both, and DocuSign is a `logger.info` stub. The `signed` state — which unlocks escrow and, transitively, vault access — is reachable by one party acting alone.

**R-10 — There is no NDA gate.** `ProposalStatus.NDA_PENDING`, `NDA_SIGNED`, `nda_docusign_envelope_id`, and `nda_signed_at` all exist in the schema; **no code path ever sets them** (grep-confirmed). Disclosure is gated on *escrow funded*, not on NDA execution. There is no diligence tier: a buyer sees teaser-level data (which today means everything, per R-1), then jumps straight to post-payment full access.

**R-11 — There is no evidentiary integrity layer.** `audit_logs` is an ordinary read-write table owned by the same role the application uses. No hash chain, no canonical serialization, no signatures, no RFC 3161 timestamps, no external anchoring, no WORM storage, no exportable evidence package. An operator with DB access can rewrite history undetectably, and nothing produced here would survive a challenge in a dispute.

**R-12 — Confidential content leaves the trust boundary for LLM inference.** `services/messages.py:28-45` sends negotiation message plaintext to NVIDIA to classify contact info; `services/listings.py:75-105` sends the full BOM-authoring transcript. There is no DPA analysis in the repo, no user disclosure, no opt-out, no residency control. For a platform whose stated premise is that confidentiality failures are existential, this is a structural issue, not a bug.

**R-13 — Upload validation is header-trust only.** Vault: no content-type validation at all, size checked *after* full read into memory (`api/listings.py:217-219`). Avatars: `content_type` header trusted, no magic-byte verification (`services/profile.py:35-50`). No malware scanning anywhere. No archive-bomb or polyglot defence.

**R-14 — Bulk PII exposure to any member.** `GET /api/v1/materials` returns `seller_email` for every listing (`api/materials.py:54-71`); `GET /api/v1/communities/{id}/members` returns every member's email for any public community to any authenticated user (`api/communities.py:175-189`). Registration is open and self-verifiable (R-2), so the member directory is effectively public.

**R-15 — Access token in a URL query string.** `GET /api/v1/notifications/stream?token=…` (`api/notifications.py:55`) — nginx's default `combined` log format records `$request` including the query string, so live access tokens are written to `/var/log/nginx/access.log`.

**R-16 — Authorization is scattered, with no shared primitive.** Six distinct hand-rolled ownership-check shapes across eight modules. R-8 is exactly the failure mode this produces: one handler picked the wrong helper and nothing caught it.

**R-17 — No CI, therefore no enforcement.** No `.github/`, no pipeline definitions anywhere. 129 tests exist and are good, but nothing runs them automatically. No SAST, no dependency audit, no secret scanning, no IaC scanning — and no IaC to scan.

**R-18 — No detection or alerting.** Prometheus + Loki + Grafana are deployed but no security metrics, no alert rules, no routing. Nothing fires on mass download, enumeration, privilege change, or failed-authorization spikes. Audit logs are queryable only through the admin console UI.

**R-19 — No data-retention or deletion capability.** No account deletion, no data export, no retention policy, no erasure path. For PIPEDA/GDPR this is a compliance gap; it also means the "immutable evidence vs. erasure rights" conflict has not been designed for at all.

### ✅ Genuinely clean — stated so it isn't re-litigated
- **No SQL injection.** All raw SQL is parameterised; f-strings interpolate only module constants (`services/demand.py:13-49`, `services/search.py:133-145`). ORM filters use bound `ilike` patterns throughout.
- **No SSRF, no XXE, no command injection, no SSTI, no unsafe deserialization.** No fetch of user-supplied URLs, no XML parsing, no subprocess/eval/pickle. Verified by grep.
- **No secrets in git history.** Pickaxe across all refs for `sk-ant-`/`sk_live_`/`whsec_`/`nvapi-`/`AKIA` returns only `.env.example` placeholders and test fixtures. `.env` is correctly gitignored and never committed.
- **No mass assignment.** Every request body is a closed Pydantic model with explicit fields; `role` is constrained to `{creator, manufacturer}` at registration (`schemas/auth.py:19-21`); `owner_id`/`creator_id`/`seller_id` are always taken from the authenticated principal, never the body.
- **No JWT algorithm confusion.** `jwt.decode(..., algorithms=[settings.JWT_ALGORITHM])` — a fixed single-element list; `none` cannot be negotiated. Token `type` claim is checked on every decode path.
- **Refresh-token rotation is correctly implemented,** including family-based reuse detection that nukes the whole family on replay (`services/auth.py:133-144`).
- **Vault asset lookup is scoped to the transaction's listing** — no IDOR on the highest-value object in the system (`services/settlement.py:208-213`).
- **Admin tooling uses the same authorization model** as everything else; no bypass path.
- **Qdrant payloads carry only teaser-tier fields** — the one place staged disclosure was implemented correctly.
- **The transaction state machine is explicit** with a `_SYSTEM_ONLY_TARGETS` set preventing a party from self-declaring `escrow_funded` or `completed` (`services/transactions.py:29-52`).
- **Stripe webhook verification is correct** — HMAC-SHA256, `compare_digest`, 300-second replay window, hard-fails on an unset secret.
- **Password storage:** bcrypt cost 12, 72-byte guard, 12-char minimum with a common-password denylist, plus a constant-time dummy-hash path that closes the login user-enumeration oracle (`services/auth.py:21, 65`).

---

## 8. Confidence and coverage

| Area | Confidence | Basis / caveat |
|---|---|---|
| Route inventory & guards | **High** | Every handler read; all 89 classified; none ambiguous. |
| Data model & classification | **High** | All models read line by line. |
| Document lifecycle | **High** | Traced end to end through code. |
| Live deployment posture | **High** | Verified against the running host: `ss`, nginx, cloudflared, systemd, live `curl`. |
| Injection / SSRF / deserialization | **High** | Exhaustive grep + manual read of every raw-SQL and outbound-HTTP site. |
| Business logic | **Medium-high** | Logic read thoroughly; concurrency behaviour (TOCTOU on accept/disburse) needs runtime testing — there is no row-level locking anywhere, which I will pressure-test in Phase 3. |
| Frontend | **Medium** | Auth, token storage, and XSS sinks reviewed (no `dangerouslySetInnerHTML`/`innerHTML`/`eval` anywhere ✅). UI logic not exhaustively reviewed. |
| Dependency CVEs | **Low** | **No scanner was run.** No CVE is claimed. `pip-audit`/`osv-scanner` against `uv.lock` is required. |
| Secret values in `.env` | **None** | Reading `.env` was correctly blocked by policy. Whether `SECRET_KEY`/`VAULT_ENCRYPTION_KEY` are still dev defaults is **unknown and unknowable from code** — see R-3. |
| Backup / DR | **None** | No backup configuration found anywhere in the repo or on the host. Cannot assess restore, encryption, or retention because nothing exists to assess. |
| Cloudflare configuration | **None** | WAF rules, rate limiting, Access policies, and TLS settings live in the Cloudflare dashboard, outside this repo. |
| Postgres role grants | **Low** | `grant-saha-permissions.sql` seen but live grants not enumerated. |

### Explicitly not covered
1. Runtime/DAST testing — no authenticated fuzzing, no race-condition testing, no concurrency probing.
2. Dependency CVE scan.
3. Cloudflare-side configuration.
4. Frontend UI logic beyond auth/token/XSS.
5. Postgres server hardening, `pg_hba.conf`, live role grants.
6. The Jetson host OS itself — patch level, SSH exposure, firewall (`ufw`/`iptables`) rules, physical security.
7. `saha-dev-infra/seed/seed_demo_data.py` and the migration SQL files (read for schema, not audited as code).

---

## 9. What I need from you before Phase 3

1. **Jurisdictions** — which privacy regimes actually apply? It changes the retention, residency, and erasure findings materially.
2. **Are `SECRET_KEY` and `VAULT_ENCRYPTION_KEY` still the `.env.example` defaults?** Check without pasting them here. If they are, R-3 escalates to critical: every JWT and every vault object is decryptable by anyone who has read the repo.
3. **Is `STRIPE_SECRET_KEY` set to a live key, or empty/`REPLACE_ME`?** If mock, then `escrow_funded` is reachable with no money moving — which combined with R-2 means a free path to another party's vault once they accept an offer.
4. **Are the 100 seeded listings and 10 demo accounts real or synthetic?** R-1 is a live trade-secret leak if any real IP has been listed; a lower-severity design flaw if the corpus is entirely demo data.
5. **Is this host on a trusted LAN, or a shared network?** R-5's severity turns on this.

---

*End of Phase 1. Phases 2–5 (threat model, full vulnerability audit, findings, remediation plan) and 6–7 (feature gaps, target architecture) follow on your go-ahead. No code has been modified.*
