# NS-Injector — control panel (read + EDIT). Writes config/static for the ADMIN container only.
# Safe-by-construction: validate -> timestamped backup -> atomic write -> one-click revert.
import os, json, html, shutil, re, datetime as dt, urllib.request, glob
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

CONFIG_FILE = os.getenv("CONFIG_FILE", "/app/config/endpoints.json")
STATIC_DIR  = os.getenv("STATIC_DIR", "/app/static")
HEALTH_URL  = os.getenv("INJECTOR_HEALTH", "http://localhost:8000/health")
PUB_STATIC  = "https://js.cloudworxcx.com/static/"
MAX_BACKUPS = 14

app = FastAPI(docs_url=None, redoc_url=None)

KNOWN = [("intercom",("Intercom Live Chat","Support chat bubble (served by the NetSapiens portal).")),
         ("postcall-ai",("Post Call AI","Per-call summary + to-do widget.")),
         ("call-tracer",("Call Tracer","Call-tracing button in the portal nav.")),
         ("promptvoice",("PromptVoice — Recording Studio","Third-party recording-studio button."))]
def describe(url):
    for k,(nm,d) in KNOWN:
        if k in url.lower(): return nm,d
    return (url.rstrip("/").split("/")[-1] or url), "Custom script."

# Documented wiring (NS can't be cleanly enumerated via API; this is the known mapping).
WIRING = {
 "superuser": {"status":"live","by":["super-user scope","brandontest","TheFireplaceShowcase"]},
 "basicuser": {"status":"unused","by":[]},
 "default":   {"status":"unused","by":["injector fallback only"]},
}
WIRING_NOTE = "Most domains never hit the injector — they load /intercom.js directly via the global PORTAL_EXTRA_JS. Only roles marked LIVE are referenced."

def load_cfg():
    with open(CONFIG_FILE) as f: return json.load(f)

def validate(cfg):
    if not isinstance(cfg, dict): raise ValueError("Top level must be an object of role → list of scripts.")
    for role, scripts in cfg.items():
        if not isinstance(role,str) or not role.strip(): raise ValueError("Role names must be non-empty text.")
        if not isinstance(scripts,list): raise ValueError("Role '%s' must be a list of script URLs." % role)
        for s in scripts:
            if not isinstance(s,str) or not s.strip(): raise ValueError("Role '%s' has an empty script entry." % role)

