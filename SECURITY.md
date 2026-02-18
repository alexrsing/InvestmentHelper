# Security Implementation Guide

This document explains the security features implemented in the Investment Helper API.

## 🔐 Security Features Implemented

### 1. JWT Authentication
- **Location**: [app/core/security.py](backend/app/core/security.py), [app/core/dependencies.py](backend/app/core/dependencies.py)
- **Features**:
  - Access tokens (30-minute expiry)
  - Refresh tokens (7-day expiry)
  - BCrypt password hashing
  - Token type validation
  - HTTPBearer scheme

**Usage in routes**:
```python
from app.core.dependencies import get_current_active_user

@router.get("/protected")
async def protected_route(current_user: dict = Depends(get_current_active_user)):
    # Only authenticated users can access
    return {"user": current_user}
```

### 2. Input Validation
- **Location**: [app/schemas/etf.py](backend/app/schemas/etf.py)
- **Features**:
  - Pydantic models for all inputs
  - Type checking
  - Length constraints
  - Regex patterns
  - Custom validators
  - Range validation

**Example**:
```python
ticker: str = Field(
    ...,
    min_length=1,
    max_length=10,
    pattern="^[A-Z]{1,10}$"
)
```

### 3. Security Headers
- **Location**: [app/core/middleware.py](backend/app/core/middleware.py)
- **Headers added**:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Strict-Transport-Security`
  - `Content-Security-Policy`
  - `Referrer-Policy`

### 4. Rate Limiting
- **Location**: [app/core/middleware.py](backend/app/core/middleware.py)
- **Default**: 60 requests per minute per IP
- **Features**:
  - Per-IP tracking
  - Sliding window
  - Rate limit headers in response
  - Configurable limits

### 5. CORS Protection
- **Location**: [app/main.py](backend/app/main.py)
- **Features**:
  - Explicit origin whitelist
  - Specific allowed methods
  - Specific allowed headers
  - Credentials support

### 6. Error Handling
- **Features**:
  - Never expose internal errors
  - Generic error messages to clients
  - Detailed logging server-side
  - Prevent information leakage

### 7. ORM Protection
- **DynamoDB/PynamoDB** prevents:
  - SQL injection (NoSQL database)
  - Parameterized queries
  - Type-safe operations

## 🚀 Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp backend/.env.example backend/.env
```

Edit `.env` and set:
```bash
# Generate a secure secret key
SECRET_KEY=$(openssl rand -hex 32)
```

### 3. Update Settings
- Configure CORS origins in `.env`
- Set appropriate rate limits
- Configure AWS credentials

## 📝 Implementing Security in Other Routers

Follow this pattern for all routers:

```python
from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_active_user
from app.schemas.your_schema import YourResponse, ErrorResponse

router = APIRouter(
    prefix="/your-endpoint",
    tags=["Your Tag"],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    }
)

@router.get(
    "/{id}",
    response_model=YourResponse,
    summary="Short description",
    description="Long description"
)
async def get_item(
    id: str = Query(..., min_length=1, max_length=50),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Detailed docstring
    """
    try:
        # Your logic here
        return result
    except Exception as e:
        # Log internally
        print(f"Error: {str(e)}")
        # Return generic error
        raise HTTPException(500, "Internal error")
```

## 🔑 Creating User Tokens (for testing)

```python
from app.core.security import create_access_token

token = create_access_token(
    data={
        "sub": "user123",
        "email": "user@example.com",
        "username": "testuser"
    }
)
```

## 🧪 Testing Authenticated Endpoints

```bash
# Get a token first (you'll need to implement a /login endpoint)
TOKEN="your-jwt-token"

# Make authenticated request
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v1/etfs/SPY
```

## ⚠️ Security Checklist

Before deploying to production:

- [ ] Change `SECRET_KEY` to a strong random value
- [ ] Set `reload=False` in uvicorn
- [ ] Configure proper CORS origins (no wildcards)
- [ ] Enable HTTPS/TLS
- [ ] Set up proper logging and monitoring
- [ ] Implement user authentication endpoint
- [ ] Add database user verification
- [ ] Consider Redis for rate limiting (not in-memory)
- [ ] Set up API key rotation
- [ ] Configure WAF rules
- [ ] Enable audit logging
- [ ] Implement input sanitization for file uploads
- [ ] Add request size limits
- [ ] Set up security scanning in CI/CD

## 🔒 Additional Security Recommendations

1. **Production Rate Limiting**: Use Redis instead of in-memory
2. **Database**: Implement row-level security
3. **Logging**: Use structured logging (JSON format)
4. **Monitoring**: Set up alerts for security events
5. **Backups**: Regular encrypted backups
6. **Dependencies**: Regular security updates (`pip-audit`)
7. **Secrets**: Use AWS Secrets Manager or similar
8. **TLS**: Use TLS 1.3 minimum

## 📚 Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)
