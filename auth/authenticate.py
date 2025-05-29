from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from auth.jwt_handler import verify_jwt_token

from sqlmodel import Session, select
from database.connection import get_session
from models.users import User

# 요청이 들어올 때 Authorization 헤더의 토큰 값을 추출
# tokenUrl : 클라이언트가 토큰을 요청할 때 사용할 엔드포인트로, 
#            FastAPI의 자동 문서화에 사용되는 정보
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/signin")

async def authenticate(token: str = Depends(oauth2_scheme)):
    if not token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="액세스 토큰이 누락되었습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = verify_jwt_token(token)
    return payload["user_id"]

async def get_current_user_role(
    user_id: int = Depends(authenticate), # authenticate 함수가 반환하는 user_id에 의존
    session: Session = Depends(get_session)
) -> str:
    """
    인증된 사용자의 ID를 기반으로 데이터베이스에서 사용자 역할을 조회하여 반환합니다.
    """
    user = session.exec(select(User).where(User.id == user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")
    return user.role # 사용자의 role 반환