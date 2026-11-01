# Saha experience and route map

Session follow-up: the home CTA, account menus and route guards now share a validated lifecycle; signed-in members bypass signup/login forms. See [Session consistency](SESSION-CONSISTENCY.md).

Updated 2026-11-01: Projects now supports independent, invite-only workspaces, reference cards, section shortcuts and existing Matrix chat. Feed and institution posts share multimedia/mention/reaction components. The in-app guide and home journey reflect this. Earlier UI-only build IDs below are a historical milestone; this expanded release requires both November migrations. See [Current status](CURRENT-STATUS.md) and [User guide](USER-GUIDE.md).

## Design intent

One Saha identity across the public website, account flows, collaboration workspace,
legacy IP tools and private administration. Forest green actions, sage selected
states, warm paper backgrounds, white surfaces, consistent borders and readable
Geist text. Fraunces is reserved for editorial headings. All fonts are local.

The public header always leads to Explore, Projects and Institutions. The logo
always returns home. Signed-in members keep the same header and gain a grouped
sidebar on content pages. On small screens an explicit navigation disclosure
replaces the old horizontally scrolling list of thirteen destinations. The IP
section remains available as a secondary expandable group. Admins retain the
ordinary collaboration navigation plus their administration entry.

## Routes and journeys

| Intent | Destination | Next step |
| --- | --- | --- |
| Understand Saha | `/` | Search research, browse projects, meet institutions |
| Learn the platform | `/guide` | Guided three-step journey and complete tool directory |
| Find research | `/explore?q=…&type=…` | Read source, inspect rights, save a resource, open a source-linked project |
| Work on an idea | `/projects` and `/projects/:id` | Create an independent invite-only workspace, add references, invite members and use team tasks |
| Start from a resource | `/projects?source=:id` | Sign in without losing source; create project |
| Find institutions | `/institutions` and `/institutions/:id` | Join, read/post updates, comment |
| Personal starting point | `/dashboard` | Collections, projects, feed, institutions |
| Private research | `/dashboard/collections` | Sources, personal notes, saved searches |
| Share progress | `/dashboard/feed` and `/dashboard/feed/:id` | Posts and discussions |
| Interest groups | `/dashboard/community` and `/dashboard/community/:id` | Membership and space management |
| Contribute research | `/dashboard/library` | Submit a source for curation |
| IP tools | `/dashboard/marketplace` | Listings, discovery, materials, demand, proposals, transactions |
| Identity verification for transactions | `/dashboard/marketplace#verification` | Existing KYC flow |
| Account and email verification | `/dashboard/profile`, `/dashboard/security` | Profile, email confirmation, MFA |
| Private platform administration | Existing private nginx port 8080 | Grouped community, marketplace and platform tools |

`/dashboard/institutions` redirects to `/institutions` so existing bookmarks keep
working without maintaining two different directories. Detail breadcrumbs show a
readable label, never raw UUIDs. Breadcrumbs do not link to nonexistent directory
indexes. The route source is `apps/frontend/lib/navigation.ts`.

Sign-in uses an allowlisted local `next` destination, retained when switching to
registration. Protected routes wait for client hydration before redirecting.
Anonymous project and institution contribution links retain context. Explore
searches update the URL, so submitted queries/filters can be bookmarked and
restored with browser Back.

## Interaction and accessibility

- Skip links, a single main landmark, visible keyboard focus, named navigation,
  current-page indicators and responsive menus.
- Profile and notification popovers use disclosure semantics instead of declaring
  ARIA menus without their required keyboard behavior. Escape returns focus to
  the trigger. The notification panel fits narrow viewports.
- Search forms have accessible labels; loading placeholders and actionable empty
  states distinguish loading, failure and absence of results.
- Disabled button links do not navigate. Reduced motion preferences are respected.
- Missing pages offer a route back; rendering failures offer retry. Public listing
  network failures are no longer disguised as missing listings.
- Transaction/KYC restrictions, institution visibility rules and chat encryption
  boundaries are unchanged. This release does not claim operational encrypted chat.

## Validation and release

Run `node scripts/test-ux-navigation.cjs`, both TypeScript checks, dependency
verification, and both production builds. The navigation tests cover real route
existence, selected navigation, breadcrumbs, safe post-auth continuation and the
anonymous server-side listing fetch. This is not a substitute for browser testing.

Browser acceptance on a socket-enabled host: check 360px, 768px and desktop layouts;
traverse home → search → project → sign-in → project, institution posts/comments,
collections, legacy transaction tools and private admin. Use keyboard navigation,
Escape, browser Back and a screen reader. Verify only one selected navigation item
within each navigation region, no viewport overflow, and no duplicate header.

The expanded social/workspace release requires both November migrations. On the October-migrated host use the release helper:

```sh
cd /home/hitarth/Downloads/saha
bash scripts/migrate-social-workspaces.sh && saha versions --local
# After local feature acceptance:
saha online && saha versions
```

Each `&&` gates the next action on success. The build command backs up old web
outputs and restores them if compilation fails. Existing nginx, tunnel, ports and
private admin exposure are preserved. A restricted coding session cannot restart
host services or certify that this release is public; use final served build IDs
from `saha versions` as the publication evidence.
