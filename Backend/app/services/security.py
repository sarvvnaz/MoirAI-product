# security.py
import bcrypt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import HTTPException, status, Depends
from jose import jwt, JWTError
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.database.db_setup import get_db
from app.database.models import User
from app.config import SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_DELTA  # your constants

bearer_scheme = HTTPBearer(auto_error=True)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or ACCESS_TOKEN_EXPIRE_DELTA)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolves the authenticated user ON THE REQUEST'S OWN DB SESSION.

    Must share the route's session (FastAPI caches the get_db dependency per
    request): with a private short-lived session the returned User is
    DETACHED, and route mutations like `current_user.gender = ...` are
    silently dropped at commit.
    """
    token = creds.credentials
    payload = decode_token(token)
    code = payload.get("sub")
    if not code:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    user = db.query(User).filter(User.participant_code == code).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user