from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from auth.jwt_handler import verify_jwt_token

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