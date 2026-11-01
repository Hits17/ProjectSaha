# Saha demo-data seeder

> **Development fixtures only — reviewed 2026-11-01.** Historical sample labels and claims below are not verified rights evidence. Publicly available patents/trademarks are not automatically free to reuse. This seeder creates approved/verified demonstration records and has no production-environment guard; never run it against the live application DB. Its dry-run still connects to the configured database. Use an isolated disposable database and do not reuse fixture credentials. See [Development](../../docs/DEVELOPMENT.md).

Loads the platform with **real, web-verified** open-source IP so the Open
Innovation Library and the marketplace have meaningful content to exercise every
screen, filter, and search path during manual testing.

## What it creates

| Dataset | Count | Notes |
|---|---|---|
| Open Innovation Library entries | **104** | 36 patents, 48 research papers, 20 trademarks — all admin-curated, `approved`, publicly visible |
| Test users (creators) | **10** | KYC-verified, email-verified, active |
| IP listings | **100** | 10 per user, each built on a real expired patent, with a bill of materials, published & indexed into Qdrant |

Every record is real and independently verifiable:

- **Patents** — expired/public-domain patents (Velcro, LEGO, PageRank, PCR,
  nylon, the transistor, RSA, …) plus royalty-free **pledged** patents (Google's
  Open Patent Non-Assertion Pledge, the Open COVID Pledge). Each `source_url` is
  a canonical `patents.google.com` link; titles/assignees were read from Google
  Patents.
- **Research papers** — open-access articles from **PLOS** journals, all licensed
  **CC BY 4.0**. Each `source_url` is a `doi.org` link resolved from the PLOS API.
- **Trademarks** — genericized former trademarks now free to use (aspirin,
  escalator, thermos, zipper, …), sourced from Wikipedia's genericized-trademark
  list. Licensed `public_domain`.
- **Listing patents** — 100 distinct expired US patents, each surfaced with a
  product-style title, a marketplace pitch that cites the (now public-domain)
  patent number, and a plausible BOM.

Datasets live in [`data/open_resources.json`](data/open_resources.json) and
[`data/listings.json`](data/listings.json) and can be regenerated/extended.

## Prerequisite — apply the enum migration first

The library now supports a `trademark` resource type. Add the enum value **as
the postgres superuser** (the app role does not own the type; `ALTER TYPE …
ADD VALUE` cannot run inside a transaction):

```bash
sudo -u postgres psql -d saha -c \
  "ALTER TYPE open_resource_type ADD VALUE IF NOT EXISTS 'trademark';"
```

Then restart the backend so it picks up the new value:

```bash
sudo systemctl restart saha-backend
```

## Run the seeder

Run it from the backend app so its `.env`, config, and models load, and so
listing publish uses the real NVIDIA embedding → Qdrant path:

```bash
cd apps/backend
uv run python ../../saha-dev-infra/seed/seed_demo_data.py --dry-run   # validate, writes nothing
uv run python ../../saha-dev-infra/seed/seed_demo_data.py             # apply
```

The run is **idempotent**: users are keyed by email, library entries by
identifier/URL, listings by (creator, title). Re-running skips anything that
already exists, so it is safe to run repeatedly. If the embedding API is briefly
unavailable, affected listings are still **published** (the publish path
tolerates Qdrant failure) but without a vector; the script reports exactly which
ones so you can re-run later to backfill.

## Test-user credentials

All ten share the password **`SahaDemo#2026!`**. All are `creator` role,
KYC-verified, and email-verified.

| # | Email | Name | Focus (their 10 listings) |
|---|---|---|---|
| 01 | demo01@saha.test | Dr. Elena Vasquez | Clean-energy hardware |
| 02 | demo02@saha.test | Marcus Chen | Medical devices |
| 03 | demo03@saha.test | Priya Nair | Consumer products |
| 04 | demo04@saha.test | Tomás Herrera | AgriTech & food processing |
| 05 | demo05@saha.test | Aisha Okafor | Industrial manufacturing |
| 06 | demo06@saha.test | David Kowalski | Materials science |
| 07 | demo07@saha.test | Sofia Rossi | Hardware & electronics |
| 08 | demo08@saha.test | Rahul Mehta | Biotech & pharma |
| 09 | demo09@saha.test | Grace Lindqvist | Chemicals & polymers |
| 10 | demo10@saha.test | Kenji Tanaka | Precision instruments |

> These are throwaway `@saha.test` accounts for a staging/demo environment. Do
> not reuse the shared password for anything real.

## Verify after seeding

```sql
SELECT resource_type, count(*) FROM open_resources GROUP BY resource_type;   -- 36 / 48 / 20
SELECT status, count(*) FROM ip_listings GROUP BY status;                    -- +100 published
SELECT count(*) FROM users WHERE email LIKE 'demo%@saha.test';               -- 10
```

Qdrant vector growth: `curl -s localhost:6333/collections/ip_listings | jq .result.points_count`.
