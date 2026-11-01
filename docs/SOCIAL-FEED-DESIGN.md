# Social feed + profile reputation — design

## Current implementation — 2026-11-01

The original ranking/reputation rationale below is retained. Current ordinary
collaboration requires confirmed email or existing verified KYC; older statements
below prescribing KYC for every social write or a standing threshold for creating
a community are historical design proposals, not current authorization behavior.

The feed and institution updates now share a multimedia composer and interaction
cards: six attachments/one video, bounded MIME-checked upload, audience-inherited
media access, UUID-backed member mentions, six expressive reactions, follows,
saved posts, search, one-level replies and sharing with thoughts. Reactions remain
separate from reputation votes; edits reset endorsements. Media is not scanned by
the text classifier. See the [User guide](USER-GUIDE.md), [current security
boundaries](../security/CURRENT-SECURITY.md) and [interactive backend reference](architecture/SAHA_BACKEND.html).

Private projects are invite-only and can start without a patent. Project tasks and
references are access-controlled; institution updates stay public. Chat uses
Matrix/Element and has no plaintext fallback. Neither ordinary posts nor uploaded
post media are end-to-end encrypted.

---


**Date:** 2026-08-06 · **Status:** design, implementation in progress
**Related:** [security/AUDIT.md](../security/AUDIT.md) · [security/ROADMAP.md](../security/ROADMAP.md)

---

## 1. What was asked for, and one thing I'd change

Asked for: a social feed (post / comment / like), a LinkedIn-style profile page, and
Reddit-style profile rating driven by how the community responds to someone.

I researched how Reddit actually computes karma and ranks content, and read
Reddit's own `_sorts.pyx`. Almost all of it transfers. **One part should not be
copied directly, and it is the most important part.**

### Reddit karma is a popularity measure. Saha needs a credibility measure.

On Reddit, karma answers *"do people enjoy this person's contributions?"* On a
platform where someone decides whether to hand a counterparty unfiled patent
claims, the question is *"can I trust this person with something irreversible?"*
Those are different questions, and a single number cannot answer both.

Three concrete problems with importing karma as-is:

1. **It is cheap to earn and expensive to verify.** Post agreeable content, get
   karma. Nothing about that predicts whether someone honours a licence term.
2. **It launders.** If social karma and trading reputation are one score, a user
   farms engagement and arrives at a negotiation looking like a proven
   counterparty. That is the failure mode to design against, not to discover later.
3. **Saha already has a hard signal.** Transaction reviews require a *completed
   deal* — expensive to fake, and directly about the behaviour that matters.
   Diluting it with post likes makes it weaker, not richer.

### The design: two tracks, never summed

| | **Standing** (social) | **Track record** (transactional) |
|---|---|---|
| Earned from | posts, comments, votes received | completed deals + counterparty reviews |
| Cost to earn | low | high — requires a real transaction |
| Answers | "does this person contribute usefully?" | "does this person deliver?" |
| Displayed as | a number with tier label | ★ rating + deal count |
| Gates | downvoting, community creation, post frequency | nothing — it is *information*, shown to counterparties |

Both appear on the profile. **They are never added together and never collapsed
into one badge.** A user with 5,000 standing and zero completed deals reads
exactly as what they are: an active community member who has never traded.

This is the Stack Overflow insight rather than the Reddit one — reputation should
unlock *privileges* proportionate to how it was earned, not act as a universal
score. Standing gates social privileges. It does not gate anything commercial.

---

## 2. Reddit mechanics worth copying, with the real formulas

Taken from Reddit's `_sorts.pyx` (their published implementation), not from
secondary descriptions.

### 2.1 Hot ranking — for the feed

```
sign  = +1 if score > 0, -1 if score < 0, else 0
order = log10(max(|score|, 1))
hot   = round(sign * order + (created_utc - 1134028003) / 45000, 7)
```

Two properties make this the right default, and both matter here:

- **Logarithmic vote weight.** The first 10 votes move a post as much as the next
  100. New contributors are not buried under established ones.
- **45,000-second time divisor (~12.5 h).** Each ~12.5 hours of age costs a post
  one order of magnitude of score. A feed on a platform this size would otherwise
  freeze on whatever went well once.

We keep the constants. They are well-tuned and there is no reason to invent our own.

### 2.2 Wilson lower bound — for ranking comments

