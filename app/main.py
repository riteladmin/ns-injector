import os
import json
import logging
from contextlib import asynccontextmanager
from ipaddress import ip_address, ip_network

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("ns-injector")

CONFIG_FILE = os.getenv("CONFIG_FILE", "/app/config/endpoints.json")

# Comma-separated CIDRs or IPs. Empty = allow all.
ALLOWED_IPS = os.getenv("ALLOWED_IPS", "")

_allowed_networks = []
if ALLOWED_IPS:
    for entry in ALLOWED_IPS.split(","):
        entry = entry.strip()
        if entry:
            _allowed_networks.append(ip_network(entry, strict=False))

# In-memory cache for the config to avoid disk reads on every request
_config_cache = {}
_last_mtime = 0


def get_config() -> dict:
    global _config_cache, _last_mtime
    try:
        current_mtime = os.path.getmtime(CONFIG_FILE)
        if current_mtime > _last_mtime:
            with open(CONFIG_FILE, "r") as f:
                _config_cache = json.load(f)
            _last_mtime = current_mtime
            logger.info("Configuration reloaded from disk.")
    except FileNotFoundError:
        logger.error("Config file %s not found.", CONFIG_FILE)
    except json.JSONDecodeError:
        logger.error("Invalid JSON in %s. Using last known good config.", CONFIG_FILE)

    return _config_cache


def _is_allowed(client_ip: str) -> bool:
    if not _allowed_networks:
        return True
    try:
        addr = ip_address(client_ip)
    except ValueError:
        return False
    return any(addr in net for net in _allowed_networks)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _allowed_networks:
        logger.info("IP allowlist active: %s", ALLOWED_IPS)
    else:
        logger.info("IP allowlist disabled — all sources permitted.")
    logger.info("Pre-loading configuration...")
    get_config()
    yield


app = FastAPI(docs_url=None, redoc_url=None, lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

STATIC_DIR = os.getenv("STATIC_DIR", "/app/static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.middleware("http")
async def ip_allowlist(request: Request, call_next):
    # Always allow health checks from localhost
    if request.url.path == "/health":
        return await call_next(request)
    client_ip = request.client.host if request.client else "unknown"
    if not _is_allowed(client_ip):
        logger.warning("Blocked request from %s to %s", client_ip, request.url.path)
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})
    return await call_next(request)


@app.get("/health", include_in_schema=False)
async def health():
    config = get_config()
    return JSONResponse({"status": "healthy", "roles": len(config)})


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.get("/{role}")
async def serve_injector(request: Request, role: str):
    config = get_config()
    logger.info("Role endpoint triggered: %s (client: %s)", role, request.client.host if request.client else "unknown")

    scripts = config.get(role)
    if not scripts:
        scripts = config.get("default")

    if not scripts:
        raise HTTPException(status_code=404, detail="Endpoint not configured and no default found.")

    response = templates.TemplateResponse(
        "injector.js",
        {"request": request, "scripts": scripts},
        media_type="application/javascript",
    )

    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response
