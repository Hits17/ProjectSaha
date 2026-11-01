// Run: node --test scripts/test-ux-navigation.cjs (uses the installed frontend TypeScript).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createRequire } = require('node:module');
const app = path.resolve(__dirname, '../apps/frontend');
const localRequire = createRequire(path.join(app, 'package.json'));
const ts = localRequire('typescript');

function load(relative, overrides = {}) {
  const filename = path.join(app, relative);
  const js = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const exports = {};
  vm.runInNewContext(js, { exports, URL, AbortSignal, process: { env: {} },
    require: name => { if (name === 'server-only') return {}; return localRequire(name); }, ...overrides }, { filename });
  return exports;
}
const nav = load('lib/navigation.ts');

test('every navigation destination resolves to an actual page, including secondary IP tools', () => {
  const routes = new Set();
  function visit(directory, segments = []) {
    for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
      if (item.isDirectory()) visit(path.join(directory, item.name), item.name.startsWith('(') ? segments : [...segments, item.name]);
      else if (item.name === 'page.tsx') routes.add('/' + segments.join('/'));
    }
  }
  visit(path.join(app, 'app'));
  for (const item of [...nav.primaryNavigation, ...nav.workspaceNavigation.flatMap(g => g.items)]) {
    assert.ok(routes.has(item.href), `Missing destination: ${item.href}`);
  }
  assert.equal(new Set(nav.workspaceNavigation.flatMap(g => g.items.map(i => i.href))).size, 15);
});

test('active navigation matches path segments without marking overview active on every page', () => {
  assert.equal(nav.routeIsActive('/projects/abc', '/projects'), true);
  assert.equal(nav.routeIsActive('/projects-other', '/projects'), false);
  assert.equal(nav.routeIsActive('/dashboard/collections', '/dashboard'), false);
  assert.equal(nav.routeIsActive('/dashboard', '/dashboard'), true);
});

test('breadcrumbs retain valid parent links and do not display raw record identifiers', () => {
  const detail = nav.breadcrumbs('/dashboard/listings/abc-123/dialogue');
  assert.equal(detail.at(-1).label, 'Listing assistant');
  assert.equal(detail.at(-1).href, undefined);
  assert.equal(detail.at(-2).href, '/dashboard/listings/abc-123');
  assert.equal(detail.at(-2).label, 'Details');
  assert.equal(nav.breadcrumbs('/listings/abc')[1].href, '/dashboard/discover');
  assert.equal(nav.breadcrumbs('/dashboard/members/abc')[2].href, undefined);
});

test('sign-in preserves a selected source, search filter and deep-link destination', () => {
  for (const target of ['/projects?source=a%2Fb', '/explore?q=water&type=patent', '/dashboard/collections', '/institutions/abc#posts']) {
    assert.equal(nav.safeReturnTo(target), target);
    assert.equal(new URL(nav.signInHref(target), 'https://saha.invalid').searchParams.get('next'), target);
  }
});

test('sign-in continuation rejects external, malformed and authentication-loop targets', () => {
  for (const target of [null, '', 'https://evil.test', '//evil.test', '/\\evil.test', 'javascript:alert(1)', '/login?next=/login', '/register', '/api/v1/admin', '/dashboard/../../login', '/\nevil.test', '/unknown']) {
    assert.equal(nav.safeReturnTo(target), '/dashboard', String(target));
  }
});

test('server listing fetch uses an absolute anonymous URL without cache or session forwarding', async () => {
  let call;
  const mod = load('lib/server-listings.ts', { fetch: async (url, options) => {
    call = { url: String(url), options };
    return new Response(JSON.stringify({ id: 'example', status: 'published' }), { status: 200 });
  } });
  assert.equal((await mod.publicListing('a/b')).id, 'example');
  assert.equal(call.url, 'http://127.0.0.1:8000/api/v1/listings/a%2Fb');
  assert.equal(call.options.cache, 'no-store');
  assert.deepEqual(Object.keys(call.options.headers), ['Accept']);
});

test('missing listings become 404, but origin failures reach the retry screen', async () => {
  assert.equal(await load('lib/server-listings.ts', { fetch: async () => new Response('', { status: 404 }) }).publicListing('x'), null);
  await assert.rejects(load('lib/server-listings.ts', { fetch: async () => new Response('', { status: 503 }) }).publicListing('x'), /could not be loaded/);
});
