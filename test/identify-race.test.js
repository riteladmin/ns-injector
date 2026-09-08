#!/usr/bin/env node
/**
 * The portal shim must still identify when the token arrives AFTER the widget loads.
 * Run: node test/identify-race.test.js
 *
 * ── WHY ──────────────────────────────────────────────────────────────────────────────────────────
 * This file used to read `localStorage.ns_t` exactly once, inside `script.onload`, and give up in
 * silence if the key was not there yet. Whether that worked was a race between the NetSapiens portal
 * writing the key and an EXTERNAL script finishing its download — a race this file does not control.
 *
 * When it lost, the widget ran anonymous for the whole page load and every chat started on that page
 * was recorded as an anonymous website visitor even though the person was signed in. It was losing:
 * on 2026-09-08, seven real portal chats were recorded anonymous and four browsers held BOTH
 * identified and anonymous conversations — the same people, captured sometimes and not others.
 *
 * The failure is invisible from inside the browser: nothing throws, nothing logs, the chat works
 * perfectly and merely has no name on it. So it needs a test that drives the real file and asserts
 * the timing, which is what this is. Scenarios 2 and 3 both FAIL against the pre-fix version — that
 * is the point of them.
 */
const fs = require('fs');
const path = require('path');

const SRC = process.env.CWX_SHIM || path.join(__dirname, '..', 'static', 'cwx-chat.js');
const src = fs.readFileSync(SRC, 'utf8');

function scenario(name, { tokenAt, widgetAt, expectBy }) {
  return new Promise((resolve) => {
    const t0 = Date.now();
    const store = {};
    let identified = null, identifiedAt = null;
    const script = { setAttribute() {}, set onload(fn) { this._fn = fn; }, get onload() { return this._fn; } };

    global.localStorage = { getItem: (k) => (k in store ? store[k] : null) };
    global.window = {};
    global.document = { createElement: () => script, head: { appendChild() {} }, documentElement: {} };

    eval(src); // registers script.onload

    setTimeout(() => {
      global.window.CWXWidget = { identify: (t) => { identified = t; identifiedAt = Date.now() - t0; } };
      script.onload();
    }, widgetAt);
    if (tokenAt !== null) setTimeout(() => { store['ns_t'] = 'TOKEN'; }, tokenAt);

    setTimeout(() => {
      const ok = tokenAt === null
        ? identified === null
        : (identified === 'TOKEN' && identifiedAt <= expectBy);
      console.log(`${ok ? '  ✓' : '  ✗'} ${name}`
        + (identified ? ` (identified at ~${identifiedAt}ms)` : ' (never identified)'));
      resolve(ok);
    }, 2500);
  });
}

(async () => {
  const results = [];
  results.push(await scenario('token present BEFORE the widget loads', { tokenAt: 0, widgetAt: 50, expectBy: 300 }));
  // ★ The two that were losing. Both identify now; both are silent no-ops on the pre-fix file.
  results.push(await scenario('★ token written 400ms AFTER the widget loads', { tokenAt: 450, widgetAt: 50, expectBy: 900 }));
  results.push(await scenario('★ slow portal login — token at 1.5s', { tokenAt: 1500, widgetAt: 50, expectBy: 2000 }));
  // A genuinely logged-out page must stay quiet rather than identify with junk or throw.
  results.push(await scenario('logged out — never identifies, never throws', { tokenAt: null, widgetAt: 50, expectBy: 0 }));

  const failed = results.filter((r) => !r).length;
  console.log(failed ? `\nIDENTIFY-RACE: ${failed} FAILED` : '\nIDENTIFY-RACE GREEN');
  process.exit(failed ? 1 : 0);
})();
