from time import time
from fastapi import HTTPException, status
from jose import jwt, JWTError, ExpiredSignatureError
from database.connection import Settings

settings = Settings()

# ✅ JWT 생성
def create_jwt_token(email: str, user_id: int) -> str:
    payload = {
        "user": email,
        "user_id": user_id,
        "iat": int(time()),
        "exp": int(time()) + 3600  # 1시간 유효
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return token

# ✅ JWT 검증
def verify_jwt_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="토큰이 만료되었습니다."
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다."
        )
