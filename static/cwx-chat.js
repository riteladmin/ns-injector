/**
 * CloudWorx chat — NetSapiens portal shim (v3.3.0 P2). Injected into the manager portal via
 * ns-injector (same mechanism as intercom.js). Loads the chat widget in PORTAL mode and hands it the
 * logged-in user's session token (ns_t) so the agent + staff get VERIFIED identity.
 *
 * ns_t is read from the portal's own localStorage (same-origin) and passed to the widget's identify(),
 * which sends it ONCE over TLS at session-create; the server validates it live against NetSapiens and
 * discards it. It is never stored by the widget or this shim.
 *
 * Configure PORTAL_EMBED_KEY to the tenant's portal chat widget embed key.
 */
(function () {
  var PORTAL_EMBED_KEY = '6bcdaf879f10a0a31c8ba0240ea35038'; // RITEL portal widget (pilot)
  var WIDGET_SRC = 'https://webchat.cloudworxcx.com/widget.js';

  function nsT() { try { return localStorage.getItem('ns_t'); } catch (e) { return null; } }

  var s = document.createElement('script');
  s.src = WIDGET_SRC;
  s.setAttribute('data-embed-key', PORTAL_EMBED_KEY);
  s.setAttribute('data-mode', 'portal');
  s.onload = function () {
    // identify() is a no-op if there's no token (e.g. not actually logged in). The widget re-reads
    // nothing else; the token is handed over just-in-time before any session starts.
    try { var t = nsT(); if (t && window.CWXWidget && window.CWXWidget.identify) window.CWXWidget.identify(t); } catch (e) {}
  };
  (document.head || document.documentElement).appendChild(s);
})();
