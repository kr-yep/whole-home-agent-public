// Exercise the actual switch controller with fake renderers, no artwork/WebGL.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const controller = source.slice(source.indexOf('let characterLoad ='), source.indexOf('function drawCast()'));
function actor(ready = true) {
  return { ready: async () => ready, destroyed: false, attached: false,
    destroy() { this.destroyed = true; }, detach() { this.attached = false; },
    attach() { this.attached = true; }, express() {} };
}
function setup(createActor) {
  const fallback = { hidden: false };
  const context = { actor: null, app: {}, who: 'rem', view: {},
    CHARACTERS: { rem: { name: 'Rem' }, nailong: { name: 'Nailong' } },
    createActor, document: { getElementById: () => fallback },
    console: { warn() {} }, speak() {}, layout() {}, drawCast() {},
    readView: () => ({}), CHOICE_KEY: 'choice', localStorage: { setItem() {} } };
  vm.createContext(context);
  vm.runInContext(controller, context);
  return { context, fallback };
}
(async () => {
  let state = setup(async () => actor(false));
  await state.context.setCharacter('rem');
  assert.equal(state.context.actor, null);
  assert.equal(state.fallback.hidden, false);
  const original = actor();
  state = setup(async () => { throw new Error('missing'); });
  state.context.actor = original;
  await state.context.setCharacter('nailong');
  assert.equal(state.context.actor, original);
  assert.equal(original.destroyed, false);
  let resolveOld;
  const old = actor(), newest = actor();
  state = setup(id => id === 'rem' ? new Promise(resolve => { resolveOld = resolve; }) : Promise.resolve(newest));
  const pending = state.context.setCharacter('rem');
  await state.context.setCharacter('nailong');
  resolveOld(old);
  await pending;
  assert.equal(state.context.actor, newest);
  assert.equal(state.context.who, 'nailong');
  assert.equal(newest.attached, true);
  assert.equal(old.destroyed, true);
  assert.equal(state.fallback.hidden, true);
  await state.context.setCharacter('__proto__');
  assert.equal(state.context.actor, newest);
  console.log('PASS: missing asset, preserved actor, latest selection wins, invalid ID');
})().catch(error => { console.error(error); process.exitCode = 1; });