def backups():
    paths=sorted(glob.glob(CONFIG_FILE+".bak-*"), key=os.path.getmtime, reverse=True)
    return [{"name":os.path.basename(p),"mtime":dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%b %-d, %Y %H:%M:%S")} for p in paths]

def save_cfg(cfg):
    validate(cfg)
    ts=dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    if os.path.exists(CONFIG_FILE): shutil.copy2(CONFIG_FILE, CONFIG_FILE+".bak-"+ts)
    tmp=CONFIG_FILE+".tmp"
    with open(tmp,"w") as f: json.dump(cfg,f,indent=4)
    os.replace(tmp, CONFIG_FILE)
    for p in sorted(glob.glob(CONFIG_FILE+".bak-*"), key=os.path.getmtime, reverse=True)[MAX_BACKUPS:]:
        try: os.remove(p)
        except Exception: pass

def static_files():
    out=[]
    for fn in sorted(os.listdir(STATIC_DIR)):
        if not fn.endswith(".js") or ".bak" in fn: continue
        st=os.stat(os.path.join(STATIC_DIR,fn)); out.append({"name":fn,"size":st.st_size,"mtime":dt.datetime.fromtimestamp(st.st_mtime).strftime("%b %-d, %Y %H:%M")})
    return out

def health():
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=2) as r: json.load(r); return True
    except Exception: return False

@app.get("/health")
def hz(): return {"status":"ok","role":"admin"}

@app.get("/api/state")
def state():
    try: cfg=load_cfg(); err=None
    except Exception as e: cfg={}; err=str(e)
    enriched={}
    for role,scripts in (cfg.items() if isinstance(cfg,dict) else []):
        items=[]
        for u in scripts:
            nm,d=describe(u)
            local = u.startswith(PUB_STATIC) or u.startswith("/static/")
            kind = "here" if local else ("portal" if u.startswith("/") else "external")
            items.append({"url":u,"name":nm,"desc":d,"kind":kind})
        enriched[role]=items
    return JSONResponse({"ok":err is None,"error":err,"config":cfg,"roles":enriched,
        "wiring":WIRING,"wiring_note":WIRING_NOTE,"static":static_files(),"backups":backups(),
        "injector_ok":health()})

@app.post("/api/save")
async def save(req: Request):
    try:
        body=await req.json(); cfg=body.get("config")
        if isinstance(cfg,str): cfg=json.loads(cfg)
        save_cfg(cfg)
        return {"ok":True,"message":"Saved. The injector will use it on the next portal load."}
    except json.JSONDecodeError as e:
        return JSONResponse({"ok":False,"error":"Invalid JSON: "+str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"ok":False,"error":str(e)}, status_code=400)

@app.post("/api/revert")
async def revert(req: Request):
    try:
        name=(await req.json()).get("name","")
        if not re.fullmatch(r"endpoints\.json\.bak-[0-9-]+", name): raise ValueError("Bad backup name.")
        src=os.path.join(os.path.dirname(CONFIG_FILE), name)
        if not os.path.exists(src): raise ValueError("Backup not found.")
        with open(src) as f: cfg=json.load(f)
        save_cfg(cfg)   # validates + snapshots current before restoring
        return {"ok":True,"message":"Reverted to "+name}
    except Exception as e:
        return JSONResponse({"ok":False,"error":str(e)}, status_code=400)

@app.post("/api/upload")
async def upload(req: Request):
    try:
        name=os.path.basename(req.query_params.get("name",""))
        if not name.endswith(".js"): raise ValueError("Only .js files are allowed.")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", name): raise ValueError("Filename may only contain letters, numbers, dot, dash, underscore.")
        data=await req.body()
        if not data: raise ValueError("Empty upload.")
        if len(data) > 2_000_000: raise ValueError("File too large (max 2 MB).")
        dest=os.path.join(STATIC_DIR, name); existed=os.path.exists(dest)
        if existed: shutil.copy2(dest, dest+".bak-"+dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
        tmp=dest+".uptmp"
        with open(tmp,"wb") as fh: fh.write(data)
        os.replace(tmp,dest)
        return {"ok":True,"message":("Replaced " if existed else "Uploaded ")+name+" - served at /static/"+name,"name":name}
    except Exception as ex:
        return JSONResponse({"ok":False,"error":str(ex)}, status_code=400)

@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(PAGE)

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Portal Injector — Control Panel</title>
<style>
:root{--ink:#13212e;--mut:#5f6b78;--soft:#8b96a2;--line:#e4eaf0;--bg:#eef2f6;--paper:#fff;--tint:#f5f9fc;
--blue:#2f6da3;--blueD:#1f4e79;--blueL:#eaf2f9;--gold:#c4982e;--goldL:#fbf4e3;--green:#1e8a52;--greenL:#e9f6ee;--red:#cf4444;--redL:#fde8e8}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12.5px;word-break:break-all}
.bar{background:linear-gradient(135deg,var(--blue),var(--blueD));color:#fff;padding:16px 0}
.bar .wrap{display:flex;align-items:center;gap:14px}
.bar h1{margin:0;font-size:18px;font-weight:680;letter-spacing:.3px}.bar .tag{font-size:11px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;background:rgba(255,255,255,.16);padding:3px 9px;border-radius:20px}
.bar .gold{color:var(--gold)} .bar .right{margin-left:auto;display:flex;gap:9px;align-items:center}
.hp{display:inline-flex;align-items:center;gap:7px;font-size:12px;font-weight:600;background:rgba(255,255,255,.14);border-radius:20px;padding:5px 11px}
.dot{width:8px;height:8px;border-radius:50%}.dot.ok{background:#7ff0b0}.dot.bad{background:#ff9a9a}
.wrap{max-width:1020px;margin:0 auto;padding:0 22px}
.sub{color:var(--mut);font-size:13.5px;margin:16px 0 0}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.7px;color:var(--soft);margin:28px 0 12px;font-weight:700}
.note{background:var(--goldL);border:1px solid #efe2c4;color:#6b5418;font-size:12.5px;border-radius:11px;padding:12px 15px;line-height:1.55}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}
.card{background:var(--paper);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.ch{display:flex;align-items:center;gap:9px;padding:12px 15px;border-bottom:1px solid var(--line);background:var(--tint)}
.ch .role{font-family:ui-monospace,monospace;font-size:13px;color:var(--blueD);font-weight:700}
.badge{font-size:10px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;padding:2px 8px;border-radius:20px}
.bg-live{background:var(--greenL);color:var(--green)}.bg-unused{background:#eef0f3;color:var(--soft)}
.ch .by{margin-left:auto;font-size:11px;color:var(--soft);text-align:right}
.scripts{list-style:none;margin:0;padding:6px}
.s{display:flex;align-items:center;gap:9px;padding:8px 9px;border-radius:9px}.s+.s{border-top:1px solid #f1f4f7}
.s .ic{flex:none;width:9px;height:9px;border-radius:50%}.ic.here{background:var(--green)}.ic.portal{background:var(--blue)}.ic.external{background:var(--gold)}
.s .nm{font-weight:600;font-size:13.5px}.s .u{color:var(--soft);font-size:11px}
.s .x{margin-left:auto;border:0;background:none;color:var(--soft);cursor:pointer;font-size:16px;line-height:1;padding:2px 6px;border-radius:6px}.s .x:hover{background:var(--redL);color:var(--red)}
.s .mv{border:1px solid var(--line);background:#fff;color:var(--mut);cursor:pointer;border-radius:6px;font-size:11px;padding:1px 5px}
.addrow{display:flex;gap:6px;padding:8px 9px 11px}.addrow input{flex:1;border:1px solid var(--line);border-radius:8px;padding:6px 9px;font-size:12.5px;font-family:ui-monospace,monospace}
.btn{border:0;border-radius:8px;padding:7px 13px;font-size:13px;font-weight:600;cursor:pointer}
.btn.pri{background:var(--blue);color:#fff}.btn.pri:hover{background:var(--blueD)}.btn.ghost{background:#fff;border:1px solid var(--line);color:var(--ink)}.btn.sm{padding:5px 10px;font-size:12px}
.btn.gold{background:var(--gold);color:#3a2c08}.btn:disabled{opacity:.5;cursor:default}
.toolbar{display:flex;gap:10px;align-items:center;margin:14px 0;flex-wrap:wrap}
.panel{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:16px}
textarea{width:100%;min-height:230px;border:1px solid var(--line);border-radius:10px;padding:13px;font-family:ui-monospace,monospace;font-size:12.5px;line-height:1.5;color:#0f1c2b;background:#fbfdff}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:9px 12px;font-size:13px;border-top:1px solid var(--line)}th{color:var(--soft);font-size:11px;text-transform:uppercase;letter-spacing:.4px;border-top:0}
td.n{font-variant-numeric:tabular-nums;color:var(--mut);white-space:nowrap}
.bk{display:flex;align-items:center;gap:10px;padding:7px 0;border-top:1px solid var(--line);font-size:12.5px}.bk:first-child{border-top:0}.bk code{flex:1}
.up{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.muted{color:var(--soft);font-size:12px}
#toast{position:fixed;right:18px;bottom:18px;display:flex;flex-direction:column;gap:8px;z-index:50}
.t{padding:11px 15px;border-radius:10px;font-size:13px;font-weight:600;box-shadow:0 8px 24px rgba(20,30,45,.18);max-width:360px}
.t.ok{background:var(--green);color:#fff}.t.err{background:var(--red);color:#fff}
details{margin-top:10px}summary{cursor:pointer;color:var(--mut);font-size:12.5px}
.tabs{display:flex;gap:6px;margin-bottom:12px}.tab{padding:7px 14px;border-radius:9px 9px 0 0;cursor:pointer;font-size:13px;font-weight:600;color:var(--mut);background:transparent;border:0}.tab.on{background:var(--paper);color:var(--blueD);border:1px solid var(--line);border-bottom-color:var(--paper)}
.foot{margin:30px 0 60px;color:var(--soft);font-size:11.5px;text-align:center}
</style></head><body>
<div class="bar"><div class="wrap"><h1>CloudWorx <span class="gold">·</span> Portal Injector</h1><span class="tag">Control Panel</span>
<div class="right"><span class="hp" id="hp"><span class="dot bad"></span>checking…</span></div></div></div>
<div class="wrap">
<p class="sub">What gets injected into the NetSapiens portal, who sees it, and the scripts hosted on this box — all editable here. Edits are validated, backed up automatically, and the injector reloads them on the next portal load.</p>

<div class="tabs">
<button class="tab on" data-tab="manage" onclick="tab('manage')">Manage</button>
<button class="tab" data-tab="raw" onclick="tab('raw')">Raw JSON</button>
<button class="tab" data-tab="files" onclick="tab('files')">Hosted files</button>
<button class="tab" data-tab="backups" onclick="tab('backups')">Backups</button>
</div>

<div id="manage">
<div class="note" id="wnote"></div>
<h2>Who sees what — roles &amp; injected scripts</h2>
<div class="grid" id="roles"></div>
<div class="toolbar"><input id="newrole" placeholder="new role name (e.g. superuser)" style="border:1px solid var(--line);border-radius:8px;padding:7px 10px;font-size:13px">
<button class="btn ghost sm" onclick="addRole()">+ Add role</button>
<button class="btn pri" id="saveBtn" onclick="saveCfg()" style="margin-left:auto">Save changes</button>
<span class="muted" id="dirty"></span></div>
</div>

<div id="raw" style="display:none"><div class="panel">
<div style="display:flex;align-items:center;margin-bottom:10px"><b style="font-size:14px">endpoints.json</b><span class="muted" style="margin-left:auto">edit directly · validated on save</span></div>
<textarea id="rawta" spellcheck="false"></textarea>
<div class="toolbar"><button class="btn pri" onclick="saveRaw()">Save raw JSON</button><button class="btn ghost" onclick="render()">Reset to current</button></div>
</div></div>

<div id="files" style="display:none"><div class="panel">
<h2 style="margin-top:0">Scripts hosted on this box <span class="muted">(/static)</span></h2>
<table id="ftab"><thead><tr><th>File</th><th>Size</th><th>Updated</th><th>Used by</th></tr></thead><tbody></tbody></table>
<h2>Add a locally-hosted script</h2>
<div class="up"><input type="file" id="upfile" accept=".js"><button class="btn gold" onclick="doUpload()">Upload .js</button>
<span class="muted">Saved to /static, served instantly. Then add <code>https://js.cloudworxcx.com/static/&lt;file&gt;</code> to a role under Manage.</span></div>
</div></div>

<div id="backups" style="display:none"><div class="panel">
<h2 style="margin-top:0">Config backups <span class="muted">(newest first · auto-created on every save)</span></h2>
<div id="bklist"></div>
</div></div>

<div class="foot">Read+write · private to the LAN/WireGuard · injector container is separate and untouched.</div>
</div>
<div id="toast"></div>
<script>
var S=null, cfg={}, dirty=false;
function toast(msg,ok){var d=document.createElement('div');d.className='t '+(ok?'ok':'err');d.textContent=msg;document.getElementById('toast').appendChild(d);setTimeout(function(){d.remove()},4200)}
function tab(n){['manage','raw','files','backups'].forEach(function(t){document.getElementById(t).style.display=t==n?'':'none'});document.querySelectorAll('.tab').forEach(function(b){b.classList.toggle('on',b.dataset.tab==n)});if(n=='raw')document.getElementById('rawta').value=JSON.stringify(cfg,null,4)}
function esc(s){return (s+'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function setDirty(v){dirty=v;document.getElementById('dirty').textContent=v?'unsaved changes':''}
function load(){fetch('api/state').then(function(r){return r.json()}).then(function(d){S=d;cfg=JSON.parse(JSON.stringify(d.config||{}));
 document.getElementById('hp').innerHTML='<span class="dot '+(d.injector_ok?'ok':'bad')+'"></span>'+(d.injector_ok?'Injector running':'Injector unreachable');
 document.getElementById('wnote').innerHTML='<b>How roles are used:</b> '+esc(d.wiring_note);
 render();setDirty(false)})}
function kindOf(u){return (u.indexOf('https://js.cloudworxcx.com/static/')==0||u.indexOf('/static/')==0)?'here':(u[0]=='/'?'portal':'external')}
function nameOf(u){var k={'intercom':'Intercom Live Chat','postcall-ai':'Post Call AI','call-tracer':'Call Tracer','promptvoice':'PromptVoice — Recording Studio'};for(var x in k){if(u.toLowerCase().indexOf(x)>=0)return k[x]}return u.split('/').pop()||u}
function render(){
 var roles=document.getElementById('roles');roles.innerHTML='';
 Object.keys(cfg).forEach(function(role){
  var w=(S.wiring||{})[role]||{status:'',by:[]};
  var st=w.status=='live'?'<span class="badge bg-live">live</span>':(w.status=='unused'?'<span class="badge bg-unused">unused</span>':'');
  var by=(w.by&&w.by.length)?('used by: '+w.by.map(esc).join(', ')):(w.status=='unused'?'not referenced by anything':'');
  var items='';(cfg[role]||[]).forEach(function(u,i){
   items+='<li class="s"><span class="ic '+kindOf(u)+'"></span><div><div class="nm">'+esc(nameOf(u))+'</div><div class="u">'+esc(u)+'</div></div>'+
    '<button class="mv" onclick="mv(\''+role+'\','+i+',-1)">↑</button><button class="mv" onclick="mv(\''+role+'\','+i+',1)">↓</button>'+
    '<button class="x" title="remove" onclick="rm(\''+role+'\','+i+')">×</button></li>';
  });
  var c=document.createElement('div');c.className='card';
  c.innerHTML='<div class="ch"><span class="role">/'+esc(role)+'</span>'+st+'<span class="by">'+esc(by)+'</span></div>'+
   '<ul class="scripts">'+(items||'<li class="s"><span class="u">no scripts — nothing is injected</span></li>')+'</ul>'+
   '<div class="addrow"><input placeholder="script URL or /static/file.js" id="add_'+role+'"><button class="btn ghost sm" onclick="addScript(\''+role+'\')">Add</button>'+
   '<button class="btn ghost sm" title="delete role" onclick="delRole(\''+role+'\')">Delete role</button></div>';
  roles.appendChild(c);
 });
 // files tab
 var tb=document.querySelector('#ftab tbody');tb.innerHTML='';
 (S.static||[]).forEach(function(f){
  var used=[];Object.keys(cfg).forEach(function(r){(cfg[r]||[]).forEach(function(u){if(u.indexOf('/static/'+f.name)>=0||u.indexOf(f.name)>=0&&kindOf(u)=='here')used.push('/'+r)})});
  tb.innerHTML+='<tr><td><code>'+esc(f.name)+'</code></td><td class="n">'+(f.size>1024?Math.round(f.size/1024)+' KB':f.size+' B')+'</td><td class="n">'+esc(f.mtime)+'</td><td>'+(used.length?used.map(function(x){return '<code>'+esc(x)+'</code>'}).join(' '):'<span class="muted">unused</span>')+'</td></tr>';
 });
 // backups tab
 var bl=document.getElementById('bklist');bl.innerHTML='';
 (S.backups||[]).forEach(function(b){bl.innerHTML+='<div class="bk"><code>'+esc(b.name)+'</code><span class="muted">'+esc(b.mtime)+'</span><button class="btn ghost sm" onclick="revert(\''+b.name+'\')">Restore</button></div>'});
 if(!(S.backups||[]).length)bl.innerHTML='<span class="muted">No backups yet — they\'re created automatically on each save.</span>';
 document.getElementById('rawta').value=JSON.stringify(cfg,null,4);
}
function mv(r,i,d){var a=cfg[r];var j=i+d;if(j<0||j>=a.length)return;var t=a[i];a[i]=a[j];a[j]=t;setDirty(true);render()}
function rm(r,i){cfg[r].splice(i,1);setDirty(true);render()}
function addScript(r){var el=document.getElementById('add_'+r);var v=(el.value||'').trim();if(!v)return;cfg[r].push(v);setDirty(true);render()}
function addRole(){var v=(document.getElementById('newrole').value||'').trim();if(!v)return;if(cfg[v]){toast('Role already exists',false);return}cfg[v]=[];document.getElementById('newrole').value='';setDirty(true);render()}
function delRole(r){if(!confirm('Delete role /'+r+'? The injector will 404→fallback to /default for anything pointed at it.'))return;delete cfg[r];setDirty(true);render()}
function post(url,body){return fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(function(r){return r.json().then(function(j){return{ok:r.ok,j:j}})})}
function commit(payload){return post('api/save',payload).then(function(x){if(x.ok&&x.j.ok){toast(x.j.message||'Saved',true);load()}else{toast((x.j&&x.j.error)||'Save failed',false)}})}
function saveCfg(){var live=cfg.superuser?'':'';if(!confirm('Save changes to the injector config?\\n\\nThis affects what loads in the live portal for anything pointed at these roles (currently /superuser).'))return;commit({config:cfg})}
function saveRaw(){var t=document.getElementById('rawta').value;var p;try{p=JSON.parse(t)}catch(e){toast('Invalid JSON: '+e.message,false);return}if(!confirm('Save this raw JSON as the live injector config?'))return;commit({config:p})}
function revert(name){if(!confirm('Restore '+name+'? (the current config is backed up first)'))return;post('api/revert',{name:name}).then(function(x){if(x.ok&&x.j.ok){toast(x.j.message,true);load()}else{toast((x.j&&x.j.error)||'Revert failed',false)}})}
function doUpload(){var f=document.getElementById('upfile').files[0];if(!f){toast('Pick a .js file first',false);return}fetch('api/upload?name='+encodeURIComponent(f.name),{method:'POST',headers:{'Content-Type':'application/javascript'},body:f}).then(function(r){return r.json().then(function(j){return{ok:r.ok,j:j}})}).then(function(x){if(x.ok&&x.j.ok){toast(x.j.message,true);load()}else{toast((x.j&&x.j.error)||'Upload failed',false)}})}
load();
</script></body></html>"""
