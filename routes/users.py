from fastapi import APIRouter, Depends, HTTPException, status,Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select
from auth.hash_password import HashPassword
from auth.jwt_handler import create_jwt_token
from database.connection import get_session
from models.users import User, UserSignIn, UserSignUp
from utils.oauth import oauth
from fastapi.responses import Response
from auth.authenticate import authenticate
from auth.authenticate import authenticate
import os
import logging


user_router = APIRouter(tags=["User"])

# users = {}

hash_password = HashPassword()
logger = logging.getLogger("uvicorn.error")

# 구글 OAuth 로그인
@user_router.get("/google/login")
async def google_login(request: Request):
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    return await oauth.google.authorize_redirect(request, redirect_uri)

# 구글 OAuth 인증 후 콜백
@user_router.get("/google/callback")
async def google_callback(request: Request, session=Depends(get_session)):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo")
    if not userinfo:
        userinfo = await oauth.google.parse_id_token(request, token)

    # 1. DB에서 사용자 조회 또는 생성
    statement = select(User).where(User.email == userinfo["email"])
    user = session.exec(statement).first()
    if not user:
        user = User(
            email=userinfo["email"],
            username=userinfo.get("name"),
            password="",  # 소셜 로그인은 패스워드 없음
            hobby="",
            role="user",
            diarys=[]
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    # 2. JWT 발급
    jwt_token = create_jwt_token(user.email, user.id)

    # 3. 프론트엔드로 리다이렉트 (JWT는 쿼리스트링으로만 전달, 실제 서비스는 쿠키 권장)
    redirect_url = f"http://localhost:5173/oauth?token={jwt_token}"
    return RedirectResponse(url=redirect_url)

# 회원 가입(등록)
@user_router.post("/signup", status_code=status.HTTP_201_CREATED)
async def sign_new_user(data: UserSignUp, session = Depends(get_session)) -> dict:
    statement = select(User).where(User.email == data.email)
    user = session.exec(statement).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail="동일한 사용자가 존재합니다.")
    
    new_user = User(
        email=data.email,
        password=hash_password.hash_password(data.password),
        username=data.username,
        role=data.role,
        diarys=[]
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    return {
        "message": "사용자 등록이 완료되었습니다.",
        "user": new_user
    }

# 로그인
@user_router.post("/signin")
async def sign_in(data: OAuth2PasswordRequestForm = Depends(), session = Depends(get_session)) -> dict:
    statement = select(User).where(User.email == data.username)
    user = session.exec(statement).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="사용자를 찾을 수 없습니다.")    

    # if user.password != data.password:
    if hash_password.verify_password(data.password, user.password) == False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="패스워드가 일치하지 않습니다.")
    
    return {
        "message": "로그인에 성공했습니다.",
        "username": user.username, 
        "access_token": create_jwt_token(user.email, user.id)
    }
    # return JSONResponse(    
    #     status_code=status.HTTP_200_OK,
    #     content={
    #         "message": "로그인에 성공했습니다.",
    #         "username": user.username, 
    #         "access_token": create_jwt_token(user.email, user.id)
    #     }
    # )