# Saha: open creativity and joint development

Updated 2026-11-01. Source implementation now includes multimedia posts, mentions, reactions and independent private projects. This is a product/implementation roadmap, not proof of deployment. See [User guide](USER-GUIDE.md) and [Current status](CURRENT-STATUS.md).

The primary product is a non-monetized open innovation community. People should be able to discover documented inventions, inspect rights/source information, find collaborators and build together. Transactions remain available as a secondary, existing capability.

## Core scope in this development slice

- Public Explore and curated library search, with clearly separate external searches in Google Patents, Espacenet and WIPO PATENTSCOPE. This is not an exhaustive internet index.
- Resource-level source, jurisdiction, rights evidence and notes. A publication or copyright license alone does not establish patent permission.
- Public institution pages, member posts/comments and optional human verification. The platform admin can enable verification requests; enabling requests never automatically awards badges. Institution name/domain changes invalidate verification.
- Random internal reference for every space, in a separate private record. Accessible only to the space owner and Saha platform administrators (the existing MFA-protected `admin` role). Ordinary members and community moderators cannot see it.
- Confirmed-email collaboration without financial KYC. Existing KYC-verified accounts retain collaboration access. Financial KYC remains on transaction workflows. Email confirmation is weaker Sybil resistance than KYC; retain rate limits, reports and abuse monitoring.
- Standalone invite-only project spaces with optional library sources, goals, skills, repository, contribution guide, private task board and reference cards. Project status updates require the task author, assignee or owner, with version checks to prevent lost updates.
- New private chat through Matrix/Element E2EE, not Saha server-side decryption. Public posts/comments remain intentionally public. Legacy chat is not retroactively encrypted.

## Ten additional features and sequencing

| Order | Feature | Smallest useful release | Why it helps |
|---|---|---|---|
| 1 | Collaborative project workspaces | **Implemented:** optional source, invite-only membership, goals, reference links with platform/type badges, search and manager pins, contribution guide, repository and versioned tasks. Owner-controlled stages are included. Next: pending invitation acceptance, milestones and self-claim tasks. | Moves people from reading a patent to working together. |
| 2 | Broad source ingestion with provenance | Versioned adapters for official bulk/API sources, publication/family deduplication, source timestamps, licensing evidence and transparent coverage counts. Credentials/quotas and source terms must be configured before enabling ingestion. | Builds an actual multi-source discovery corpus without claiming every indexed publication is openly reusable. |
| 3 | Personal collections and saved search alerts | **First slice implemented:** private collections, notes and saved queries. Next: topic/skills filters, configurable alerts/digest and safe export. | Makes research resumable and encourages useful return visits. |
| 4 | Reproducibility notebooks | Versioned experiment notes, materials/methods, results, negative findings and attachments; public/private controls independent of publication. | Turns ideas into reusable evidence and avoids duplicated experiments. |
| 5 | Contributor matching | Opt-in skills/interests and “help wanted” tasks; explain each match using public signals. Avoid inferring sensitive personal traits. | Helps a lone researcher find the missing expertise. |
| 6 | Open hardware/materials workspace | BOM versioning, standard units, alternatives, sourcing requests and local makerspace equipment availability. | Connects discovery to physical prototyping. |
| 7 | Attribution and contribution history | Versioned contributor credits, citations, project forks/remixes and provenance graph. Keep social standing separate from demonstrated project contributions and transaction reputation. | Gives people credit while preserving traceability of reused work. |
| 8 | Institution events and working groups | Public calls for collaboration, seminars, RSVP, recurring project sessions and institution-managed topic groups. | Helps institutions become active communities rather than static pages. |
| 9 | Community governance and trust tools | Shared role management, moderation queue for supported public content, appeals, code of conduct, spam controls and notification preferences. Encrypted-chat reports must be voluntarily submitted by participants; no covert server scanning. | Makes open participation sustainable while respecting private chat. |
| 10 | Accessible multilingual learning paths | Readable summaries with source citations, terminology glossary, translation, guided beginner tasks and keyboard/screen-reader checks. AI output remains editable and visibly distinct from source evidence. | Lets more people participate in technically demanding projects. |

Do not gate open collaboration on a paid plan or require a transaction to unlock a community/project. Do not add reputation points for payments to determine a person's creative contribution. Preserve the existing transaction routes as optional tools.

## Release gates

1. Privacy/authorization tests: references and evidence absent from public API/feed/search/export; private membership revocation enforced on every reading surface.
2. Institution tests: request policy off/on, meaningful evidence/reason, no self-approval, no self-issued badge, identity edits invalidate badges.
3. Chat tests: server rejects plaintext transport; private Matrix rooms require E2EE and disallow ordinary-member plaintext events/invites; removed members cannot receive future keys; device verification/recovery tested with two real clients before launch.
4. Database: explicitly ordered additive migrations tested on an isolated database, including repeat application. No automatic changes to the live database.
5. Project tests: source approval, membership, assignment and task-version conflicts. Full request tests against an isolated PostgreSQL service in CI remain necessary.
6. Discovery claims: show actual source coverage; never equate public patent documents with an open license. Curation is not a legal/scientific guarantee.

## Sources used for technical/product boundaries

- Matrix protocol: https://spec.matrix.org/latest/client-server-api/
- Element encryption/device recovery: https://web-docs.element.dev/e2ee.html
- EPO discovery: https://www.epo.org/en/searching-for-patents/technical/espacenet
- WIPO public-domain guide: https://www.wipo.int/edocs/pubdocs/en/wipo_pub_1063.pdf

Progress, concrete validation results and exact resume instructions live in `DEVELOPMENT-HISTORY.md`.
