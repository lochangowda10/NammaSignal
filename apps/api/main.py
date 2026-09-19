"""
NammaSignal Core API Gateway
FastAPI application with correlation IDs, CORS, structured logging, Cedar-protected routes,
authentication, and security enhancements.
"""

import time
import uuid
import logging
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.routes.observations import router as observations_router
from apps.api.routes.hazards import router as hazards_router
from apps.api.routes.simulation import router as simulation_router
from apps.api.routes.audit import router as audit_router
from apps.api.routes.auth import router as auth_router
from apps.api.security import apply_security_middleware
from domain.gazetteer import get_all_canonical_landmarks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nammasignal.api")

app = FastAPI(
    title="NammaSignal API",
    description="Unified, evidence-backed hazard assessment and fusion platform for Bengaluru road hazards.",
    version="1.0.0",
)

# Apply security enhancements
apply_security_middleware(app)

# CORS configuration for local web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start_time = time.perf_counter()

    response: Response = await call_next(request)

    process_time = (time.perf_counter() - start_time) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"

    logger.info(
        "HTTP %s %s -> %s (%.2fms) [Request-ID: %s]",
        request.method,
        request.url.path,
        response.status_code,
        process_time,
        request_id,
    )
    return response


# Include API v1 routes
API_V1_PREFIX = "/api/v1"
app.include_router(observations_router, prefix=API_V1_PREFIX)
app.include_router(hazards_router, prefix=API_V1_PREFIX)
app.include_router(simulation_router, prefix=API_V1_PREFIX)
app.include_router(audit_router, prefix=API_V1_PREFIX)
app.include_router(auth_router, prefix=API_V1_PREFIX)  # Authentication endpoints

# Also mount at root for direct criteria compatibility (e.g. POST /simulation/reset, POST /observations)
app.include_router(observations_router)
app.include_router(hazards_router)
app.include_router(simulation_router)
app.include_router(audit_router)
app.include_router(auth_router)  # Auth routes also at root for convenience


from pathlib import Path
from fastapi.responses import JSONResponse, FileResponse

WEB_INDEX_PATH = Path(__file__).parent.parent / "web" / "index.html"


@app.get("/", response_class=FileResponse, tags=["Frontend"])
@app.get("/dashboard", response_class=FileResponse, tags=["Frontend"])
def serve_dashboard():
    """Serves the NammaSignal interactive UI command center."""
    if WEB_INDEX_PATH.exists():
        return FileResponse(str(WEB_INDEX_PATH))
    return JSONResponse(
        content={"message": "NammaSignal API active. Dashboard index.html not found."},
        status_code=200,
    )


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "HEALTHY",
        "service": "NammaSignal Intelligence Engine",
        "version": "1.0.0",
        "cedar_security": "ACTIVE",
    }


@app.get(f"{API_V1_PREFIX}/landmarks", tags=["Landmarks"])
def get_landmarks():
    """Returns curated list of Bengaluru arterial hotspots and flood zones."""
    return get_all_canonical_landmarks()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=8000, reload=True)
