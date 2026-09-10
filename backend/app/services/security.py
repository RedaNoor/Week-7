"""
Security middleware for the Real Estate Voice Agent API.

Provides:
- API key authentication (Depends-based)
- Optional admin-only authorization
- Request/response audit logging with PII redaction
- Input length validation helpers

Usage in main.py:

    from app.services.security import (
        require_api_key, require_admin_key, sanitize_text,
        AuditLogger, RateLimiter, rate_limit
    )

    app.add_middleware(AuditLogMiddleware)

    @app.post("/agent/chat", dependencies=[Depends(require_api_key)])
    def agent_chat(...): ...

    @app.post("/agent/learn", dependencies=[Depends(require_admin_key)])
    def agent_learn(...): ...

    @app.post("/agent/retrain",
              dependencies=[Depends(require_admin_key), Depends(rate_limit("retrain"))])
    def agent_retrain(...): ...
"""

from __future__ import annotations

import os
import re
import time
import logging
import threading
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Optional, Callable

from fastapi import Header, HTTPException, Request, status
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("security")
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_API_KEY = os.getenv("API_KEY", "").strip()
_ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "").strip()

# If neither is set, we still allow requests but log a warning — this lets
# local development continue without forcing key setup. Production should
# always set both.
_REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "false").lower() == "true"

# Trusted origins for the dashboard / website (CORS allow-list)
_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv(
        "TRUSTED_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000"
    ).split(",") if o.strip()
]

# Rate limit defaults (per-IP request counts over rolling 60s window)
RATE_LIMITS = {
    "default":    (60, 60),    # 60 req / 60s
    "chat":       (20, 60),    # 20 req / 60s
    "appointments": (5, 60),   # 5 bookings / 60s
    "retrain":    (2, 300),    # 2 retrains / 5 min
    "learn":      (10, 60),    # 10 manual learns / 60s
    "memory":     (30, 60),    # 30 memory queries / 60s
}

# Regex patterns for PII redaction in logs
_PII_PATTERNS = [
    # Pakistan phone numbers: +92 3xx xxxxxxx, 03xx xxxxxxx
    (re.compile(r"\+92[\s\-]?3\d{2}[\s\-]?\d{7}"), "+92-3XX-XXXXXXX"),
    (re.compile(r"\b03\d{2}[\s\-]?\d{7}\b"), "03XX-XXXXXXX"),
    # Email addresses
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "REDACTED@example.com"),
    # CNIC: 12345-1234567-1
    (re.compile(r"\b\d{5}-\d{7}-\d\b"), "XXXXX-XXXXXXX-X"),
]


def redact_pii(text: str) -> str:
    """Redact common PII patterns from a string for safe logging."""
    if not text:
        return text
    out = str(text)
    for pattern, replacement in _PII_PATTERNS:
        out = pattern.sub(replacement, out)
    return out


# ---------------------------------------------------------------------------
# Input sanitization
# ---------------------------------------------------------------------------
# CR/LF characters used for email header injection — strip before any
# field is placed into an RFC 822 header (Subject, To, From, etc.)
_HEADER_NEWLINE_RE = re.compile(r"[\r\n]")


def sanitize_header(value: Optional[str]) -> str:
    """Strip CR/LF from a string intended for an email header.

    Also limits length to 200 chars (defense-in-depth against log
    forgery and oversized header attacks)."""
    if not value:
        return ""
    cleaned = _HEADER_NEWLINE_RE.sub(" ", str(value))
    return cleaned[:200]


def sanitize_text(value: Optional[str], max_length: int = 8000) -> str:
    """Sanitize free-form text input. Truncates to max_length."""
    if not value:
        return ""
    v = str(value)
    # Strip null bytes (often used to bypass naive string checks)
    v = v.replace("\x00", "")
    return v[:max_length]


def sanitize_property_id(value: Optional[str]) -> Optional[str]:
    """Validate property ID format (e.g. P001, P027)."""
    if not value:
        return None
    v = str(value).strip().upper()
    if not re.match(r"^[Pp]\d{3}$", v):
        return None
    return v


def sanitize_session_id(value: Optional[str]) -> str:
    """Sanitize session ID — only allow alphanumerics, dash, underscore."""
    if not value:
        return "anonymous"
    v = str(value).strip()[:64]
    v = re.sub(r"[^A-Za-z0-9_\-]", "", v)
    return v or "anonymous"


# ---------------------------------------------------------------------------
# API key authentication
# ---------------------------------------------------------------------------
def _check_key(provided: str, expected: str) -> bool:
    """Constant-time string compare to prevent timing attacks."""
    if not expected or not provided:
        return False
    if len(provided) != len(expected):
        return False
    result = 0
    for a, b in zip(provided, expected):
        result |= ord(a) ^ ord(b)
    return result == 0


