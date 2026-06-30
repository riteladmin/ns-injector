# NS-Injector — read-only control panel (additive; never writes config).
import os, json, html, datetime as dt, urllib.request
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

CONFIG_FILE = os.getenv("CONFIG_FILE", "/app/config/endpoints.json")
STATIC_DIR  = os.getenv("STATIC_DIR", "/app/static")
HEALTH_URL  = os.getenv("INJECTOR_HEALTH", "http://localhost:8000/health")
PUB_STATIC  = "https://js.cloudworxcx.com/static/"

app = FastAPI(docs_url=None, redoc_url=None)
e = lambda s: html.escape(str(s if s is not None else ""))

def load_cfg():
    try:
        with open(CONFIG_FILE) as f: return json.load(f), os.path.getmtime(CONFIG_FILE), None
    except Exception as ex: return {}, None, str(ex)

def static_files():
    out = []
    try:
        for fn in sorted(os.listdir(STATIC_DIR)):
            if not fn.endswith(".js") or ".bak" in fn: continue
            st = os.stat(os.path.join(STATIC_DIR, fn))
            out.append({"name": fn, "size": st.st_size, "mtime": st.st_mtime})
    except Exception: pass
    return out

def classify(u):
    if u.startswith(PUB_STATIC): return "local", u[len(PUB_STATIC):]
    if u.startswith("/static/"): return "local", u[len("/static/"):]
    if u.startswith("/"):        return "portal", None
    return "external", None

def health():
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=2) as r:
            return True, json.load(r)
    except Exception as ex: return False, str(ex)

CSS = """
:root{--ink:#1b2733;--muted:#6b7682;--line:#e6ebf0;--bg:#f3f6f9;--blue:#1f4e79;--card:#fff}
*{box-sizing:border-box} body{margin:0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}
.wrap{max-width:980px;margin:0 auto;padding:22px 20px 60px}
.top{display:flex;align-items:center;gap:14px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:14px;margin-bottom:20px}
.top h1{font-size:18px;margin:0;font-weight:650;letter-spacing:.2px}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:6px}
.dot.ok{background:#1e8a52}.dot.bad{background:#cf4444}
.pill{font-size:12px;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.card h3{margin:0 0 10px;font-size:14px;font-family:ui-monospace,Menlo,Consolas,monospace;color:var(--blue)}
ol{margin:0;padding-left:0;list-style:none} ol li{padding:7px 0;border-top:1px solid #f0f3f6;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
ol li:first-child{border-top:0} code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;word-break:break-all}
.meta{color:var(--muted);font-size:11.5px;margin-left:auto;white-space:nowrap}
.b{font-size:10px;font-weight:700;letter-spacing:.4px;padding:2px 7px;border-radius:20px;text-transform:uppercase}
.b.local{background:#e9f6ee;color:#1e8a52}.b.portal{background:#eaf2f9;color:#1f4e79}.b.ext{background:#fcf3e4;color:#b07d12}
.b.missing{background:#fde8e8;color:#cf4444}.b.orphan{background:#f0eef9;color:#6a4fb0}
.empty{color:var(--muted);font-style:italic}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);margin:26px 0 10px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:9px 14px;font-size:13px;border-top:1px solid var(--line)} th{background:#fafbfc;color:var(--muted);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.4px;border-top:0}
td.num{font-variant-numeric:tabular-nums;color:var(--muted)}
.note{background:#eaf2f9;border:1px solid #d7e6f4;color:#274b6d;font-size:12.5px;border-radius:10px;padding:12px 14px;margin-top:22px;line-height:1.5}
details{margin-top:18px} summary{cursor:pointer;color:var(--muted);font-size:12.5px} pre{background:#0f1c2b;color:#cfe3f5;padding:14px;border-radius:10px;overflow:auto;font-size:12px}
a{color:var(--blue)}
"""

@app.get("/health")
def hz(): return {"status": "ok", "role": "admin"}

@app.get("/api/state")
def state():
    cfg, mt, err = load_cfg()
    return JSONResponse({"config": cfg, "config_error": err, "static": [
        {**f, "mtime": dt.datetime.fromtimestamp(f["mtime"]).isoformat()} for f in static_files()]})

