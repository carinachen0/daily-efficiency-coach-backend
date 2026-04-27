from __future__ import annotations

from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, status
from passlib.context import CryptContext
from jose import jwt

from app.db import mongodb
from app.models import UserRegister, UserLogin, TokenResponse
from app.utils import now_utc

from app.auth_utils import get_current_user_id
from fastapi import Depends

import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        SECRET_KEY,
        algorithm=ALGORITHM
    )


@router.post("/register", response_model=TokenResponse)
async def register(payload: UserRegister):
    # Check if email already exists
    existing = await mongodb.collection("users").find_one({"email": payload.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Hash password and save user
    hashed = hash_password(payload.password)
    result = await mongodb.collection("users").insert_one({
        "email": payload.email,
        "passwordHash": hashed,
        "createdAt": now_utc(),
    })

    # Return token immediately so user is logged in after registering
    token = create_token(str(result.inserted_id))
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin):
    # Find user by email
    user = await mongodb.collection("users").find_one({"email": payload.email})
    if not user or not verify_password(payload.password, user["passwordHash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    token = create_token(str(user["_id"]))
    return {"access_token": token, "token_type": "bearer"}