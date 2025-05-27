from typing import TYPE_CHECKING, List, Optional
from datetime import datetime, timedelta
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

# from models.users import User
# from pydantic import BaseModel

if TYPE_CHECKING:
    from models.users import User

def korea_now():                                                        #캘린더
    return datetime.utcnow() + timedelta(hours=9)                       #캘린더


class Diary(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    title: str
    content: str
    image: str
    state: str
    emotion: Optional[str] = None
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    user: Optional["User"] = Relationship(back_populates="diarys")
    created_at: datetime = Field(default_factory=korea_now, nullable=False) # 현재 시간으로 기본값 설정

# 일기장 수정 시 전달되는 데이터 모델
class DiaryUpdate(SQLModel):
    title: Optional[str] = None
    content: Optional[str] = None
    image: Optional[str] = None
    state: Optional[str] = None
    
# 일기 목록 조회 시 반환할 새로운 Pydantic 모델
# Diary의 모든 필드를 상속하고, username 필드를 추가합니다.
class DiaryList(SQLModel):
    id: int
    title: str
    content: str
    image: str
    state: str
    emotion: Optional[str] = None
    created_at: datetime # datetime 타입으로 추가
    user_id: Optional[int] = None
    username: Optional[str] = None # 작성자 이름 필드