import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

logger = logging.getLogger(__name__)

# Security configuration
SECRET_KEY = "your-secret-key"  # In production, use environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()

class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests = {}
        self.rate_limit = requests_per_minute

    def is_allowed(self, client_id: str) -> bool:
        current_time = time.time()
        if client_id in self.requests:
            requests = [req for req in self.requests[client_id] if req > current_time - 60]
            self.requests[client_id] = requests
            if len(requests) >= self.rate_limit:
                return False
        else:
            requests = []
        self.requests[client_id] = requests + [current_time]
        return True

rate_limiter = RateLimiter()

async def rate_limit_middleware(request: Request, call_next):
    client_id = request.client.host
    if not rate_limiter.is_allowed(client_id):
        raise HTTPException(status_code=429, detail="Too many requests")
    response = await call_next(request)
    return response

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def verify_token(credentials: HTTPAuthorizationCredentials = None):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
