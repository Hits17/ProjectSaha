const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('../apps/frontend/node_modules/typescript');
const exportsObject = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(__dirname + '/../apps/frontend/lib/mentions.ts', 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020}}).outputText, {exports: exportsObject});
const { mentionText, editMentionText, insertMention } = exportsObject;
const id = '12345678-1234-1234-1234-123456789012';
const tag = `@[Asha Patel](${id})`;
test('friendly mention text preserves stable account identity', () => {
  const result = mentionText(`Hello ${tag}!`);
  assert.equal(result.text, 'Hello @Asha Patel!');
  assert.equal(result.tokens[0].id, id);
});
test('inserting text before or after a mention preserves it', () => {
  assert.equal(editMentionText(`Hello ${tag}!`, 'Hi there Hello @Asha Patel!'), `Hi there Hello ${tag}!`);
  assert.equal(editMentionText(tag, '@Asha Patel thanks'), `${tag} thanks`);
});
test('editing inside a mention removes the account association', () => {
  assert.equal(editMentionText(tag, '@Asha Patil'), '@Asha Patil');
  assert.equal(editMentionText(tag, ''), '');
});
test('choosing a member inserts identity without losing surrounding text', () => {
  const result = insertMention('Hi @as, welcome', 3, 6, { user_id: id, full_name: 'Asha Patel' });
  assert.equal(result.raw, `Hi ${tag} , welcome`);
  assert.equal(mentionText(result.raw).text.slice(0, result.caret), 'Hi @Asha Patel ');
});
test('duplicate display names retain their own account identities', () => {
  const secondId = '22345678-1234-1234-1234-123456789012';
  const raw = `${tag} and @[Asha Patel](${secondId})`;
  const edited = editMentionText(raw, '@Asha Patel and @Asha Patel!');
  assert.equal(mentionText(edited).tokens[0].id, id);
  assert.equal(mentionText(edited).tokens[1].id, secondId);
});
