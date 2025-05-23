from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select
from auth.hash_password import HashPassword
from auth.jwt_handler import create_jwt_token
from database.connection import get_session
from models.users import User, UserSignIn, UserSignUp


user_router = APIRouter(tags=["User"])

# users = {}

hash_password = HashPassword()

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