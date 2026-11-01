#!/usr/bin/env python3
"""Regenerate offline, searchable architecture pages from the local source tree."""
import ast
import html
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/architecture'
ARCHIVE = OUT / 'archive'
ARCHIVE.mkdir(exist_ok=True)
for path in [*OUT.glob('*.html'), *OUT.glob('*.drawio')]:
    if not (ARCHIVE / path.name).exists():
        shutil.copy2(path, ARCHIVE / path.name)
esc = html.escape


def table(headers, rows):
    return '<div class="table-scroll"><table><thead><tr>' + ''.join(f'<th>{esc(str(c))}</th>' for c in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{esc(str(c))}</td>' for c in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def paragraphs(*items):
    return ''.join(f'<p>{esc(item)}</p>' for item in items)


def routes(app):
    rows = []
    for page in sorted((ROOT / 'apps' / app / 'app').rglob('page.tsx')):
        parts = [p for p in page.relative_to(ROOT / 'apps' / app / 'app').parts[:-1] if not p.startswith('(')]
        rows.append(('/' + '/'.join(parts), str(page.relative_to(ROOT))))
    return table(['URL pattern', 'Source file'], rows)


api_rows = []
for file in sorted((ROOT / 'apps/backend/app/api').glob('*.py')):
    tree = ast.parse(file.read_text())
    prefix = ''
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'APIRouter':
            prefix = next((k.value.value for k in node.keywords if k.arg == 'prefix' and isinstance(k.value, ast.Constant)), '')
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)): continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in {'get','post','put','patch','delete'} and dec.args and isinstance(dec.args[0], ast.Constant):
                deps = []
                for part in ast.walk(node.args):
                    if isinstance(part, ast.Call) and isinstance(part.func, ast.Name) and part.func.id == 'Depends' and part.args:
                        dep = ast.unparse(part.args[0])
                        if dep != 'get_db': deps.append(dep)
                api_rows.append((dec.func.attr.upper(), prefix + dec.args[0].value, ', '.join(deps) or 'See handler / global middleware', f'{file.name}:{node.lineno}'))

