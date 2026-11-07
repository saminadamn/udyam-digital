import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import errors
from app.config import get_settings
from app.db import Base, engine
from app.routers import admin, admin_orders, advisor, auth, consent, escalations, kyc, notifications, products, quotes, system, voice
from app.security import log_filter

logging.basicConfig(level=logging.INFO)
log_filter.install()

@asynccontextmanager
async def lifespan(_: FastAPI):
    get_settings().check_secrets()
    Base.metadata.create_all(engine)
    tasks = []
    if get_settings().retention_job_enabled:
        from app.kyc.retention import loop as retention

        tasks.append(asyncio.create_task(retention(get_settings().retention_job_interval_sec)))
    if get_settings().sla_job_enabled:
        from app.escalations.sla import loop

        tasks.append(asyncio.create_task(loop(get_settings().sla_scan_interval_sec)))
    if get_settings().notify_dispatch_enabled:
        from app.notifications.service import loop as dispatch

        tasks.append(asyncio.create_task(dispatch(get_settings().notify_dispatch_interval_sec)))
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="Udyam Digital API", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
                   allow_origin_regex=get_settings().cors_origin_regex or None,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
errors.install(app)


@app.exception_handler(HTTPException)
async def _http(_: Request, exc: HTTPException):
    d = exc.detail if isinstance(exc.detail, dict) else {"code": "ERROR", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=errors.body(d.get("code", "ERROR"), d.get("message", ""), d.get("details")))


PREFIX = "/api/v1"
ROUTERS = (auth.router, auth.me_router, advisor.router, voice.router, admin.router, notifications.router, products.router, quotes.router, quotes.orders_router,
           consent.router, kyc.router, escalations.router, escalations.agents_router, admin_orders.router, system.router)
for r in ROUTERS:
    app.include_router(r, prefix=PREFIX)
