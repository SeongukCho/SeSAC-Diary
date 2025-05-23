from typing import TYPE_CHECKING, List, Optional
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

# from models.users import User
# from pydantic import BaseModel

if TYPE_CHECKING:
    from models.users import User

class Diary(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    title: str
    content: str
    image: str
    private: str
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    user: Optional["User"] = Relationship(back_populates="diarys")

# 일기장 수정 시 전달되는 데이터 모델
class DiaryUpdate(SQLModel):
    title: Optional[str] = None
    content: Optional[str] = None
    image: Optional[str] = None
    private: Optional[str] = None