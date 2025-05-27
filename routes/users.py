from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select
from database.connection import get_session
from models.users import User, UserSignUp
from auth.hash_password import HashPassword
from auth.jwt_handler import create_jwt_token
from auth.authenticate import authenticate

router = APIRouter(prefix="/users", tags=["User"])
hash_password = HashPassword()

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def sign_up(data: UserSignUp, session=Depends(get_session)):
    statement = select(User).where(User.email == data.email)
    if session.exec(statement).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 이메일입니다."
        )
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
    return {"message": "사용자 등록이 완료되었습니다.", "user": new_user}

@router.post("/signin", status_code=status.HTTP_200_OK)
async def sign_in(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session=Depends(get_session)
):
    statement = select(User).where(User.email == form_data.username)
    user = session.exec(statement).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    if not hash_password.verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="패스워드가 일치하지 않습니다."
        )
    access_token = create_jwt_token(user.email, user.id)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 24,
        path="/"
    )
    return {"message": "로그인에 성공했습니다.", "username": user.username}

@router.get("/me", status_code=status.HTTP_200_OK)
async def get_login_status(user: User = Depends(authenticate)):
    return {"message": "로그인 상태입니다.", "user": user}

@router.get("/checkemail/{email}", status_code=status.HTTP_200_OK)
async def check_email(email: str, session=Depends(get_session)):
    statement = select(User).where(User.email == email)
    if session.exec(statement).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 등록된 이메일입니다."
        )
    return {"message": "사용 가능한 이메일입니다."}

@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(response: Response):
    response.delete_cookie(key="access_token", path="/")
    return {"message": "로그아웃 되었습니다."}
