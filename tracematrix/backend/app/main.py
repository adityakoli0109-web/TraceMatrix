from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.auth import router as auth_router
from app.api.investigations import router as investigations_router
from app.api.system import router as system_router
from app.config import get_settings
from app.logging import configure_logging, new_request_id

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title="TraceMatrix API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or new_request_id()
        try:
            response = await call_next(request)
        except Exception:
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "request_id": rid},
            )
        response.headers["X-Request-ID"] = rid
        return response


app.add_middleware(RequestIdMiddleware)
app.include_router(auth_router)
app.include_router(investigations_router)
app.include_router(system_router)


@app.exception_handler(Exception)
async def unhandled(_, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
