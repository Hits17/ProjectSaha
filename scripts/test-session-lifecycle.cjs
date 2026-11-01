const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createRequire } = require('node:module');
const local = createRequire(path.resolve(__dirname, '../apps/frontend/package.json'));
const ts = local('typescript');
const React = local('react');
const { renderToStaticMarkup } = local('react-dom/server');
function load(file, overrides = {}, globals = {}) {
  const exports = {};
  const code = ts.transpileModule(fs.readFileSync(path.resolve(__dirname, '..', file), 'utf8'), { fileName: file, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText;
  vm.runInNewContext(code, { exports, AbortSignal, Promise, URL, atob, process: { env: { NODE_ENV: 'production' } }, require: key => overrides[key] ?? local(key), ...globals });
  return exports;
}
const response = (status, data = {}) => ({ status, ok: status >= 200 && status < 300, headers: new Headers(), json: async () => data });
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
const user = { id: 'member-a', full_name: 'Current name', role: 'creator' };
const tokens = { access_token: 'new-access', refresh_token: 'new-refresh' };
for (const app of ['frontend', 'admin']) {
  const { createSessionController, shouldSyncSession } = load(`apps/${app}/lib/session-controller.ts`);
  test(`${app}: cross-tab login/logout syncs but same-account rotation preserves drafts`, () => {
    const current = { status: 'authenticated', user };
    assert.equal(shouldSyncSession(current, JSON.stringify({ state: { user, accessToken: 'rotated' } })), false);
    assert.equal(shouldSyncSession(current, JSON.stringify({ state: { user: null, accessToken: null, signedOut: true } })), true);
    assert.equal(shouldSyncSession(current, JSON.stringify({ state: { user: { id: 'member-b' }, accessToken: 'b-token' } })), true);
    assert.equal(shouldSyncSession(current, null), true);
    assert.equal(shouldSyncSession(current, '{invalid'), true);
  });
  test(`${app}: persisted hints cannot restore privilege or legacy refresh tokens`, () => {
    let configuration;
    const store = load(`apps/${app}/store/auth.ts`, {
      "@/lib/session-storage": load(`apps/${app}/lib/session-storage.ts`),
      zustand: { create: () => initializer => { let state; const set = update => { state = { ...state, ...(typeof update === 'function' ? update(state) : update) }; }; state = initializer(set, () => state); return { getState: () => state }; } },
      'zustand/middleware': { createJSONStorage: factory => factory(), persist: (initializer, options) => { configuration = options; return initializer; } },
    }).useAuthStore;
    const hydrated = configuration.merge({ user, accessToken: 'cached', refreshToken: 'must-not-hydrate', status: 'authenticated', revision: 999 }, store.getState());
    assert.equal(hydrated.status, 'loading'); assert.equal(hydrated.revision, 1); assert.equal(hydrated.refreshToken, null);
    assert.equal(configuration.partialize({ ...hydrated, refreshToken: 'must-not-persist' }).refreshToken, undefined);
    assert.equal(configuration.skipHydration, true);
  });
  test(`${app}: blocked browser storage does not break in-memory login or logout`, () => {
    const { resilientSessionStorage } = load(`apps/${app}/lib/session-storage.ts`);
    const storage = resilientSessionStorage(() => { throw Error('Storage denied'); });
    assert.equal(storage.getItem('session'), null);
    storage.setItem('session', 'active'); assert.equal(storage.getItem('session'), 'active');
    storage.removeItem('session'); assert.equal(storage.getItem('session'), null);
  });
  function harness(replies, changes = {}) {
    let state = { user, accessToken: 'old-access', refreshToken: null, revision: 1, signedOut: false, status: 'authenticated', ...changes };
    const calls = [];
    const controller = createSessionController({
      snapshot: () => state, base: '',
      fetch: async (...args) => { calls.push(args); const reply = replies.shift(); if (!reply) throw Error('Unexpected request'); return typeof reply === 'function' ? reply() : reply; },
      accept: (u, t) => { state = { ...state, user: u, accessToken: t.access_token, refreshToken: t.refresh_token, status: 'authenticated', revision: state.revision + 1 }; },
      tokens: t => { state = { ...state, accessToken: t.access_token, refreshToken: t.refresh_token }; },
      profile: u => { state = { ...state, user: u }; },
      anonymous: () => { state = { ...state, user: null, accessToken: null, refreshToken: null, status: 'anonymous', signedOut: true, revision: state.revision + 1 }; },
      unavailable: () => { state = { ...state, status: 'unavailable' }; },
    });
    return { controller, calls, get: () => state, change: patch => { state = { ...state, ...patch, revision: state.revision + 1 }; } };
  }
  test(`${app}: restoration uses server profile, not cached name/role`, async () => {
    const h = harness([response(200, user)], { user: { ...user, full_name: 'Old name' }, status: 'loading' });
    await h.controller.restore();
    assert.equal(h.get().status, 'authenticated'); assert.equal(h.get().user.full_name, 'Current name'); assert.equal(h.calls.length, 1);
  });
  test(`${app}: cookie-only session restores even without persisted profile`, async () => {
    const h = harness([response(200, tokens), response(200, user)], { user: null, accessToken: null, status: 'loading' });
    await h.controller.restore();
    assert.equal(h.get().user.id, user.id); assert.equal(h.calls[0][1].credentials, 'include'); assert.equal(h.calls[1][1].headers.Authorization, 'Bearer new-access');
  });
  test(`${app}: expired access token rotates once and verifies identity`, async () => {
    const h = harness([response(401), response(200, tokens), response(200, user)]);
    await h.controller.restore(); assert.equal(h.get().accessToken, 'new-access'); assert.equal(h.calls.length, 3);
  });
  test(`${app}: explicit logout never silently restores a surviving cookie`, async () => {
    const h = harness([], { signedOut: true, user: null, accessToken: null });
    await h.controller.restore(); assert.equal(h.get().status, 'anonymous'); assert.equal(h.calls.length, 0);
  });
  test(`${app}: invalid refresh clears identity; outage preserves retryable credentials`, async () => {
    const rejected = harness([response(401), response(401)]); await rejected.controller.restore(); assert.equal(rejected.get().status, 'anonymous');
    const outage = harness([response(503)]); await outage.controller.restore(); assert.equal(outage.get().status, 'unavailable'); assert.equal(outage.get().accessToken, 'old-access');
  });
  test(`${app}: transient refresh failure does not log the member out`, async () => {
    for (const status of [403, 429, 500, 503]) {
      const h = harness([response(status)]); assert.equal(await h.controller.refresh(), null); assert.equal(h.get().status, 'authenticated'); assert.equal(h.get().accessToken, 'old-access');
    }
  });
  test(`${app}: concurrent refresh callers share one exchange and identity check`, async () => {
    const gate = deferred(); const h = harness([() => gate.promise, response(200, user)]);
    const a = h.controller.refresh(); const b = h.controller.refresh(); gate.resolve(response(200, tokens));
    assert.deepEqual(await Promise.all([a, b]), ['new-access', 'new-access']); assert.equal(h.calls.length, 2);
  });
  test(`${app}: another account's cookie cannot supply a mutation retry token`, async () => {
    const h = harness([response(200, tokens), response(200, { ...user, id: 'member-b' })]);
    assert.equal(await h.controller.refresh(), null); assert.equal(h.get().status, 'anonymous');
  });
  test(`${app}: logout while restoration is pending cannot resurrect a session`, async () => {
    const gate = deferred(); const h = harness([() => gate.promise]); const restoring = h.controller.restore();
    h.change({ user: null, accessToken: null, signedOut: true, status: 'anonymous' }); gate.resolve(response(200, user)); await restoring;
    assert.equal(h.get().user, null); assert.equal(h.get().status, 'anonymous');
  });
  test(`${app}: late refresh does not overwrite a replacement login`, async () => {
    const gate = deferred(); const h = harness([() => gate.promise]); const refreshing = h.controller.refresh();
    h.change({ user: { id: 'member-b' }, accessToken: 'b-access' }); gate.resolve(response(200, tokens));
    assert.equal(await refreshing, null); assert.equal(h.get().accessToken, 'b-access'); assert.equal(h.calls.length, 1);
  });
  test(`${app}: restoration also rejects a changed cookie account`, async () => {
    const h = harness([response(401), response(200, tokens), response(200, { id: 'member-b' })]);
    await h.controller.restore(); assert.equal(h.get().status, 'anonymous');
  });
  test(`${app}: API ignores an authenticated result after logout/account switch`, async () => {
    const gate = deferred(); let state = { accessToken: 'old-access', user, revision: 1 };
    const api = load(`apps/${app}/lib/api.ts`, { '@/store/auth': { useAuthStore: { getState: () => state } } }, { fetch: () => gate.promise });
    const result = api.request('/private', { token: 'old-access' });
    // Let dynamic import and fetch run before the account changes.
    await new Promise(resolve => setImmediate(resolve));
    state = { accessToken: null, user: null, revision: 2 }; gate.resolve(response(200, { secret: 'old account' }));
    await assert.rejects(result, /session changed/i);
  });
  test(`${app}: a late 401 reuses an already rotated token without refreshing again`, async () => {
    const gate = deferred(); let state = { accessToken: 'old-access', user, revision: 1 }; let count = 0;
    const api = load(`apps/${app}/lib/api.ts`, { '@/store/auth': { useAuthStore: { getState: () => state } } }, { fetch: async (_url, options) => { count++; if (count === 1) return gate.promise; assert.equal(options.headers.Authorization, 'Bearer new-access'); return response(200, { ok: true }); } });
    const result = api.request('/private', { token: 'old-access' }); await new Promise(resolve => setImmediate(resolve));
    state = { ...state, accessToken: 'new-access' }; gate.resolve(response(401));
    assert.equal((await result).ok, true); assert.equal(count, 2);
  });
  test(`${app}: a stale caller cannot send a request after local logout`, async () => {
    let calls = 0;
    const api = load(`apps/${app}/lib/api.ts`, { '@/store/auth': { useAuthStore: { getState: () => ({ accessToken: null, user: null, revision: 3 }) } } }, { fetch: async () => { calls++; return response(200); } });
    await assert.rejects(api.request('/private', { token: 'old-access' }), /session changed/i); assert.equal(calls, 0);
  });
  test(`${app}: credentials never go to a supplied external URL`, async () => {
    let calls = 0;
    const api = load(`apps/${app}/lib/api.ts`, { '@/store/auth': { useAuthStore: { getState: () => ({ accessToken: 'old-access', user, revision: 1 }) } } }, { fetch: async () => { calls++; return response(200); } });
    for (const target of ['https://outside.invalid/secret', '//outside.invalid/secret', '/\\outside.invalid/secret'])
      await assert.rejects(api.request(target, { token: 'old-access' }), /local application path/i);
    assert.equal(calls, 0);
  });
  test(`${app}: binary response is rejected if logout happens while reading its body`, async () => {
    const gate = deferred(); let state = { accessToken: 'old-access', user, revision: 1 };
    const api = load(`apps/${app}/lib/api.ts`, { '@/store/auth': { useAuthStore: { getState: () => state } } }, { fetch: async () => ({ ...response(200), blob: () => gate.promise }) });
    const result = api.request('/api/v1/social/media/test', { token: 'old-access', responseType: 'blob' });
    await new Promise(resolve => setImmediate(resolve)); state = { user: null, accessToken: null, revision: 2 }; gate.resolve(new Blob(['private media']));
    await assert.rejects(result, /session changed/i);
  });
  test(`${app}: password/MFA step-up failures do not rotate the session`, async () => {
    let count = 0;
    const api = load(`apps/${app}/lib/api.ts`, { '@/store/auth': { useAuthStore: { getState: () => ({ accessToken: 'old-access', user, revision: 1 }) } } }, { fetch: async () => { count++; return { ...response(401, { detail: 'Fresh verification required' }), headers: new Headers({ 'X-Step-Up-Required': 'true' }) }; } });
    await assert.rejects(api.request('/private', { token: 'old-access' }), /Fresh verification/); assert.equal(count, 1);
  });

}
for (const status of ['loading', 'unavailable', 'authenticated', 'anonymous']) {
  test(`home CTA renders the correct action for ${status}`, () => {
    const { HomeSessionActions } = load('apps/frontend/components/home-session-actions.tsx', {
      '@/store/auth': { useAuthStore: selector => selector({ status }) },
      'next/link': ({ children, ...props }) => React.createElement('a', props, children),
    });
    const markup = renderToStaticMarkup(React.createElement(HomeSessionActions));
    assert.equal(markup.includes('/register'), status === 'anonymous');
    assert.equal(markup.includes('/dashboard'), status === 'authenticated');
    if (status === 'loading' || status === 'unavailable') assert.ok(markup.includes('role="status"'));
  });
}
