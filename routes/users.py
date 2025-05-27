from fastapi import APIRouter, Depends, HTTPException, status,Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select
from auth.hash_password import HashPassword
from auth.jwt_handler import create_jwt_token
from database.connection import get_session
from models.users import User, UserSignIn, UserSignUp
from utils.oauth import oauth
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

    # 3. 쿠키에 JWT 저장 후 프론트로 리다이렉트 (쿼리스트링X)
    redirect_url = "http://localhost:5173/oauth"
    response = RedirectResponse(url=redirect_url)
    response.set_cookie(
        key="access_token",
        value=jwt_token,
        httponly=True,      # JS에서 접근 불가, 보안 ↑
        secure=False,       # HTTPS 환경에선 True
        samesite="lax",     # 필요에 따라 "strict" 등 변경
        max_age=60*60*24,   # 1일, 필요시 조정
        path="/"
    )
    return response

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
        hobby=data.hobby,
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
    
    jwt_token = create_jwt_token(user.email, user.id)
    response = JSONResponse(content={
        "message": "로그인에 성공했습니다.",
        "username": user.username
    })
    response.set_cookie(
        key="access_token",
        value=jwt_token,
        httponly=True,      # JS에서 접근 못하게 (보안 ↑)
        secure=False,       # 배포 환경에선 True로 변경!
        samesite="lax",     # 또는 "strict", 필요에 따라
        max_age=60*60*24,   # 1일 (초 단위)
        path="/"
    )
    return response
    # return JSONResponse(    
    #     status_code=status.HTTP_200_OK,
    #     content={
    #         "message": "로그인에 성공했습니다.",
    #         "username": user.username, 
    #         "access_token": create_jwt_token(user.email, user.id)
    #     }
    # )



@user_router.get("/me")
async def get_current_user(user_id: int = Depends(authenticate)):
    return {"user_id": user_id}

@user_router.post("/logout")
async def logout():
    response = JSONResponse(content={"message": "로그아웃 완료"})
    response.delete_cookie(
        key="access_token",
        path="/",          # ✅ 쿠키 설정했던 path와 동일하게!
        samesite="lax"     # 쿠키 설정과 동일해야 확실히 삭제됨
    )
    return response