@app.get("/", response_class=HTMLResponse)
def index():
    cfg, mt, err = load_cfg()
    files = static_files()
    fileset = {f["name"]: f for f in files}
    ok, hinfo = health()

    referenced = {}
    roles_html = ""
    for role, scripts in (cfg.items() if isinstance(cfg, dict) else []):
        scripts = scripts or []
        items = ""
        for u in scripts:
            kind, fn = classify(u)
            if kind == "local":
                referenced.setdefault(fn, set()).add(role)
                f = fileset.get(fn)
                if f:
                    meta = "{:,} B · {:%Y-%m-%d %H:%M}".format(f["size"], dt.datetime.fromtimestamp(f["mtime"]))
                    badge = '<span class="b local">local</span>'
                else:
                    meta = "file not found in /static"; badge = '<span class="b missing">missing file</span>'
                items += '<li>{}<code>{}</code><span class="meta">{}</span></li>'.format(badge, e(u), e(meta))
            elif kind == "portal":
                items += '<li><span class="b portal">portal</span><code>{}</code><span class="meta">served by the NetSapiens portal</span></li>'.format(e(u))
            else:
                items += '<li><span class="b ext">external</span><code>{}</code></li>'.format(e(u))
        roles_html += '<div class="card"><h3>/{}</h3><ol>{}</ol></div>'.format(e(role), items or '<li class="empty">(no scripts)</li>')

    rows = ""
    for f in files:
        refs = referenced.get(f["name"])
        ref = ", ".join("/" + e(r) for r in sorted(refs)) if refs else '<span class="b orphan">orphan</span>'
        rows += '<tr><td><code>{}</code></td><td class="num">{:,}</td><td class="num">{:%Y-%m-%d %H:%M}</td><td>{}</td></tr>'.format(
            e(f["name"]), f["size"], dt.datetime.fromtimestamp(f["mtime"]), ref)

    hdot = '<span class="dot ok"></span>injector healthy' if ok else '<span class="dot bad"></span>injector unreachable'
    cfgmt = "{:%Y-%m-%d %H:%M}".format(dt.datetime.fromtimestamp(mt)) if mt else "—"
    raw = e(json.dumps(cfg, indent=2)) if not err else e("ERROR reading config: " + str(err))

    html_doc = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NS Injector — Control Panel</title><style>{css}</style></head><body><div class="wrap">
<div class="top"><h1>NS Injector — Control Panel</h1>
<span class="pill">{hdot}</span>
<span class="pill">config: <code>{cfgfile}</code> · updated {cfgmt}</span>
<span class="pill" style="margin-left:auto"><a href="/">↻ refresh</a> · read-only</span></div>
<h2>Roles &amp; injected scripts</h2><div class="grid">{roles}</div>
<h2>Locally-hosted scripts (/static)</h2>
<table><thead><tr><th>File</th><th class="num">Size</th><th class="num">Modified</th><th>Used by</th></tr></thead><tbody>{rows}</tbody></table>
<div class="note"><b>How this is wired:</b> the NetSapiens portal loads <code>https://js.cloudworxcx.com/&lt;role&gt;</code> via a scoped <code>PORTAL_EXTRA_JS</code> setting; the injector returns a small loader that injects that role's scripts into the portal page. <span class="b local">local</span> = hosted here in <code>/static</code>; <span class="b portal">portal</span> = a relative path served by the NetSapiens portal itself (e.g. <code>/intercom.js</code>); <span class="b ext">external</span> = a third-party URL. This panel is <b>read-only</b> — edit <code>endpoints.json</code> on the box to change anything.</div>
<details><summary>Raw endpoints.json</summary><pre>{raw}</pre></details>
</div></body></html>""".format(css=CSS, hdot=hdot, cfgfile=e(CONFIG_FILE), cfgmt=cfgmt, roles=roles_html, rows=rows or '<tr><td colspan=4 class="empty">none</td></tr>', raw=raw)
    return HTMLResponse(html_doc)
