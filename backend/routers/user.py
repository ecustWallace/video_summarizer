from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text
from database import engine  # 确保你有 database.py 提供 engine

router = APIRouter()

class UserCreateRequest(BaseModel):
    email: str

@router.post("/api/users/create")
async def create_user(user: UserCreateRequest):
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO users (email)
                VALUES (:email)
                ON CONFLICT (email) DO NOTHING
            """),
            {"email": user.email}
        )
        conn.commit()
    return {"message": "User creation triggered", "email": user.email}

