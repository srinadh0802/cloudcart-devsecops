"""JWT authentication and independent service authentication."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import jwt
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from .config import JWT_SECRET, INTERNAL_KEY

bearer = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    hashed = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return salt.hex() + ':' + hashed.hex()

def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = (bytes.fromhex(v) for v in stored.split(':'))
        got = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(got, expected)
    except (ValueError, TypeError):
        return False

def token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': str(user_id), 'role': role, 'iat': now, 'exp': now + timedelta(hours=8)}, JWT_SECRET, algorithm='HS256')

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if not credentials:
        raise HTTPException(401, 'Login required')
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=['HS256'])
        return {'id': int(payload['sub']), 'role': payload['role']}
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, 'Invalid or expired session')

def require_owner(user: dict = Depends(current_user)) -> dict:
    if user['role'] != 'owner':
        raise HTTPException(403, 'Store-owner account required')
    return user

def internal_auth(x_internal_key: str | None = Header(default=None)) -> None:
    if not x_internal_key or not hmac.compare_digest(x_internal_key, INTERNAL_KEY):
        raise HTTPException(403, 'Internal service credential required')
