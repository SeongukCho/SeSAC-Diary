import httpx
import uuid
import os
from dotenv import load_dotenv

load_dotenv()  # .env 파일 읽어서 환경 변수 설정

CLOVA_API_KEY = os.getenv("CLOVA_API_KEY")

async def analyze_emotion_async(content: str) -> str:
    CLOVA_API_URL = "https://clovastudio.stream.ntruss.com/testapp/v3/chat-completions/HCX-005"
    headers = {
        "Authorization": CLOVA_API_KEY,  # .env에서 불러온 값 사용
        "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4()),
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json"
    }

    prompt = [
        {
            "role": "system",
            "content": (
            "- 이것은 문장 감정 분석기 입니다.\n"
            "- 감정만 답하고 부연 설명은 하지 마세요.\n"
            "- 감정은 다음 중 하나로만 답하세요: 긍정, 부정, 중립, 슬픔, 놀람\n"
            "문장: 기분 진짜 좋다\n감정: 긍정\n"
            "###\n"
            "문장: 아오 진짜 짜증나게 하네\n감정: 부정\n"
            "###\n"
            "문장: 이걸로 보내드릴게요\n감정: 중립\n"
            "###\n"
            "문장: 너무 슬퍼서 눈물이 난다\n감정: 슬픔\n"
            "###\n"
            "문장: 헐 진짜 이게 가능해?\n감정: 놀람\n"
            "###"
        )
        },
        {
            "role": "user",
            "content": f"문장: {content}\n감정:"
        }
    ]

    payload = {
        "messages": prompt,
        "topP": 0.6,
        "topK": 0,
        "maxTokens": 20,
        "temperature": 0.1,
        "repetitionPenalty": 1.1,
        "stop": ["###"],
        "includeAiFilters": True,
        "seed": 0
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(CLOVA_API_URL, headers=headers, json=payload)
        result = response.json()
        # 응답 예시 구조에 맞게 파싱
        emotion_text = result["result"]["message"]["content"].strip()
        return emotion_text
