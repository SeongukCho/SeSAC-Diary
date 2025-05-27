# routes/oauth_router.py
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlmodel import select
from database.connection import get_session
from models.users import User
from auth.jwt_handler import create_jwt_token
from utils.oauth import oauth
import os

oauth_router = APIRouter(tags=["OAuth"])

@oauth_router.get("/google/login")
async def google_login(request: Request):
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@oauth_router.get("/google/callback")
async def google_callback(request: Request, session=Depends(get_session)):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo")
    if not userinfo:
        userinfo = await oauth.google.parse_id_token(request, token)

    # 사용자 생성 또는 조회
    statement = select(User).where(User.email == userinfo["email"])
    user = session.exec(statement).first()
    if not user:
        user = User(
            email=userinfo["email"],
            username=userinfo.get("name"),
            password="", # 소셜 로그인 유저는 비밀번호 없음음
            hobby="",
            role="user",
            diarys=[]
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    jwt_token = create_jwt_token(user.email, user.id)

    redirect_url = f"http://localhost:5173/list"
    response = RedirectResponse(redirect_url)
    response.set_cookie(
        key="access_token",
        value=jwt_token,
        httponly=True,
        max_age=3600,
        secure=False,
        samesite="lax"
    )
    return response
