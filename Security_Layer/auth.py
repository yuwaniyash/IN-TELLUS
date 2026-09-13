"""
Authentication layer.

Handles: password hashing, JWT creation/verification, and the FastAPI
dependencies that protect endpoints and resolve WHICH company a request
belongs to — this is what makes multi-tenant data isolation (sites,
accounts, extracted records) actually enforceable instead of just a
schema convention nobody checks.

Design decisions:
- Passwords are hashed with bcrypt (via passlib), never stored or logged
  in plain text.
- JWTs carry user_id, company_id, and role in the payload — company_id is
  what every company-scoped query (resolve_site, /accounts, /sites) should
  pull from the token, NEVER from a request body/query param, since a
  client could otherwise just claim to be a different company.
- Tokens are stateless (no server-side session table) — simplest option
  for a project this size. Logout is client-side (discard the token);
  there's no server-side revocation list. Fine for now, worth revisiting
  if you ever need to force-expire a compromised token before it expires
  naturally.
"""
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from Security_Layer.file_intake import get_connection

load_dotenv()

SECRET_KEY = os.environ["JWT_SECRET_KEY"]
ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "1440"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# tokenUrl just tells Swagger UI where the login form posts to — doesn't
# affect actual behavior, just makes /docs show a working "Authorize" button.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


# ---------- password helpers ----------

def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ---------- token helpers ----------

def create_access_token(user_id: int, company_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "company_id": company_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------- DB lookups ----------

def get_user_by_email(email: str) -> dict | None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT user_id, company_id, full_name, email, password_hash, role
               FROM users WHERE email = %s;""",
            (email,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "user_id": row[0], "company_id": row[1], "full_name": row[2],
            "email": row[3], "password_hash": row[4], "role": row[5],
        }
    finally:
        cur.close()
        conn.close()


def create_user(company_id: int, full_name: str, email: str, password: str, role: str = "member") -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO users (company_id, full_name, email, password_hash, role)
               VALUES (%s, %s, %s, %s, %s) RETURNING user_id;""",
            (company_id, full_name, email, hash_password(password), role)
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        return user_id
    finally:
        cur.close()
        conn.close()


# ---------- FastAPI dependencies ----------
# Use these in any endpoint that needs to know who's calling, or which
# company's data to scope a query to.

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    payload = decode_access_token(token)
    return {
        "user_id": int(payload["sub"]),
        "company_id": payload["company_id"],
        "role": payload["role"],
    }


def get_current_company_id(current_user: dict = Depends(get_current_user)) -> int:
    """The dependency most endpoints actually want — just the company_id
    to scope queries by, without needing the full user dict."""
    return current_user["company_id"]


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Use on endpoints only a company admin should call (e.g. adding
    other users, deleting sites)."""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user