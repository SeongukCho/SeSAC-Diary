import json
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, UploadFile, status, Body, Query
# from fastapi.responses import FileResponse # S3 사용으로 FileResponse는 주석 처리 또는 제거
from sqlmodel import select, Session
from pydantic import BaseModel # DiaryCreate 모델을 위해 추가
from datetime import datetime, date # date 타입 사용을 위해 추가

from auth.authenticate import authenticate, get_current_user_role
from database.connection import get_session

from models.diarys import Diary, DiaryUpdate, DiaryList # DiaryList 모델이 username, user_id, state 필드를 포함해야 함
from models.users import User
from utils.s3 import upload_file_to_s3, get_presigned_url, s3, BUCKET_NAME
from utils.clova import analyze_emotion_async

# pathlib 모듈의 Path 클래스를 FilePath 이름으로 사용
from pathlib import Path as FilePath
# FILE_DIR = FilePath("C:/temp/uploads") # S3를 주로 사용하므로 로컬 파일 저장 경로는 필요 없을 수 있음
# FILE_DIR.mkdir(exist_ok=True) # 위와 동일

diary_router = APIRouter(tags=["Diary"])

# --- Pydantic 모델 정의 (필요시 models/diarys.py 로 이동) ---
class DiaryCreate(BaseModel):
    title: str
    content: str
    state: bool = True
    image: Optional[str] = None # S3에 업로드된 경우 파일 키(경로) 또는 URL
    diary_date: date # YYYY-MM-DD 형식으로 받을 예정

# --- API 엔드포인트 ---

@diary_router.get("/presigned-url")
async def generate_presigned_url_for_upload(file_type: str, user_id: int = Depends(authenticate)):
    try:
        url_data = get_presigned_url(file_type) # 이 함수는 S3 업로드용 URL과 파일 키(key)를 반환해야 함
        return url_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Presigned URL 생성 실패: {str(e)}")

@diary_router.get("/download-url")
async def generate_presigned_url_for_download(file_key: str, user_id: int = Depends(authenticate)):
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
        raise HTTPException(status_code=500, detail=f"다운로드 URL 생성 실패: {str(e)}")

@diary_router.get("/check-duplicate", response_model=dict)
async def check_duplicate_diary_exists(
    diary_date: date = Query(..., description="YYYY-MM-DD 형식의 날짜"),
    user_id: int = Depends(authenticate),
    session: Session = Depends(get_session)
):
    statement = select(Diary).where(
        Diary.user_id == user_id,
        Diary.diary_date == diary_date
    )
    existing_diary = session.exec(statement).first()
    if existing_diary:
        return {"exists": True}
    return {"exists": False}

@diary_router.get("/", response_model=List[DiaryList])
async def retrieve_all_diaries(
    session: Session = Depends(get_session),
    state: Optional[bool] = None,
    current_user_id: Optional[int] = Depends(authenticate), # authenticate가 None을 반환할 수 있도록 authenticate 수정 필요 또는 별도 의존성 사용
    user_role: Optional[str] = Depends(get_current_user_role)
):
    statement = select(Diary).join(User, isouter=True).order_by(Diary.created_at.desc()) # User 정보를 함께 가져오기 위함
    
    is_admin = (user_role == "admin")

    if state is not None:
        statement = statement.where(Diary.state == state)
        if not state: # 비공개 일기 (state=False)를 요청한 경우
            if is_admin:
                # 관리자는 모든 비공개 일기를 볼 수 있습니다. (추가 필터링 없음)
                pass
            elif current_user_id:
                # 일반 사용자는 자신의 비공개 일기만 볼 수 있습니다.
                statement = statement.where(Diary.user_id == current_user_id)
            else:
                # 로그인하지 않은 경우 비공개 일기는 볼 수 없습니다.
                return []
        # state=True (공개 일기)인 경우, 누구나 볼 수 있으므로 추가 필터링이 필요 없습니다.
    else:
        # state 파라미터가 없을 때 (전체 목록, 기본 필터링)
        if is_admin:
            # 관리자는 모든 일기 (공개/비공개 모두)를 볼 수 있습니다.
            pass
        elif current_user_id:
            # 로그인한 일반 사용자: 자신의 모든 일기 + 다른 사람의 공개 일기
            statement = statement.where(
                (Diary.user_id == current_user_id) | (Diary.state == True)
            )
        else:
            # 로그인하지 않은 사용자: 모든 공개 일기만 볼 수 있습니다.
            statement = statement.where(Diary.state == True)

    # # state 파라미터가 없을 때 (전체 목록, 기본 필터링)
    # else:
    #     if current_user_id:
    #         # 로그인한 사용자: 자신의 모든 일기 + 다른 사람의 공개 일기
    #         statement = statement.where(
    #             (Diary.user_id == current_user_id) | (Diary.state == True)
    #         )
    #     else:
    #         # 로그인하지 않은 사용자: 모든 공개 일기
    #         statement = statement.where(Diary.state == True)
    
    diary_results = session.exec(statement).unique().all()
    
    response_diaries = []
    for diary in diary_results:
        diary_data = diary.model_dump() # Diary 모델의 데이터
        # DiaryList에 필요한 추가 정보 (username, user_id, state)
        diary_data["username"] = diary.user.username if diary.user else "알 수 없음"
        diary_data["user_id"] = diary.user_id
        # diary_data["state"] = diary.state # 이미 model_dump에 포함되어 있을 것임 (Diary 모델 필드라면)
        
        # DiaryList 모델에 맞게 response_diaries에 추가
        # 이 부분은 DiaryList 모델의 정의에 따라 조정될 수 있습니다.
        # 예를 들어, DiaryList가 Diary 모델을 상속하고 username만 추가한다면:
        # response_diaries.append(DiaryList(**diary_data, username=diary_data["username"]))
        # 현재 코드에서는 DiaryList가 모든 필드를 직접 받는다고 가정합니다.
        response_diaries.append(DiaryList(**diary_data))
        
    return response_diaries

