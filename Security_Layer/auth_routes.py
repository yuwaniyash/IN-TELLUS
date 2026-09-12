"""
Auth endpoints: register a new company + first admin user, and login.
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from Security_Layer.auth import (
    create_access_token, verify_password, get_user_by_email,
    create_user, get_current_user
)
from Security_Layer.file_intake import get_connection

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterCompanyRequest(BaseModel):
    company_name: str
    full_name: str
    email: EmailStr
    password: str


@router.post("/register")
def register_company(payload: RegisterCompanyRequest):
    if get_user_by_email(payload.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO companies (company_name) VALUES (%s) RETURNING company_id;",
            (payload.company_name,)
        )
        company_id = cur.fetchone()[0]
        conn.commit()
    finally:
        cur.close()
        conn.close()

    user_id = create_user(
        company_id=company_id,
        full_name=payload.full_name,
        email=payload.email,
        password=payload.password,
        role="admin",
    )

    token = create_access_token(user_id=user_id, company_id=company_id, role="admin")
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(
        user_id=user["user_id"], company_id=user["company_id"], role=user["role"]
    )
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def read_current_user(current_user: dict = Depends(get_current_user)):
    return current_user