import json
from typing import List
from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, UploadFile, status, Body
from fastapi.responses import FileResponse
from sqlmodel import select, Session
from auth.authenticate import authenticate
from database.connection import get_session

from models.diarys import Diary, DiaryUpdate, DiaryList
from models.users import User

from utils.s3 import upload_file_to_s3,get_presigned_url,s3, BUCKET_NAME
from utils.clova import analyze_emotion_async


diary_router = APIRouter(tags=["Diary"])

# diarys = []

# pathlib 모듈의 Path 클래스를 FilePath 이름으로 사용
from pathlib import Path as FilePath
FILE_DIR = FilePath("C:/temp/uploads")
FILE_DIR.mkdir(exist_ok=True)

# presigned_url 생성  /presigned-url => get_presigned_url()
@diary_router.get("/presigned-url")
async def generate_presigned_url(file_type: str, user_id: int = Depends(authenticate)):
    try:
        url_data = get_presigned_url(file_type)
        return url_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 다운로드용 Presigned URL 생성
@diary_router.get("/download-url")
async def generate_download_url(file_key: str, user_id: int = Depends(authenticate)):
    try:
        url = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': file_key
            },
            ExpiresIn=3600  # 유효기간 1시간
        )
        return {"download_url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 일기장 전체 조회  /diarys/ => retrive_all_diarys()
@diary_router.get("/", response_model=List[DiaryList])
async def retrive_all_diarys(session: Session = Depends(get_session)) -> List[DiaryList]:
    statement = select(Diary).join(User, isouter=True)
    diary_results = session.exec(statement).unique().all()
    
    response_diarys = []
    for diary in diary_results:
        diary_data = diary.model_dump()
        if diary.user:
            diary_data["userName"] = diary.user.userName
        else:
            diary_data["userName"] = "알 수 없음"

        response_diarys.append(DiaryList(**diary_data))
    
    return response_diarys

# 일기장 상세 조회 /diarys/{diarys_id} => retrive_diary(diary_id)
@diary_router.get("/{diary_id}", response_model=DiaryList)
async def retirve_diary(diary_id: int, session: Session = Depends(get_session)) -> DiaryList:
    statement = select(Diary).where(Diary.id == diary_id).join(User, isouter=True)
    diary = session.exec(statement).first()

    if not diary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="일치하는 일기장을 찾을 수 없습니다."
        )
    
    diary_data = diary.model_dump()
    if diary.user:
        diary_data["userName"] = diary.user.userName
    else:
        diary_data["userName"] = "알 수 없음"
    
    # created_at은 이미 diary_data에 포함되어 있으므로 별도로 추가할 필요 없음
    return DiaryList(**diary_data)

# 일기장 등록       /diarys/ => create_diary()
@diary_router.post("/", status_code=status.HTTP_201_CREATED)
# async def create_diary(data = Form(...), user_id = Depends(authenticate), session = Depends(get_session)) -> dict:
async def create_diary(
        data: dict = Body(...),                   # Form으로 전달된 데이터
        user_id = Depends(authenticate),    # 인증된 사용자 ID
        session = Depends(get_session)      # DB 세션
    ) -> dict:

    # 전달된 데이터를 JSON 형식으로 변환 후 Diary 모델에 맞게 변환
    data = Diary(**data)
    
    # # 파일을 저장
    # file_path = FILE_DIR / image.filename
    # with open(file_path, "wb") as file:
    #     file.write(image.file.read())

    # # 파일 경로를 Diary 모델의 image 필드에 저장
    # data.image = str(file_path)

    data.user_id = user_id
    
    # 감정 분석 결과 추가
    emotion = await analyze_emotion_async(data.content)
    data.emotion = emotion
    
    session.add(data)
    session.commit()
    session.refresh(data)

    return {"message": "일기장 등록이 완료되었습니다."}

# 일기장 하나 삭제  /diarys/{diary_id} => delete_diary(diary_id)
@diary_router.delete("/{diary_id}")
async def delete_diary(diary_id: int, session = Depends(get_session)) -> dict:
    diary = session.get(Diary, diary_id)
    if diary:
        session.delete(diary)
        session.commit()
        return {"message": "일기장 삭제가 완료되었습니다."}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="일치하는 일기장를 찾을 수 없습니다."
    )

# 일기장 전체 삭제  /diarys/ => delete_all_diarys()
@diary_router.delete("/")
async def delete_all_diarys(session = Depends(get_session)) -> dict:
    statement = select(Diary)
    diarys = session.exec(statement)
    for diary in diarys:
        session.delete(diary)

    session.commit()

    return {"message": "일기장 전체 삭제가 완료되었습니다."}

# 일기장 수정       /diarys/{diary_id} => update_diary(diary_id)
@diary_router.put("/{diary_id}", response_model=Diary)
async def update_diary(data: DiaryUpdate,
                       diary_id:int = Path(...),
                       session = Depends(get_session)) -> Diary:
    diary = session.get(Diary, diary_id)
    if diary:
        # 요청 본문으로 전달된 데이터 중 값이 없는 부분을 제외
        # diary_data = data.dict(exclude_unset=True)
        diary_data = data.model_dump(exclude_unset=True)

        for key, value in diary_data.items():
            setattr(diary, key, value)

        if 'content' in diary_data:
            emotion = await analyze_emotion_async(diary.content)
            diary.emotion = emotion

        session.add(diary)
        session.commit()
        session.refresh(diary)

        return diary
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="일치하는 일기장를 찾을 수 없습니다."
    )

@diary_router.get("/download/{diary_id}")
async def download_file(diary_id: int, session = Depends(get_session)):
    diary = session.get(Diary, diary_id)
    if not diary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="일기장를 찾을 수 없습니다."
        )        
    
    file_path = diary.image
    if not FilePath(file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="파일을 찾을 수 없습니다."
        )
    
    return FileResponse(file_path, media_type="application/octet-stream", filename=FilePath(file_path).name)