def require_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> None:
    """Dependency: require a valid X-API-Key header on the request.

    If REQUIRE_AUTH=false (default in dev), missing/invalid keys are logged
    but the request is allowed through. Set REQUIRE_AUTH=true in production.
    """
    if not _REQUIRE_AUTH:
        if not x_api_key:
            logger.debug("[auth] no API key provided (REQUIRE_AUTH=false, allowing)")
        return
    if not _API_KEY:
        logger.error("[auth] API_KEY is not configured but REQUIRE_AUTH=true")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server is not configured for authenticated access",
        )
    if not x_api_key or not _check_key(x_api_key, _API_KEY):
        logger.warning(f"[auth] invalid API key attempt: {redact_pii(x_api_key or '')[:20]}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )


def require_admin_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> None:
    """Dependency: require the admin API key (for mutating/admin endpoints)."""
    if not _REQUIRE_AUTH:
        if not x_api_key:
            logger.debug("[auth] no admin key provided (REQUIRE_AUTH=false, allowing)")
        return
    if not _ADMIN_API_KEY:
        logger.error("[auth] ADMIN_API_KEY is not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin endpoints are not configured",
        )
    if not x_api_key or not _check_key(x_api_key, _ADMIN_API_KEY):
        logger.warning("[auth] invalid admin key attempt")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


# ---------------------------------------------------------------------------
# Rate limiter (in-memory, per-IP)
# ---------------------------------------------------------------------------
class RateLimiter:
    """Simple in-memory per-IP sliding-window rate limiter.

    For multi-process deployment, swap this out for a Redis-backed limiter.
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """Returns True if request is allowed, False if rate-limited."""
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._hits[key]
            # Evict expired entries
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= max_requests:
                return False
            bucket.append(now)
            return True

    def reset(self, key: Optional[str] = None) -> None:
        with self._lock:
            if key:
                self._hits.pop(key, None)
            else:
                self._hits.clear()


rate_limiter = RateLimiter()


def rate_limit(bucket: str = "default") -> Callable:
    """Dependency factory: enforce a named rate-limit bucket per client IP."""
    def _dep(request: Request) -> None:
        if bucket not in RATE_LIMITS:
            return  # unknown bucket — skip
        max_req, window = RATE_LIMITS[bucket]
        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{bucket}"
        if not rate_limiter.check(key, max_req, window):
            logger.warning(f"[rate-limit] {client_ip} exceeded {bucket} ({max_req}/{window}s)")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {bucket}. Try again in {window} seconds.",
                headers={"Retry-After": str(window)},
            )
    return _dep


# ---------------------------------------------------------------------------
# CORS allow-list
# ---------------------------------------------------------------------------
def get_trusted_origins() -> list[str]:
    return _TRUSTED_ORIGINS


# ---------------------------------------------------------------------------
# Audit logging middleware
# ---------------------------------------------------------------------------
_SENSITIVE_PATHS = {"/appointments", "/agent/chat", "/agent/learn",
                    "/agent/retrain", "/orchestrator/"}
_REDACT_QUERY_PARAMS = {"q", "query", "message", "transcript", "lead_id",
                        "phone", "email", "to"}


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Logs every request with method, path, IP, status, duration.

    PII in query strings is redacted before logging.
    """

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        path = request.url.path

        # Pre-flight: skip OPTIONS
        if request.method == "OPTIONS":
            return await call_next(request)

        # Get client IP (respect X-Forwarded-For from proxies)
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        )

        # Sanitize query string for logging
        query = request.url.query
        if query:
            # Redact sensitive params
            parts = []
            for kv in query.split("&"):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    if k.lower() in _REDACT_QUERY_PARAMS:
                        parts.append(f"{k}=REDACTED")
                    else:
                        parts.append(f"{k}={redact_pii(v)[:80]}")
                else:
                    parts.append(redact_pii(kv)[:80])
            query_safe = "&".join(parts)
        else:
            query_safe = ""

        try:
            response: Response = await call_next(request)
        except Exception as exc:
            duration_ms = int((time.time() - start) * 1000)
            logger.error(
                f"AUDIT ip={client_ip} method={request.method} path={path} "
                f"q={query_safe} status=500 duration={duration_ms}ms "
                f"error={redact_pii(str(exc))[:200]}"
            )
            raise

        duration_ms = int((time.time() - start) * 1000)
        # Log all requests, but mark sensitive paths
        sensitive = any(p in path for p in _SENSITIVE_PATHS)
        logger.info(
            f"AUDIT ip={client_ip} method={request.method} path={path} "
            f"q={query_safe} status={response.status_code} "
            f"duration={duration_ms}ms "
            f"{'SENSITIVE' if sensitive else ''}"
        )

        # Add security headers to response
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        return response


# ---------------------------------------------------------------------------
# Webhook signature verification (placeholder for Twilio/Vapi/Deepgram)
# ---------------------------------------------------------------------------
def verify_twilio_signature(
    request: Request,
    body: bytes,
    auth_token: Optional[str] = None,
) -> bool:
    """Verify the X-Twilio-Signature header against the request body.

    Returns True if signature is valid OR if TWILIO_AUTH_TOKEN is not set
    (development mode). Production deployments MUST set TWILIO_AUTH_TOKEN.
    """
    token = auth_token or os.getenv("TWILIO_AUTH_TOKEN", "")
    if not token:
        logger.warning("[webhook] TWILIO_AUTH_TOKEN not set — skipping signature verification (dev only)")
        return True

    import hashlib
    import hmac
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    if not signature:
        return False
    # Twilio signs the URL + form params; for raw JSON webhook we sign URL + body
    message = url.encode() + body
    expected = hmac.new(token.encode(), message, hashlib.sha1).digest()
    expected_b64 = __import__("base64").b64encode(expected).decode()
    return _check_key(signature, expected_b64)


# ---------------------------------------------------------------------------
# Convenience: get current timestamp in ISO 8601 UTC
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