Raw score ranks a 300↑/100↓ comment above a 10↑/0↓ one, which is wrong: the
second has better evidence of quality. Reddit's "best" sort uses the lower bound
of the Wilson score interval at 80% confidence:

```
z     = 1.281551565545
n     = ups + downs
p     = ups / n
left  = p + z²/(2n)
right = z * sqrt(p(1-p)/n + z²/(4n²))
score = (left - right) / (1 + z²/n)
```

This asks *"given this sample, what is the pessimistic estimate of the true
approval rate?"* Small samples are penalised until they earn confidence. It is
the correct default for comments and we use it.

### 2.3 Vote fuzzing — deliberately NOT copied

Reddit randomises displayed up/down counts so bot operators cannot tell whether
their votes landed. It is a sound defence **for an anonymous platform**.

Saha is KYC-verified with real identities and an append-only audit log. Fuzzing
here would make displayed numbers untrustworthy while buying nothing — the
Sybil-resistance that fuzzing approximates, we get directly from identity
verification. Votes are instead **attributable and auditable**: one row per
(voter, target), enforced by a unique constraint.

Stating this explicitly because "Reddit does it" is not a reason on its own.

### 2.4 Diminishing returns

Reddit applies undisclosed sub-linear scaling so one viral post cannot manufacture
an established-looking account. We implement it openly:

```
standing_from_item = round(K * ln(1 + max(net_score, 0)))     # K = 6
per_item_cap       = 50
```

Logarithmic, capped per item, and **published in the UI** rather than secret.
A secret formula on a professional platform invites reverse-engineering; a stated
one invites contribution.

---

## 3. Anti-gaming

Ranked by how likely each is to actually be attempted here.