models = []
for file in sorted((ROOT / 'apps/backend/app/db/models').glob('*.py')):
    for node in ast.parse(file.read_text()).body:
        if not isinstance(node, ast.ClassDef): continue
        name = next((n.value.value for n in node.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__tablename__' for t in n.targets) and isinstance(n.value, ast.Constant)), None)
        if name:
            columns = [(n.target.id, ast.unparse(n.annotation)) for n in node.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and isinstance(n.value, ast.Call) and ast.unparse(n.value.func) == 'mapped_column']
            models.append((name, str(file.relative_to(ROOT)), columns))
schema = ''.join(f'<details><summary>{esc(name)} · {len(columns)} mapped columns</summary><p><code>{esc(file)}</code></p>{table(["Column", "Python mapping"], columns)}</details>' for name, file, columns in models)

ports = table(['Entry', 'Destination', 'Boundary'], [
    ('sahasolutions.com / www', 'Cloudflare Tunnel → nginx :80', 'Existing public hostnames'),
    ('/ and application pages', 'Frontend :3000', 'Shared Saha navigation'),
    ('/api/* and /health*', 'Backend :8000', 'API enforces each resource policy'),
    ('Private LAN/VPN nginx :8080', 'Admin :3002; API :8000', 'Excluded from public tunnel'),
    ('Native PostgreSQL', ':5432 / saha', 'Application data, memberships, references'),
    ('Existing Docker infrastructure', 'Redis, MinIO, search and supporting services', 'Kept by saha-infra; inspect actual Compose for binds'),
    ('Local chat test', 'HTTPS localhost:18448 and :18449', 'Separate stack; never published by saha online'),
])
status = paragraphs('Source snapshot: 2026-11-01. New social/workspace code requires both November migrations. The social/workspace release is owner-confirmed locally; a subsequent session-consistency patch needs new app builds and coordinated restart, with no further migration. Current source and successful builds are not proof of publication. See CURRENT-STATUS.md for exact evidence.', 'The owner previously confirmed the existing public tunnel was serving matching builds. This coding sandbox cannot access host sockets or systemd. Matrix/Element remains local testing only; two-device encryption acceptance is outstanding.')
policy = table(['Area', 'Who may access', 'Important distinction'], [
    ('Research / public institutions', 'Public approved resources and public post audiences', 'Published patents are not automatically reusable'),
    ('Projects / tasks / reference links', 'Invited project members; manager-controlled membership', 'Source optional; projects cannot become public through community settings'),
    ('Member feed', 'Signed-in users; author/qualified admins can review held material', 'Post audiences also protect attached media'),
    ('Private space reference', 'Space owner or MFA-qualified Saha admin', 'Not exposed to ordinary members or group moderators'),
    ('Collections / research notes', 'Account owner', 'Private access, not end-to-end encryption'),
    ('Encrypted chat', 'Linked Matrix identities of active participants', 'Element holds device keys; membership service has no device keys'),
    ('IP transactions / vault', 'Existing party, KYC, step-up and state gates', 'Optional preserved workflow; vault at-rest encryption is not chat E2EE'),
])
project = paragraphs('Create an invite-only project directly from Projects with a name and goal. A library resource is optional. The November migration makes older projects private while preserving their membership and restricts associated posts to the community audience.', 'Owners/moderators add existing Saha users by email through Members & invitations. This currently grants membership immediately; it is not a pending invitation acceptance workflow. Members can leave, and managers can remove members. Existing Matrix grants must be revoked before removal is confirmed.', 'References store an HTTPS URL, title, notes, selected platform and file type. Members browse/filter/copy links; authors or managers edit/remove them. Only managers pin. A version check rejects stale edits with 409 and a project has at most 200 references. Bundled SVG badges avoid fetching third-party favicons. The destination hostname remains visible; the selected icon is not identity verification.', 'The server never retrieves, indexes or copies linked files. Original platform permissions still apply. References and tasks are access-controlled database records, not encrypted chat. Existing task assignment, three-column status board, project stages and contribution guides are retained.')
social = paragraphs('One composer/card system serves the member feed and public institution updates. Compose text, optional titles and links, up to six media attachments (at most one video), keyboard-selectable member mentions and topic hashtags. Feed views include latest/ranked, followed authors, saved posts and server-side text search.', 'JPEG/PNG/WebP images are limited to 8 MiB; MP4/WebM video to 40 MiB. The API bounds reads, checks MIME signatures and stores opaque object keys. Draft uploads are owner-only with per-owner draft quotas; attaching is atomic and single-use. Downloads enforce the current post policy before storage access and use private/no-store. Image/video decoding, malware scanning, transcoding and streaming/range delivery are not implemented.', 'Six expressive reactions are independent from reputation votes. Editing clears endorsements; report/moderation behavior is preserved. Replies are one level deep, existing vote ranking is retained, and orphan replies remain visible without revealing deleted parent text. Sharing with thoughts creates a link post, not a native repost record or counter.', 'Mention labels are normalized to active account identities. Notification recipients must be able to see the post; notifications do not copy private post text. Admin moderation can inspect attachments with authenticated blob fetches. Text classifiers do not claim to classify visual media.')
chat = paragraphs('Projects reuse the community encrypted-room scope. Saha proves ownership of a personal Matrix identity using a temporary access token plus password/MFA step-up, stores only the Matrix identity, and coordinates room policy/invites/removal.', 'Element performs encryption and decryption on member devices. The dedicated membership bot must have no device encryption keys. Rooms require encryption, private invitation, joined-only history and non-federation. Ordinary users cannot change room state or send unencrypted message events.', 'Legacy community/proposal chat returns HTTP 410; historical records are not migrated or relabeled as E2EE. If the provider is unavailable or not configured, the interface reports that state and does not fall back to plaintext. Real device verification, ciphertext inspection, key rotation after removal and recovery tests remain required.')
ui = paragraphs('The public app uses one AppShell, route map, account menu, footer, breadcrumbs and responsive navigation. Green/sage/paper design tokens, local fonts and shared components keep Home, Explore, Institutions, Projects and the workspace coherent. Secondary IP tools remain available without dominating the collaboration journey.', 'Production browser API requests use the current nginx origin. Server-rendered listing reads use an absolute internal backend origin without forwarding user sessions. 404 means missing data; backend failures reach a retry screen.', 'Both apps use an explicit loading/authenticated/anonymous/unavailable session lifecycle. Cached hints are validated with /users/me; cookie-only recovery is supported. Home CTA/header/guest-only routes agree. Transient failures retain retryable state. Refresh validates account identity before retries; session revisions reject late JSON/blob responses. Same-origin login/logout changes synchronize without unmounting drafts for same-account rotation. Long-lived refresh tokens are never persisted. Media uses authenticated fetch and temporary blob URLs.', 'Text rendering uses React escaping, safe links, friendly UUID-backed mentions and accessible media descriptions. Modal focus, keyboard mention navigation, busy/error states and route continuation are implemented. Live browser/mobile/screen-reader acceptance remains to be performed.')
transaction = paragraphs('IP listings, BOM, discovery, protected vault assets, proposals, legal/contract state, settlement, disputes, reviews, demand and admin ledger remain in the repository. They are optional workflows. Collaboration does not require a payment or transaction.', 'Existing financial KYC, step-up, admin MFA, party/state authorization, production configuration guards and append-only audit controls remain relevant. Do not use the archived architecture as proof a planned payment, legal, Azure or compliance integration has shipped. The dated security audit retains the original risks and remediation evidence.')
operations = paragraphs('Use saha stop → migration/backup helper → saha build → saha start --local → saha versions --local → saha online → saha versions. The social/workspace helper performs the backup, stops apps, applies only the two November migrations, builds and starts locally; it leaves the tunnel stopped.', 'Never replace a running .next tree. Build receipts, required route manifests and X-Saha-Build identify source. A read-only schema gate refuses startup when required model columns are missing. nginx serves frontend/API on the public origin and admin only through the private listener.', 'No dependencies were added for this release. Use frozen pnpm and uv lockfiles, the isolated test stack and explicit migration dependency order. The original host checkout retains a nested frontend repository. The prepared ProjectSaha publication checkout includes frontend source as ordinary files for a complete clone; see docs/REPOSITORY-PUBLISHING.md for upload status.')

CSS = '''*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}body{margin:0;background:#f5f4ee;color:#263b31;font:16px/1.65 system-ui,sans-serif}a{color:#21674c}a:focus-visible,button:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid #bb8936;outline-offset:3px}.skip{position:absolute;left:-9999px}.skip:focus{left:16px;top:16px;background:white;padding:12px;z-index:5}aside{position:fixed;inset:0 auto 0 0;width:280px;background:#e7ede4;border-right:1px solid #cbd6ca;padding:24px;overflow:auto}aside h1{font-size:24px;line-height:1.2}nav a{display:block;padding:7px 0;text-decoration:none;font-size:14px}nav a:hover{text-decoration:underline}main{margin-left:280px;padding:36px 5vw;max-width:1500px}header{margin-bottom:32px}.eyebrow{text-transform:uppercase;letter-spacing:.12em;font-size:12px}.notice{padding:18px;border-left:4px solid #bb8936;background:#fff8e7}section{background:#fffefa;border:1px solid #d5ddd1;border-radius:16px;padding:28px;margin:24px 0;scroll-margin:24px}h2{font-size:24px;line-height:1.3}h3{font-size:18px}code{font-size:13px;overflow-wrap:anywhere}.table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}td,th{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #d5ddd1;overflow-wrap:anywhere}th{background:#edf2e9}details{border:1px solid #d5ddd1;border-radius:8px;margin:10px 0;padding:12px}summary{cursor:pointer;font-weight:600}input{width:100%;padding:11px;border:1px solid #bac8b8;border-radius:8px;background:white;font:inherit}button{padding:8px 12px;margin:8px 4px 0 0;border:1px solid #bac8b8;border-radius:8px;background:white;color:#21674c;cursor:pointer}.flow{display:flex;flex-wrap:wrap;gap:12px;align-items:center}.node{border:1px solid #bac8b8;background:#edf2e9;padding:16px;border-radius:10px;font-size:14px}.count{font-size:12px}.hidden,[hidden]{display:none!important}@media(max-width:850px){aside{position:static;width:auto}main{margin:0;padding:20px}nav{display:flex;flex-wrap:wrap;gap:12px}section{padding:18px}}@media print{aside,.controls{display:none}main{margin:0;padding:0}section{break-inside:avoid}details>*{display:block!important}}'''
JS = '''const search=document.querySelector('#search');const sections=[...document.querySelectorAll('main section')];function filter(){const q=search.value.toLowerCase().trim();let count=0;for(const section of sections){const visible=!q||section.textContent.toLowerCase().includes(q);section.hidden=!visible;if(visible)count++;}document.querySelector('#count').textContent=count+' sections shown';}search.addEventListener('input',filter);document.querySelector('#expand').addEventListener('click',()=>document.querySelectorAll('details').forEach(d=>d.open=true));document.querySelector('#collapse').addEventListener('click',()=>document.querySelectorAll('details').forEach(d=>d.open=false));document.querySelector('#reset').addEventListener('click',()=>{search.value='';filter();search.focus();});document.querySelectorAll('nav a[href^="#"]').forEach(a=>a.addEventListener('click',()=>{search.value='';filter();}));filter();'''


def page(file, title, sections):
    navigation = ''.join(f'<a href="#{key}">{esc(label)}</a>' for key, label, _ in sections)
    content = ''.join(f'<section id="{key}"><h2>{esc(label)}</h2>{body}</section>' for key, label, body in sections)
    (OUT/file).write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Saha · {esc(title)}</title><style>{CSS}</style></head><body><a class="skip" href="#main">Skip to content</a><aside><p class="eyebrow">Saha / documentation</p><h1>{esc(title)}</h1><p>Source snapshot · 2026-11-01</p><label for="search">Find a section</label><input id="search" type="search" placeholder="Search this reference"><p id="count" class="count" role="status"></p><nav aria-label="Reference sections">{navigation}</nav><hr><a href="SAHA_ARCHITECTURE.html">System</a> · <a href="SAHA_BACKEND.html">Backend</a> · <a href="SAHA_FRONTEND.html">Frontend</a><p><a href="../CURRENT-STATUS.md">Release evidence</a> · <a href="README.md">Documentation index</a></p></aside><main id="main"><header><p class="eyebrow">Open creativity · shared development</p><h1>{esc(title)}</h1><p>Current implementation, permissions and operations. Search sections or expand the source inventories. Works offline.</p><div class="controls"><button id="expand">Expand inventories</button><button id="collapse">Collapse inventories</button><button id="reset">Clear search</button></div></header>{content}<footer>Generated by scripts/update-architecture-docs.py from checked-out source. <a href="archive/README.md">Earlier references are archived.</a></footer></main><script>{JS}</script></body></html>''')

page('SAHA_ARCHITECTURE.html','System architecture',[
 ('status','Implementation and rollout', '<div class="notice">'+status+'</div>'),
 ('journey','How the platform fits together', paragraphs('Saha connects research discovery, people, institutions and invite-only projects. Start from a patent, a paper or your own idea. Keep research in private collections, share public progress in the feed, and collaborate inside a project.')+'<div class="flow"><div class="node">Discover / collect</div><span>→</span><div class="node">Meet / discuss</div><span>→</span><div class="node">Invite-only project</div><span>→</span><div class="node">Tasks / references / Element chat</div></div>'),
 ('topology','Deployment and service mapping',ports),('privacy','Access boundaries',policy),('projects','Standalone project collaboration',project),('social','Social interaction and media',social),('chat','Encrypted chat',chat),('transactions','Preserved IP tools',transaction),('operations','Release and operations',operations),
 ('diagrams','Editable diagrams', '<p><a href="saha-system-architecture.drawio">System diagram</a> · <a href="saha-deployment-topology.drawio">Deployment diagram</a></p><p>Open in diagrams.net. Files contain current uncompressed diagram XML.</p>'),
])
page('SAHA_BACKEND.html','Backend application',[
 ('status','Validation boundary',status),('layers','Runtime and source layers',paragraphs('FastAPI routers validate input and resolve authentication dependencies. Services enforce membership, ownership, lifecycle and external-provider policies. SQLAlchemy async models use PostgreSQL via asyncpg. Redis backs rate limits/cache; MinIO stores objects. Integrations isolate outbound providers.','Refresh and logout acquire a PostgreSQL advisory lock per refresh-token family, then recheck token state. Replay/logout revoke the family including rotated descendants. Existing access JWTs remain bounded by their expiry. Real DB concurrency acceptance is tracked separately.', 'app/main.py mounts the routers and middleware; app/core/config.py validates production settings. app/core/security.py owns identity and collaboration/KYC/admin guards. API dependencies do not replace per-record authorization. Some operational or optional-auth routes enforce policy inside the handler.')),
 ('access','Authorization map',policy),('projects','Projects and reference records',project),('media','Media, mentions and reactions',social),('chat','Matrix integration',chat),('ip','Transaction domain',transaction),('schema',f'Data model: {len(models)} mapped tables',schema),('api',f'Router inventory: {len(api_rows)} handlers',paragraphs('Generated from router decorators and dependency expressions. This inventory does not claim a guard alone captures every per-resource condition; inspect the linked source and authorization tests.')+table(['Method','Path','Dependency','Source'],api_rows)),
 ('operations','Build, schema and test gates',operations),
])
page('SAHA_FRONTEND.html','Frontend and administration',[
 ('status','Release and acceptance',status),('experience','Shared navigation and design',ui),('projects','Project workspace interaction',project),('feed','Social feed interaction',social),('chat','Chat handoff and account linking',chat),('pages','Public application route map',routes('frontend')),('admin','Private admin route map',paragraphs('Admin runs as a separate Next.js application behind private nginx. Institutions & Spaces controls verification policy/reviews and private references. Moderation supports protected attachment inspection. Other pages preserve user, listing, transaction and operational controls.')+routes('admin')),('operations','Build and deployment',operations),
])


def diagram(filename, nodes, edges):
    doc=ET.Element('mxfile',host='app.diagrams.net',modified='2026-11-01T00:00:00Z',agent='Saha source documentation')
    diagram=ET.SubElement(doc,'diagram',id='current',name='Current · 2026-11-01')
    model=ET.SubElement(diagram,'mxGraphModel',dx='1400',dy='1000',grid='1',gridSize='10',page='1',pageWidth='1400',pageHeight='1000')
    root=ET.SubElement(model,'root');ET.SubElement(root,'mxCell',id='0');ET.SubElement(root,'mxCell',id='1',parent='0')
    for key,label,x,y in nodes:
        cell=ET.SubElement(root,'mxCell',id=key,value=label,style='rounded=1;whiteSpace=wrap;html=0;fillColor=#e7ede4;strokeColor=#476854;fontColor=#263b31;fontSize=14;',vertex='1',parent='1')
        ET.SubElement(cell,'mxGeometry',x=str(x),y=str(y),width='260',height='100',**{'as':'geometry'})
    for i,(source,target,label) in enumerate(edges):
        cell=ET.SubElement(root,'mxCell',id='edge'+str(i),value=label,style='edgeStyle=orthogonalEdgeStyle;rounded=0;html=0;endArrow=block;',edge='1',parent='1',source=source,target=target)
        ET.SubElement(cell,'mxGeometry',relative='1',**{'as':'geometry'})
    ET.indent(doc)
    ET.ElementTree(doc).write(OUT/filename,encoding='utf-8',xml_declaration=True)

diagram('saha-system-architecture.drawio',[
 ('web','Members / shared Saha UI\nExplore · feed · institutions · projects',60,60),('api','FastAPI :8000\nIdentity + per-resource authorization',430,60),('admin','Private admin :3002\nMFA · review · moderation',800,60),('db','PostgreSQL\nProjects / membership / references\nSocial metadata / IP workflows',430,260),('storage','MinIO\nMedia and vault objects\nAPI-controlled access',800,260),('matrix','Matrix / Element\nE2EE on participant devices\nLocal testing only',60,480),('external','External reference platforms\nFiles stay with their providers',430,480),('note','November migrations required\nPublication and device acceptance\ntracked in CURRENT-STATUS.md',800,480)],
 [('web','api','Same-origin API'),('admin','api','Private API + admin guards'),('api','db','Async SQL / memberships'),('api','storage','Opaque object keys'),('api','matrix','Policy / invites / revocation only'),('web','matrix','Encrypted conversation in Element'),('web','external','Open HTTPS shortcut; no proxy fetch')])
diagram('saha-deployment-topology.drawio',[
 ('browser','Public HTTPS\nsahasolutions.com + www',40,60),('tunnel','Existing Cloudflare Tunnel\nPublic nginx origin only',370,60),('nginx','nginx :80\nPages / API / readiness / SSE',700,60),('frontend','saha-frontend :3000\nBuild receipt + X-Saha-Build',1020,60),('api','saha-backend :8000\nRead-only schema startup gate',700,280),('private','Private LAN/VPN nginx :8080\nExcluded from tunnel',40,280),('admin','saha-admin :3002\nMFA-qualified platform controls',370,280),('data','Native PostgreSQL :5432\nDocker saha-infra services',1020,280),('cli','saha CLI / grouped systemd service\nstop → migrate/build → start --local\nversions → online',370,500),('chat','Separate localhost test chat\nHTTPS :18448 / :18449\nNot started by saha',700,500)],
 [('browser','tunnel','HTTPS'),('tunnel','nginx','Local tunnel ingress'),('nginx','frontend','/'),('nginx','api','/api and /health'),('private','admin','/'),('private','api','/api'),('api','data','Local data access'),('cli','frontend','Grouped lifecycle'),('cli','api','Grouped lifecycle'),('cli','admin','Grouped lifecycle')])
(ARCHIVE/'README.md').write_text('''# Archived architecture references

These five artifacts preserve the earlier transaction-oriented documentation before
the 2026-11-01 refresh. They are historical evidence, not current API, security,
chat, deployment or database instructions. Old counts and plaintext-chat flows
are superseded by the [current architecture index](../README.md).

'''+''.join(f'- [{p.name}]({p.name})\n' for p in sorted(ARCHIVE.iterdir()) if p.suffix in {'.html','.drawio'}))
(OUT/'README.md').write_text('''# Saha architecture references

Updated 2026-11-01. Every current artifact is regenerated from the checked-out
source and current implementation notes by `python3 scripts/update-architecture-docs.py`.
The previous five artifacts are retained in [archive](archive/README.md).

| Artifact | Content |
| --- | --- |
| [System architecture](SAHA_ARCHITECTURE.html) | Product journey, service mapping, privacy, media, projects, chat and release boundaries |
| [Backend](SAHA_BACKEND.html) | Searchable handler inventory, model tables/columns, guards and service behavior |
| [Frontend](SAHA_FRONTEND.html) | Shared UI, project/feed interactions, all public/admin application routes |
| [System diagram](saha-system-architecture.drawio) | Trust boundaries and external references/chat |
| [Deployment diagram](saha-deployment-topology.drawio) | Existing nginx/Cloudflare/systemd mapping and separate local chat stack |

Open HTML directly in a browser: it uses local CSS/JavaScript, searchable sections,
expandable inventories and no external CDN. Open draw.io XML in diagrams.net.
The pages are documentation, not running application demos. For live evidence see
[Current status](../CURRENT-STATUS.md); for deployment use [Hosting](../HOSTING.md).

Regenerate after router/model/page changes. Keep historical findings in the archive;
do not interpret older planned integrations as implemented or deployed features.
''')
print(f'Regenerated 3 interactive pages, 2 diagrams; {len(models)} model tables; {len(api_rows)} route handlers.')
