from fastapi import Request, HTTPException, status
from jose import JWTError
from auth.jwt_handler import verify_jwt_token

async def authenticate(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="액세스 토큰이 쿠키에 없습니다.",
        )

    try:
        payload = verify_jwt_token(token)
        return payload["user_id"]
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
        )