| Attack | Defence |
|---|---|
| Self-voting | Rejected at the service layer and by a DB check constraint |
| Double-voting | `UNIQUE (voter_id, target_type, target_id)`; re-voting updates in place |
| Sock-puppet ring | Voting requires `kyc_status = verified` — the same gate as trading. Sybils cost a real identity check |
| Reciprocal-vote ring | **Per-pair decay**: the *n*-th vote from voter A on author B's content contributes `1/n` weight. Two accounts boosting each other converge on nothing |
| Brigading a downvote | Downvoting requires ≥ 50 standing (Stack Overflow's model). New accounts can upvote from day one and must earn the ability to penalise |
| Vote-then-edit | Material edits after the first vote reset the item's score and flag it `edited` |
| Karma farming via volume | Per-item cap (50) + log scaling; posting more low-value items yields progressively less |
| Deleting downvoted content | Standing is computed from **all** authored items including deleted ones — deletion hides content, it does not launder score |

Rate limits reuse the existing tiers: `WRITE_LIMIT` for posts/comments, a new
`VOTE_LIMIT` of 120/hour.

---

## 4. The confidentiality problem this feature creates

**This is the part of the design I would push back on hardest if it were skipped.**

Saha's premise is that disclosing an invention prematurely destroys its novelty
permanently and in every jurisdiction. We just spent an audit closing paths that
leaked BOM data. Now we are adding a feature whose entire purpose is *encouraging
members to post about what they are working on.*

That is not a reason not to build it. It is a reason to build it with a guard.

### Composer disclosure check

The same deterministic-classifier pattern as `services/contact_detect.py` — no
LLM, no network, no plaintext leaving the boundary — scanning for language that
reads like unpublished technical disclosure:

- process/composition specifics ("we're using a 3% palladium catalyst at 80°C")
- explicit novelty claims ("nobody has done this before", "our secret sauce")
- filing status hints ("before we file", "patent pending", "provisional")
- quantities with units in a technical context

On a hit the composer shows a **non-blocking** warning:

> This post may describe unpublished technical detail. Public posts are visible
> to anyone, including competitors, and public disclosure can affect patent
> novelty. Consider posting this in a private community instead.
> [Post anyway] [Move to a community] [Edit]

**Warn, never block.** The member owns their disclosure decision and a false
positive must not prevent a legitimate post. But the platform should not let
someone destroy their own patentability without one clear moment of friction.

Warnings and the member's choice are recorded in the audit log — that is the
evidence trail if a dispute ever turns on when something became public.

### Visibility is explicit, and defaults to the narrower option

Every post picks one at composition time:

| Visibility | Audience | Default for |
|---|---|---|
| `public` | anyone, unauthenticated | — |
| `members` | any signed-in Saha member | **default** |
| `community` | one community's members | posts created from a community |

Default `members`, not `public`. Someone should have to *choose* to broadcast to
the open internet. This mirrors the `PublicListingResponse` / `OwnerListingResponse`
split from SAHA-003: tiering enforced at the response model, not by filtering.

---

## 4b. Content safety — harmful content

Separate concern from §4, and a **different response**. The disclosure guard
*warns* to protect an author from themselves and is dismissible. This *restricts*
to protect third parties, and the author does not get the final say.

### The problem with the obvious approach

Saha is an IP and manufacturing marketplace. Members legitimately discuss
energetic materials, pharmaceutical synthesis, agricultural nitrates,
biotechnology and industrial chemistry — every day, as their job. A keyword
blocklist would delete the platform's actual subject matter while barely
inconveniencing anyone determined to misuse it. Worst of both outcomes.

### Detection is intent × subject, never subject alone

```
harmful SUBJECT (weapon, toxin, illicit synthesis, …)
  AND actionable INTENT (step-by-step instruction, evasion, targeting a
      person, acquisition-for-harm)
  → restrict

subject without intent  → allow   "our fertiliser improves nitrogen uptake"
intent without subject  → allow   "step-by-step guide to filing a provisional"
```

### Four outcomes

| Action | Effect | Applies to |
|---|---|---|
| `ALLOW` | published normally | no pairing detected |
| `FLAG` | published, queued for review | subject + intent in a defensive **and** professional frame ("detecting X for regulatory screening") |
| `HOLD` | **not published**; admin queue | subject + instruction/acquisition |
| `BLOCK` | refused; cannot be posted anywhere | targeting a person, evasion language, credible threats, zero-tolerance categories |

**Public visibility escalates `FLAG` → `HOLD`.** An unbounded audience and
irreversible harm means ambiguity resolves toward holding.

### Three deliberate asymmetries

1. **The classifier can hold, but never release.** Only an admin review moves a
   post out of `HELD`. A wrongly-held post costs a delay; a wrongly-published one
   may not be recoverable. Enforced by a test that walks the AST and fails if any
   function other than `review_post()` assigns `APPROVED`.

2. **Self-harm is met with support, not enforcement.** Held rather than blocked,
   and the author sees a helpline rather than a policy citation. Someone in
   crisis should not receive an enforcement notice. Tested.

3. **Reports queue, they do not remove.** A report button that auto-hides hands
   any member a veto over any other. Three independent reports pull a post — but
   a report alleging real-world harm pulls it immediately, because the downside
   of leaving harmful instructions up while a queue drains is not symmetric with
   holding a legitimate post for a few hours.

### What the classifier does not do

* **Contains no procedure.** It matches structural language patterns only —
  never a synthesis route, quantity or precursor combination. A moderation
  classifier that embeds a recipe is a liability, not a control. Tested by
  asserting the module contains no quantity-with-unit patterns.
* **Never explains what tripped it.** Author messages say what happened without
  naming the trigger; a message that says which phrase failed is a bypass guide.
* **Makes no network call.** Member content does not leave the trust boundary to
  be classified — same reasoning as SAHA-013.
* **Does not decide alone.** Everything above `ALLOW` reaches a human, and every
  decision is written to the append-only audit chain with the admin's identity.

### Known limits, stated plainly

Regex classification catches careless and opportunistic misuse. It will not stop
a determined actor who paraphrases, and it will produce false positives on
unusual phrasing. That is why nothing is auto-published out of a hold and why
every category above `ALLOW` reaches a person. Treat it as a filter that reduces
reviewer load, not as a guarantee.

## 5. Data model

```
posts
  id, author_id, visibility, community_id?, kind, title?, body,
  link_url?, listing_id?, resource_id?,           -- optional attachments
  score, up_count, down_count, comment_count,
  hot_rank, disclosure_flagged, edited_at?, deleted_at?, created_at

post_comments
  id, post_id, author_id, parent_id?,             -- one level of threading
  body, score, up_count, down_count,
  confidence,                                     -- Wilson lower bound
  edited_at?, deleted_at?, created_at

votes
  id, voter_id, target_type ('post'|'comment'), target_id, value (+1|-1), created_at
  UNIQUE (voter_id, target_type, target_id)
  CHECK  (value IN (-1, 1))

user_profiles            -- LinkedIn-style, all optional, all self-asserted
  user_id PK, headline, about, location, website_url,
  skills text[], experience jsonb, featured jsonb, updated_at

user_standing            -- derived, recomputed; never authoritative on its own
  user_id PK, post_standing, comment_standing, total_standing,
  posts_count, comments_count, computed_at
```

Deliberately **not** stored: a merged reputation number. Standing and track record
are read separately and rendered separately.

---

## 6. Profile page — LinkedIn structure, Saha substance

Research on LinkedIn's 2026 layout says the first 10–20 seconds are decided by
photo, headline, About and Featured. We keep that ordering.

The difference: LinkedIn is entirely self-asserted. On a platform where profiles
inform whether to trade IP, **self-asserted claims sit visually below verified
ones**.

```
┌──────────────────────────────────────────────────────────────┐
│  [avatar]  Full Name                          ✓ KYC verified │
│            Headline (220 chars)                              │
│            Location · Member since · [Message]               │
├──────────────────────────────────────────────────────────────┤
│  VERIFIED — platform data, not self-reported                 │
│   ★ 4.8 track record (12 deals)   ·   1,240 standing (Trusted)│
│   3 listings published · 8 library contributions · 4 communities│
├──────────────────────────────────────────────────────────────┤
│  About            (2,600 chars, first-person)                │
│  Featured         (pinned listings / library entries / posts) │
│  Experience       (self-asserted, marked as such)             │
│  Skills           (max 50)                                    │
│  Activity         (recent posts + comments, votes hidden)     │
└──────────────────────────────────────────────────────────────┘
```

Standing tiers, from the published formula:

| Standing | Tier | Unlocks |
|---|---|---|
| 0 | New | post, comment, upvote |
| 50 | Contributor | downvote |
| 250 | Established | create communities |
| 1,000 | Trusted | flag content for moderation |
| 5,000 | Distinguished | — (recognition only) |

Track record has **no tiers and unlocks nothing**. It is shown to counterparties
as information. Turning "has done many deals" into platform privilege would
create exactly the conflict of interest this split exists to avoid.

---

## 7. Other features worth adding — assessed, not assumed

Researched against what comparable platforms do. Ordered by value here, with the
ones I would *not* build called out.

**Build now (in this change)**
- **Post kinds** — `update` / `question` / `showcase`. Cheap, and makes the feed
  sortable by intent rather than one undifferentiated stream.
- **Attach a listing or library resource** to a post. This is the feature that
  makes the feed *Saha's* rather than a generic timeline: "here's what I'm
  building" links to the actual asset.
- **Wilson-ranked comments**, one level of threading. Deeper nesting is where
  discussion quality goes to die on a platform this size.
- **Save / bookmark.** Trivially cheap, high daily utility.
- **Follow a member** — feed filter, plus a notification on their posts.

**Build next**
- **Moderator queue SLA + alerting** — a queue nobody watches is not a control. Prometheus metric on oldest-held age, alert past 24 h.
- **Appeal path** for rejected posts, so a wrong call is correctable by a second reviewer.
- **Repeat-offender signals** — an account whose posts are repeatedly rejected should surface, without auto-banning.
- **@mentions** with notification (reuses the existing notification service).
- **Weekly digest of top posts** — the library digest scheduler already exists.
- **Report → moderation queue**, wired into the admin console's existing pattern.

**Deliberately not building**
- **Direct messaging.** Saha *blocks* off-platform contact exchange in
  negotiations by design. Adding an unmonitored DM channel would route around a
  deliberate product decision and the audit trail that depends on it.
- **Public follower counts.** Turns a professional network into a popularity
  contest and creates a second gameable number.
- **Post editing without trace.** Edits after votes reset the score and mark the
  item `edited` — an unmarked edit on a platform that trades on evidence is a
  small forgery.
- **Vote fuzzing.** §2.3.

---

## 8. Build order

1. Models + migration
2. Standing engine (`services/standing.py`) — Wilson, hot, per-pair decay
3. Disclosure classifier (`services/disclosure.py`)
4. Posts / comments / votes service + API
5. Profile service + API
6. Tests, including gaming-resistance cases
7. Frontend: feed, composer with the disclosure guard, profile page