@diary_router.get("/{diary_id}", response_model=DiaryList)
async def retrieve_diary(
    diary_id: int,
    session: Session = Depends(get_session),
    current_user_id: Optional[int] = Depends(authenticate), # 위와 동일하게 Optional 처리
    user_role: Optional[str] = Depends(get_current_user_role)
):
    # join(User)를 사용하여 작성자 정보도 함께 로드
    statement = select(Diary).where(Diary.id == diary_id).join(User, isouter=True)
    diary = session.exec(statement).first()

    if not diary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="일치하는 일기를 찾을 수 없습니다."
        )
        
    is_admin = (user_role == "admin")
    
    if not diary.state: # 비공개 일기인 경우
        if not is_admin and (not current_user_id or diary.user_id != current_user_id):
            # 관리자가 아니고, 로그인하지 않았거나 일기 작성자가 아닌 경우 접근 금지
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이 일기에 접근할 권한이 없습니다."
            )
            
    diary_data = diary.model_dump()
    diary_data["username"] = diary.user.username if diary.user else "알 수 없음"
    # user_id, state는 diary.model_dump()에 이미 포함되어 있다고 가정 (Diary 모델의 필드)
    
    return DiaryList(**diary_data)

@diary_router.post("/", status_code=status.HTTP_201_CREATED, response_model=Diary) # 반환 타입을 Diary로 명시 (또는 DiaryList)
async def create_diary(
    payload: DiaryCreate, # Pydantic 모델로 요청 본문 받기
    user_id: int = Depends(authenticate),
    session: Session = Depends(get_session)
):
    # 중복 체크: 같은 날짜에 같은 사용자가 이미 쓴 일기 있는지 확인
    statement = select(Diary).where(
        Diary.user_id == user_id,
        Diary.diary_date == payload.diary_date
    )
    existing_diary = session.exec(statement).first()

    if existing_diary:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, # 400 대신 409 Conflict가 더 적절할 수 있음
            detail="같은 날짜에 이미 작성한 일기가 있습니다."
        )

    # Diary 객체 생성 준비
    diary_data = payload.model_dump()
    diary_data["user_id"] = user_id
    
    # 감정 분석 (content가 비어있지 않을 때만 수행)
    if payload.content:
        try:
            emotion = await analyze_emotion_async(payload.content)
            diary_data["emotion"] = emotion
        except Exception as e:
            # 감정 분석 실패 시 로깅하고 계속 진행하거나, 오류 처리 (여기서는 일단 None으로 둘 수 있음)
            print(f"감정 분석 실패: {e}")
            diary_data["emotion"] = None # 또는 기본값
    else:
        diary_data["emotion"] = None


    new_diary = Diary(**diary_data)
    
    session.add(new_diary)
    session.commit()
    session.refresh(new_diary)

    return new_diary # 생성된 Diary 객체 반환

@diary_router.put("/{diary_id}", response_model=Diary)
async def update_diary_entry( # 함수 이름 변경 (PEP8, CRUD 느낌 살려서)
    diary_id: int,
    payload: DiaryUpdate, # DiaryUpdate 모델은 title, content, state 등 변경 가능한 필드만 포함해야 함
    user_id: int = Depends(authenticate),
    session: Session = Depends(get_session),
    user_role: str = Depends(get_current_user_role)
):
    diary = session.get(Diary, diary_id)
    if not diary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="일치하는 일기를 찾을 수 없습니다."
        )

    if user_role != "admin" and diary.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 일기를 수정할 권한이 없습니다."
        )

    diary_update_data = payload.model_dump(exclude_unset=True) # 값이 제공된 필드만 업데이트

    for key, value in diary_update_data.items():
        setattr(diary, key, value)

    # 내용이 수정되었다면 감정 재분석
    if 'content' in diary_update_data and diary.content:
        try:
            emotion = await analyze_emotion_async(diary.content)
            diary.emotion = emotion
        except Exception as e:
            print(f"감정 재분석 실패: {e}")
            # 오류 발생 시 이전 감정 유지 또는 기본값 설정
            
    # diary_date가 변경되는 경우는 중복 체크를 다시 해야 할 수도 있으나,
    # DiaryUpdate 모델에 diary_date를 포함하지 않거나, 포함 시 별도 로직 필요

    session.add(diary)
    session.commit()
    session.refresh(diary)
    return diary

