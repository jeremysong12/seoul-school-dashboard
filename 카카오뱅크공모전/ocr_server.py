"""
주민등록증 OCR 서버
FastAPI로 이미지 수신 → CLOVA OCR → 이름/생년월일 추출
"""

import re
import base64
import uuid
import cv2
import numpy as np
import requests
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pathlib import Path

app = FastAPI()

# 브라우저에서 호출 가능하도록 CORS 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# CLOVA OCR 설정 (네이버 클라우드 콘솔에서 발급)
CLOVA_OCR_URL    = "https://q7ongqj4g1.apigw.ntruss.com/custom/v1/52904/cbe9d48faa418cf80d7ec99177ad93bae9c2f6da205d96c12f24a29bc9776662/general"  # 본인 Invoke URL로 교체
CLOVA_OCR_SECRET = "bUZ4a3hEUmZxZFJCZFluVHVCZFJWWnZuTW1OdFJTa0I="              # 본인 Secret Key로 교체


def preprocess_id_card(image_bytes: bytes) -> bytes:
    """
    실내 조명 + 바닥 촬영 환경 최적화 전처리
    그레이스케일 → CLAHE → 노이즈 제거 → 샤프닝 → JPEG 반환
    """
    img_arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)

    # 1. 그레이스케일
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. 빛반사(하이라이트) 억제 — 250 이상 픽셀을 230으로 클램프
    gray = np.clip(gray, 0, 230).astype(np.uint8)

    # 3. CLAHE — 그림자/불균일 조명 보정
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # 4. 가우시안 블러 — 미세 노이즈 제거
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # 5. 샤프닝 — 텍스트 경계 선명하게
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    gray = cv2.filter2D(gray, -1, kernel)

    _, encoded = cv2.imencode('.jpg', gray, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return encoded.tobytes()


def call_clova_ocr(image_bytes: bytes) -> list[str]:
    """이미지 바이트 → OCR 텍스트 목록"""
    img_b64 = base64.b64encode(image_bytes).decode()
    payload = {
        "images": [{"format": "jpg", "name": "id_card", "data": img_b64}],
        "requestId": str(uuid.uuid4()),
        "version": "V2",
        "timestamp": 0,
    }
    resp = requests.post(
        CLOVA_OCR_URL,
        headers={"X-OCR-SECRET": CLOVA_OCR_SECRET, "Content-Type": "application/json"},
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()

    result = resp.json()
    fields = result["images"][0].get("fields", [])
    texts = [f["inferText"] for f in fields]
    confidences = [round(f.get("inferConfidence", 0), 3) for f in fields]
    avg_conf = round(sum(confidences) / len(confidences), 3) if confidences else 0
    print("[인식 텍스트]", texts)
    print("[신뢰도]", confidences)
    print(f"[평균 신뢰도] {avg_conf}")
    return texts, confidences


def parse_id_card(texts: list[str], confidences: list[float]) -> dict:
    """OCR 텍스트 목록 → 이름/생년월일 추출 + 신뢰도 포함"""
    full = " ".join(texts)
    avg_conf = round(sum(confidences) / len(confidences), 3) if confidences else 0

    # 생년월일
    birthdate = None
    m = re.search(r'(\d{6})-\d', full)
    if m:
        yy, mm, dd = m.group(1)[:2], m.group(1)[2:4], m.group(1)[4:6]
        year = 1900 + int(yy) if int(yy) >= 10 else 2000 + int(yy)
        birthdate = f"{year}년 {int(mm)}월 {int(dd)}일"

    # 이름
    name = None
    for token in texts:
        token = token.strip()
        _BLACKLIST = {"주민등록증", "대한민국", "주민등록", "주민등", "발급일자", "주소", "도로명주소"}
        if re.fullmatch(r'[가-힣]{2,4}', token) and token not in _BLACKLIST and not token.startswith("주민"):
            name = token
            break

    return {"name": name, "birthdate": birthdate, "confidence": avg_conf}


@app.get("/", response_class=HTMLResponse)
async def serve_html():
    return Path("id_verify.html").read_text(encoding="utf-8")


@app.post("/ocr")
async def ocr_endpoint(file: UploadFile = File(...)):
    image_bytes             = await file.read()
    processed_bytes         = preprocess_id_card(image_bytes)
    texts, confidences      = call_clova_ocr(processed_bytes)
    result                  = parse_id_card(texts, confidences)
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
