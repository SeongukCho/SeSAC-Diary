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
import os
import logging


user_router = APIRouter(tags=["User"])

# users = {}

hash_password = HashPassword()
logger = logging.getLogger("uvicorn.error")


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
async def sign_in(
    response: Response,
    data: OAuth2PasswordRequestForm = Depends(),
    session = Depends(get_session)
                   ) -> dict:
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
    
    access_token = create_jwt_token(user.email, user.id)

    # 토큰을 HTTPOnly 쿠키에 저장
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,       # JS에서 접근 불가 (XSS 방지)
        secure=False,        # True면 HTTPS에서만 쿠키 전송됨 (배포시 True 권장)
        samesite="lax",      # 또는 'strict' (상황에 맞게)
        max_age=60*60*24,    # 1일 (단위: 초)
        path="/"
    )

    return {
        "message": "로그인에 성공했습니다.",
        "username": user.username
        # "access_token": access_token  # 이 줄은 이제 제거해도 됨
    }
    # return JSONResponse(    
    #     status_code=status.HTTP_200_OK,
    #     content={
    #         "message": "로그인에 성공했습니다.",
    #         "username": user.username, 
    #         "access_token": create_jwt_token(user.email, user.id)
    #     }
    # )

@user_router.get("/me")
async def get_login_status(user=Depends(authenticate)):
    return {
        "message": "로그인 상태입니다.",
        "user": user
    }


@user_router.post("/logout")
async def logout(response: Response):
    # access_token 쿠키를 삭제
    response.delete_cookie(
        key="access_token",
        path="/"
    )
    return {
        "message": "로그아웃 되었습니다."
    }