# Using Saha

Updated 2026-11-01. The new social/project interface is implemented; publication
status is recorded separately in [Current status](CURRENT-STATUS.md).

## Find your way around

Home, Explore, Institutions and Projects share the same header, colors, account
menu and navigation. The signed-in workspace adds Feed, Research collections,
Community, Library, account settings and optional IP tools. Breadcrumbs lead back
to the parent page, and sign-in preserves your selected resource or destination.
The in-app `/guide` page offers the same starting points.

Confirm your email in Account security before posting or contributing. Financial
KYC is not required for ordinary collaboration; existing verified-KYC accounts
also qualify. Transactions retain their own verification requirements.

## Sign-in and returning visits

On Home, signed-in members see **Continue to your workspace**. During session
restoration, Saha checks the account instead of displaying signup links. Visiting
Sign in or Create account while signed in takes you to your workspace (or the
requested destination). Email verification still works when signed in.

If the service cannot verify your session, use **Try again**; a temporary outage
does not erase the saved sign-in. Login/logout changes synchronize across tabs on
the same origin. The private admin console uses its own origin/session. See
[Session consistency](SESSION-CONSISTENCY.md) for behavior and current limitations.

## Start an independent project

1. Open **Projects → Start a project**. Enter a name and goal; optionally add
   skills, a repository URL and contribution guidance. No patent selection is required.
2. To associate research, start from a resource's **Find or start a project** link
   in Explore. The source must be an active approved library entry.
3. The workspace is invite-only. **Members & invitations** lets the owner or a
   moderator add an existing Saha member by email. This grants membership directly;
   a pending accept/decline invitation workflow is not yet implemented.
4. Members can use the task board and add reference links. Task authors, assignees
   and the owner can change task status. The owner changes the project stage.
   Stale changes are rejected rather than overwriting another person's update.
5. Use **References**, **Tasks**, **Encrypted chat** and **Members & invitations**
   shortcuts to move around the workspace. Projects only appear to their members.

Existing projects become private when the November migration runs; their members
and existing source association are retained. Project settings cannot publish the
workspace through the generic community visibility control.

## Keep reference documents together

Use **Add link** to give a reference a title, HTTPS URL and optional notes. Select
the platform (Drive, Docs, Sheets, Slides, Dropbox, OneDrive, GitHub, GitLab, Figma,
Notion, YouTube, Zenodo, OSF or another website) and the file type. The app suggests
a platform from the address; you can change it. Local bundled badges keep cards
consistent without contacting favicon services. The domain remains visible.

Search references or filter by document, spreadsheet, presentation, design/CAD,
code, dataset, image, video, paper, folder or other. Authors/managers can edit or
remove links; owners/moderators can pin important references. Copy link shares the
original address. Removing a reference does not delete the external file. A project
supports up to 200 references.

Files remain on the original platform and use that platform's sharing permissions.
Saha does not upload/copy/index linked files or verify their contents. A private
project does not make a publicly shared external document private. Reference
metadata and tasks are member-access-controlled, not end-to-end encrypted.

## Share progress and interact

The feed and institution updates use the same post composer and cards:

- Write an update, question or showcase; optionally add a title and a link.
- Add up to six attachments: JPEG/PNG/WebP images up to 8 MiB each and at most one
  MP4/WebM video up to 40 MiB. Add descriptions for accessibility. Videos load when
  requested and do not autoplay.
- Type `@` followed by at least two name characters, select a member using the
  keyboard or mouse, and add hashtags for searchable topics. Up to ten distinct
  members may be mentioned. Labels use the actual account name.
- Choose Members or Public for feed posts; institution posts are public. Review
  any disclosure warning. Posts and their media are not encrypted chat.
- React with Like, Celebrate, Support, Love, Insightful or Curious; comment and
  reply one level deep; follow authors; save posts; copy a link or share with thoughts.
- Switch between the general feed, followed authors and saved posts. Search text
  or hashtags; sort by newest, hot or top. Load more to continue browsing.

Editing clears existing votes/reactions. Deleting hides the post and its media.
Reports go to moderation; held posts wait for review. A shared link preserves the
original audience restrictions. “Share with thoughts” creates a link post, not a
native repost counter. Polls, scheduling, document attachments and video
transcoding are not implemented. The text classifier does not inspect visual media.

## Research, institutions and chat

Explore searches the curated library and offers external research database links;
it does not index every patent on the internet. Read source and rights evidence.
A publicly available patent is not automatically openly licensed or free to reuse.
Collections, notes and saved searches are private to your account. Automatic search
alerts are planned.

Institutions are public pages with updates and membership. Admins can enable
verification requests; the owner submits evidence and a different administrator
reviews it. Name/website changes invalidate the badge. A private internal space
reference is visible only to the owner and an MFA-qualified Saha platform admin,
not to ordinary members or community moderators.

Project/group chat opens in Element after linking a personal Matrix account with
Saha password/MFA step-up. The current deployment choice is **local testing only**.
If chat is unconfigured, Saha shows that state and offers no plaintext fallback.
Follow [Encrypted chat](ENCRYPTED-CHAT.md) for setup and required device tests.
Removal stops future room access but cannot erase messages someone already received.

IP listings, materials, proposals and transactions remain accessible as optional
workspace tools; they do not unlock or gate the collaboration features.
