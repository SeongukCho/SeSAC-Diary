from contextlib import asynccontextmanager
from fastapi import FastAPI
from routes.users import user_router
from routes.diary import diary_router
from database.connection import conn

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 애플리케이션이 시작될 때 실행 코드
    print("애플리케이션 시작")
    conn()

    yield
    # 애플리케이션이 종료될 때 실행 코드
    print("애플리케이션 종료")


app = FastAPI(lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(user_router, prefix="/users")
app.include_router(diary_router, prefix="/diarys")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