@diary_router.delete("/{diary_id}", status_code=status.HTTP_204_NO_CONTENT) # 성공 시 204 No Content 반환
async def delete_diary_entry( # 함수 이름 변경
    diary_id: int,
    user_id: int = Depends(authenticate),
    session: Session = Depends(get_session),
    user_role: str = Depends(get_current_user_role)
):
    diary = session.get(Diary, diary_id)
    if not diary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="일치하는 일기를 찾을 수 없습니다."
        )
    
    if user_role != "admin" and diary.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이 일기를 삭제할 권한이 없습니다."
        )
        
    session.delete(diary)
    session.commit()
    # 204 No Content는 본문을 반환하지 않으므로 return 문 없음
    # return {"message": "일기장 삭제가 완료되었습니다."} # 대신 status_code=204 사용

@diary_router.delete("/", summary="모든 일기 삭제 (주의 요망!)")
async def delete_all_user_diaries( # 함수 이름 구체화, 현재는 특정 사용자 일기만 삭제하도록 변경
    user_id: int = Depends(authenticate), # 관리자 기능이 아니라면 해당 사용자 일기만 삭제
    session: Session = Depends(get_session)
):
    # 주의: 이 작업은 해당 사용자의 모든 일기를 삭제합니다.
    # 만약 '모든 사용자'의 모든 일기를 삭제하는 기능이라면 별도의 관리자 권한 확인이 필요합니다.
    
    statement = select(Diary).where(Diary.user_id == user_id)
    diaries_to_delete = session.exec(statement).all()
    
    if not diaries_to_delete:
        # raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="삭제할 일기가 없습니다.")
        return {"message": "삭제할 일기가 없습니다."} # 또는 204

    for diary in diaries_to_delete:
        session.delete(diary)
    
    session.commit()
    return {"message": f"사용자 ID {user_id}의 일기 {len(diaries_to_delete)}개가 삭제되었습니다."}


# S3 연동을 가정하고, 로컬 파일 직접 다운로드 대신 Presigned URL 생성 방식으로 변경
@diary_router.get("/download/s3/{diary_id}", summary="S3 이미지 다운로드 URL 생성")
async def get_s3_image_download_url(
    diary_id: int,
    user_id: int = Depends(authenticate), # 접근 권한 확인용
    session: Session = Depends(get_session)
):
    diary = session.get(Diary, diary_id)
    if not diary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="일기를 찾을 수 없습니다.")

    # 비공개 일기인 경우, 작성자만 이미지 다운로드 URL을 받을 수 있도록 함
    if not diary.state and diary.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="이미지 접근 권한이 없습니다.")

    if not diary.image: # Diary.image 필드에 S3 파일 키(key)가 저장되어 있다고 가정
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="이미지 파일 키를 찾을 수 없습니다.")

    try:
        url = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': diary.image},
            ExpiresIn=3600  # 1시간 동안 유효한 URL
        )
        return {"download_url": url, "file_key": diary.image}
    except Exception as e:
        # 실제 운영 환경에서는 에러 로깅 권장
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"이미지 다운로드 URL 생성 중 오류 발생: {str(e)}")


@diary_router.get("/list/search", response_model=List[DiaryList])
async def search_diarys(
        session: Session = Depends(get_session),
        search: Optional[str] = None,  # 검색어
) -> List[DiaryList]:

    if not search:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="검색어를 입력해주세요.")
    
    statement = select(Diary).join(User, isouter=True)

    # 공개된 글만 조회 (state=1)
    statement = statement.where(Diary.state == 1)  # 공개된 글만

    # 검색어가 있을 경우 제목을 필터링
    if search:
        statement = statement.where(Diary.title.ilike(f"%{search}%"))

    diary_results = session.exec(statement).unique().all()

    response_diarys = []
    for diary in diary_results:
        diary_data = diary.model_dump()
        diary_data["username"] = diary.user.username if diary.user else "알 수 없음"
        diary_data["user_id"] = diary.user_id
        diary_data["state"] = diary.state
        response_diarys.append(DiaryList(**diary_data))

    return response_diarys

