from typing import TYPE_CHECKING, List, Optional
from pydantic import BaseModel, EmailStr
from sqlmodel import Field, Relationship, SQLModel
# from models.diarys import Diary

if TYPE_CHECKING:
    from models.diarys import Diary

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: EmailStr
    password: str
    userName: str
    role: str
    diarys: Optional[List["Diary"]] = Relationship(back_populates="user")

class UserSignIn(SQLModel):
    email: EmailStr
    password: str

class UserSignUp(SQLModel):
    email: EmailStr
    password: str
    userName: str
    role: str
