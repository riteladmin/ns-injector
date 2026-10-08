/**
 * CloudWorx chat — NetSapiens portal shim (v3.3.0 P2). Injected into the manager portal via
 * ns-injector (same mechanism as intercom.js). Loads the chat widget in PORTAL mode and hands it the
 * logged-in user's session token (ns_t) so the agent + staff get VERIFIED identity.
 *
 * ns_t is read from the portal's own localStorage (same-origin) and passed to the widget's identify(),
 * which sends it over TLS at session-create; the server validates it live against NetSapiens and
 * discards it. It is never stored by the widget or this shim.
 *
 * ── WHY THIS RETRIES (2026-09-08) ────────────────────────────────────────────────────────────────
 * This used to read localStorage ONCE, inside script.onload, and give up silently if the key was not
 * there yet:
 *
 *     s.onload = function () { var t = nsT(); if (t && ...) identify(t); };
 *
 * Whether that worked was a race between the portal writing `ns_t` and an EXTERNAL script finishing
 * its download — a race this file does not control and cannot win reliably. When it lost, the widget
 * ran anonymous for the whole page load, and every chat started on that page was recorded as an
 * anonymous website visitor even though the person was signed in.
 *
 * It was losing: seven real portal chats are recorded anonymous, and four browsers have BOTH
 * identified and anonymous conversations — the same people, captured sometimes and not others.
 *
 * So: poll until the token appears, then identify once. The widget's own /identify call upgrades any
 * conversation that was already started before we got there, which is the other half of the fix.
 *
 * Configure PORTAL_EMBED_KEY to the tenant's portal chat widget embed key.
 */
(function () {
  var PORTAL_EMBED_KEY = 'a5bca69689c803de51495f0ccb28bb59'; // TEST: CloudWorx Manager Portal (copy) — AI door on; served only to domains whose PORTAL_EXTRA_JS points at /chat-test (2026-10-08)
  var WIDGET_SRC = 'https://webchat.cloudworxcx.com/widget.js';
  var POLL_MS = 200;      // the race is normally sub-second; this is cheap and generous
  var GIVE_UP_MS = 15000; // a genuinely logged-out page just stops looking

  function nsT() { try { return localStorage.getItem('ns_t'); } catch (e) { return null; } }
  function ready() { return window.CWXWidget && typeof window.CWXWidget.identify === 'function'; }

  var done = false;
  function tryIdentify() {
    if (done) return true;
    try {
      var t = nsT();
      if (!t || !ready()) return false;
      window.CWXWidget.identify(t);
      done = true;
      return true;
    } catch (e) { return false; }
  }

  function startPolling() {
    if (tryIdentify()) return;
    var deadline = Date.now() + GIVE_UP_MS;
    var timer = setInterval(function () {
      if (tryIdentify() || Date.now() > deadline) clearInterval(timer);
    }, POLL_MS);
  }

  var s = document.createElement('script');
  s.src = WIDGET_SRC;
  s.setAttribute('data-embed-key', PORTAL_EMBED_KEY);
  s.setAttribute('data-mode', 'portal');
  // identify() is a no-op if there is no token (e.g. not actually logged in). Start looking as soon
  // as the widget exists, and keep looking — the token may be written after we load, not before.
  s.onload = startPolling;
  (document.head || document.documentElement).appendChild(s);
})();
