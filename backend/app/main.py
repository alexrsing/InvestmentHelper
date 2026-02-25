from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.middleware import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    RequestLoggingMiddleware
)
from app.routers import etfs
from app.routers import portfolio


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Secure Investment Helper API with JWT authentication",
    docs_url=f"{settings.API_V1_STR}/docs",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS Middleware - Configure allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,  # Specific origins only
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # Explicit methods
    allow_headers=["Authorization", "Content-Type"],  # Explicit headers
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Security Middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    calls=settings.RATE_LIMIT_PER_MINUTE,
    period=60
)
app.add_middleware(RequestLoggingMiddleware)


# Include routers
app.include_router(
    etfs.router,
    prefix=settings.API_V1_STR,
)
app.include_router(
    portfolio.router,
    prefix=settings.API_V1_STR,
)


# Health check endpoint (no auth required)
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "service": settings.PROJECT_NAME}


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler to prevent information leakage.
    Never expose internal errors to clients.
    """
    # Log the actual error internally
    print(f"Unhandled exception: {str(exc)}")

    # Return generic error to client
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal error occurred. Please try again later.",
            "error_code": "INTERNAL_SERVER_ERROR"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # Disable in production
    )
