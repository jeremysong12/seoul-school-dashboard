import sounddevice as sd
import soundfile as sf
import requests
import re
import subprocess
import tempfile
import asyncio
import edge_tts

# ─── API 키 설정 ───────────────────────────────────────────
CLOVA_CLIENT_ID     = "ehvh6p7xya"
CLOVA_CLIENT_SECRET = "q9V87J3by6dn1emJ5Y2Yn3PiDA5BfMuanyzDK2lS"

CLOVA_STT_URL = "https://naveropenapi.apigw.ntruss.com/recog/v1/stt?lang=Kor"
SAMPLE_RATE   = 16000
CHANNELS      = 1
RECORD_SECS   = 6

# ─── 슬롯 설정 ────────────────────────────────────────────
SLOT_DEFINITIONS = {
    "이름": {
        "question":        "성함을 말씀해 주세요.",
        "example":         "홍길동",
        "validation_hint": "한국어 이름 2~4글자",
    },
    "생년월일": {
        "question":        "생년월일을 연도, 월, 일 순서로 말씀해 주세요.",
        "example":         "1955년 3월 15일",
        "validation_hint": "YYYY년 MM월 DD일 형식",
    },
}

KOREAN_DIGITS = {
    "공": "0", "일": "1", "이": "2", "삼": "3", "사": "4",
    "오": "5", "육": "6", "칠": "7", "팔": "8", "구": "9",
}


# ══════════════════════════════════════════════════════════
# 0. TTS (Edge TTS — ko-KR-SunHiNeural)
# ══════════════════════════════════════════════════════════

TTS_VOICE = "ko-KR-SunHiNeural"  # 여성 은행원 톤
TTS_RATE  = "+5%"                # 또렷하고 차분하게
TTS_PITCH = "+0Hz"               # 자연스러운 피치

_TTS_TMP = tempfile.gettempdir() + "/kakao_tts.mp3"


async def _speak_async(text: str, rate: str = TTS_RATE) -> None:
    tts = edge_tts.Communicate(text, voice=TTS_VOICE, rate=rate, pitch=TTS_PITCH)
    await tts.save(_TTS_TMP)


def speak(text: str, rate: str = TTS_RATE) -> None:
    """Edge TTS(SunHiNeural)로 음성 출력. 실패 시 텍스트만 출력."""
    print(f"🔊 {text}")
    try:
        asyncio.run(_speak_async(text, rate=rate))
        subprocess.run(["afplay", _TTS_TMP], check=True)
    except Exception as e:
        print(f"[TTS 오류] {e}")


# ══════════════════════════════════════════════════════════
# 1. 오디오 녹음
# ══════════════════════════════════════════════════════════

def record_audio(duration=RECORD_SECS, filename="input.wav") -> str:
    speak("지금 말씀해 주세요.")
    print(f"🎤 녹음 중... ({duration}초)")
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
    )
    sd.wait()
    sf.write(filename, audio, SAMPLE_RATE)
    print("✅ 녹음 완료")
    return filename


# ══════════════════════════════════════════════════════════
# 2. Clova Speech STT
# ══════════════════════════════════════════════════════════

def call_clova_stt(audio_file_path: str, min_len: int = 2) -> str | None:
    headers = {
        "X-NCP-APIGW-API-KEY-ID": CLOVA_CLIENT_ID,
        "X-NCP-APIGW-API-KEY":    CLOVA_CLIENT_SECRET,
        "Content-Type":           "application/octet-stream",
    }
    try:
        with open(audio_file_path, "rb") as f:
            response = requests.post(CLOVA_STT_URL, headers=headers, data=f.read(), timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"[STT 오류] {e}")
        return None

    if response.status_code == 200:
        text = response.json().get("text", "").strip()
        print(f"[STT 원문] \"{text}\"")
        return text if len(text) >= min_len else None
    else:
        print(f"[STT 오류] {response.status_code}: {response.text}")
        return None


# ══════════════════════════════════════════════════════════
# 3. STT 실패 핸들링
# ══════════════════════════════════════════════════════════

def trigger_helpme_bridge():
    """헬프미 브릿지 스텁 — 실제 구현 시 WebRTC 호출로 교체"""
    print("[헬프미] 상담원 화상 연결 요청 전송됨 (미구현)")


def stt_with_retry(prompt_message: str, max_attempts: int = 3, duration: int = RECORD_SECS, min_len: int = 2) -> dict:
    """
    STT 호출 + 실패 핸들링
    1회 실패 → 재시도
    2회 실패 → 키보드 입력 제안
    3회 실패 → 헬프미 브릿지

    Returns: {"success": bool, "text": str|None, "method": "voice"|"keyboard"|"helpme"}
    """
    speak(prompt_message)
    fail_count = 0

    while fail_count < max_attempts:
        audio = record_audio(duration=duration)
        text  = call_clova_stt(audio, min_len=min_len)

        if text:
            print(f'🗣 인식됨: "{text}"')
            return {"success": True, "text": text, "method": "voice"}

        fail_count += 1
        print(f"[실패 {fail_count}회]")

        if fail_count == 1:
            speak("죄송해요, 잘 못 들었어요. 다시 한 번 말씀해 주세요.")

        elif fail_count == 2:
            speak("음성 인식이 어렵네요. 키보드로 직접 입력해 주시겠어요?")
            keyboard_input = input("직접 입력 (건너뛰려면 Enter): ").strip()
            if keyboard_input:
                return {"success": True, "text": keyboard_input, "method": "keyboard"}
            speak("한 번 더 시도해 볼게요.")

        elif fail_count >= max_attempts:
            speak("상담원을 연결해 드릴게요. 잠시만 기다려 주세요.")
            trigger_helpme_bridge()
            return {"success": False, "text": None, "method": "helpme"}

    return {"success": False, "text": None, "method": "helpme"}


# ══════════════════════════════════════════════════════════
# 4. 전화번호 정규화
# ══════════════════════════════════════════════════════════

def normalize_phone_number(text: str) -> str | None:
    """
    STT 출력 → 010-XXXX-XXXX 형식으로 정규화
    1. 한국어 숫자 단어 치환 (공→0, 일→1, ...)
    2. 숫자 이외 문자 제거
    3. 11자리 + 010 시작이면 포맷 반환, 아니면 None
    """
    for kor, num in KOREAN_DIGITS.items():
        text = text.replace(kor, num)

    digits = "".join(c for c in text if c.isdigit())

    if len(digits) == 11 and digits.startswith("0"):
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"

    return None


# ══════════════════════════════════════════════════════════
# 5. 슬롯 추출 (규칙 기반)
# ══════════════════════════════════════════════════════════

def extract_name(text: str) -> str | None:
    """
    발화에서 한국어 이름 추출
    "저는 송정현이에요" / "송 정현이요" / "음… 송정현인데" → "송정현"

    STT가 이름 중간에 공백을 넣는 경우 (예: "송 정현") 인접 토큰을 합쳐서 처리
    """
    # 이름 앞 필러/불필요한 표현 제거
    text = re.sub(r'(저는|제\s*이름은|이름이|성함이|나는|저|나|음+|아+|어+|그냥|뭐)\s*', '', text)
    # 이름 뒤 조사/어미 제거
    text = re.sub(r'(이에요|입니다|이고요|이라고|이야|인데|이요|이라|이고|님|씨|이|가|은|는).*$', '', text)

    tokens = re.findall(r'[가-힣]+', text.strip())
    if not tokens:
        return None

    # 인접한 두 토큰 합쳐서 2~4글자면 이름으로 처리 ("송 정현" → "송정현")
    for i in range(len(tokens) - 1):
        combined = tokens[i] + tokens[i + 1]
        if 2 <= len(combined) <= 4:
            return combined

    # 단일 토큰이 2~4글자면 반환
    for token in tokens:
        if 2 <= len(token) <= 4:
            return token

    return None


def extract_birthdate(text: str) -> str | None:
    """
    발화에서 생년월일 추출
    "1955년 3월 15일" / "1955 3 15" / "55년 3월 15일" → "1955년 3월 15일"
    """
    # 4자리 연도
    match = re.search(r'(\d{4})\s*년?\s*(\d{1,2})\s*월?\s*(\d{1,2})\s*일?', text)
    if match:
        y, m, d = match.groups()
        return f"{y}년 {int(m)}월 {int(d)}일"

    # 2자리 연도 (20 미만 → 2000년대, 이상 → 1900년대)
    match = re.search(r'(\d{2})\s*년\s*(\d{1,2})\s*월?\s*(\d{1,2})\s*일?', text)
    if match:
        y, m, d = match.groups()
        year = 2000 + int(y) if int(y) < 20 else 1900 + int(y)
        return f"{year}년 {int(m)}월 {int(d)}일"

    return None


def extract_slot(user_utterance: str, slot_name: str) -> str | None:
    if slot_name == "이름":
        return extract_name(user_utterance)
    elif slot_name == "생년월일":
        return extract_birthdate(user_utterance)
    return None


# ══════════════════════════════════════════════════════════
# 6. 확인 화면
# ══════════════════════════════════════════════════════════

def confirm_value(slot_name: str, value: str) -> bool:
    """확인 화면 출력 + TTS 후 사용자 응답 반환 (True=확인, False=재시도)"""
    confirm_msg = f"{value}님 맞으신가요?" if slot_name == "이름" else f"{value} 맞으신가요?"
    print(f'\n{"="*40}')
    speak(confirm_msg + " 맞다면 아래 버튼을 눌러주세요.")
    print(f'{"="*40}')
    answer = input("[Enter] 맞아요   [n] 틀려요\n> ").strip().lower()
    return answer not in ["n", "no", "아니요", "틀려", "아니"]


# ══════════════════════════════════════════════════════════
# 7. 슬롯 수집 (이름 / 생년월일)
# ══════════════════════════════════════════════════════════

def collect_slot(slot_name: str) -> str | None:
    slot_info = SLOT_DEFINITIONS[slot_name]

    while True:
        print(f'\n🔊 {slot_info["question"]}')

        stt_result = stt_with_retry(prompt_message=slot_info["question"])
        if not stt_result["success"]:
            return None

        value = extract_slot(stt_result["text"], slot_name)

        if value is None:
            print(f'추출 실패. 예시: {slot_info["example"]}\n다시 말씀해 주세요.')
            continue

        if confirm_value(slot_name, value):
            return value


# ══════════════════════════════════════════════════════════
# 8. 전화번호 수집 (전용)
# ══════════════════════════════════════════════════════════

def collect_4digits(prompt: str) -> str | None:
    """
    4자리 숫자 덩어리 수집
    최대 2회 시도 후 실패 시 None 반환
    """
    for attempt in range(1, 3):
        stt_result = stt_with_retry(prompt_message=prompt)
        if not stt_result["success"]:
            return None

        # 한국어 숫자 변환 후 숫자만 추출
        text = stt_result["text"]
        for kor, num in KOREAN_DIGITS.items():
            text = text.replace(kor, num)
        digits = "".join(c for c in text if c.isdigit())

        if len(digits) == 4:
            return digits

        print(f"[{attempt}차 실패] 4자리가 필요해요. 인식됨: \"{stt_result['text']}\"")

    return None


def collect_phone_number() -> str | None:
    """
    010 고정 + 중간 4자리 + 끝 4자리를 따로 수집
    4자리씩 짧게 받아 STT 오인식 최소화

    실패 시 키보드 폴백 → 헬프미 스텁
    """
    print("\n🔊 휴대폰 번호 앞자리 010은 자동으로 입력됩니다.")
    print("   중간 네 자리와 마지막 네 자리만 말씀해 주세요.")

    while True:
        # 중간 4자리
        middle = collect_4digits("중간 네 자리를 말씀해 주세요. 예시로 이팔구오")
        if middle is None:
            break

        # 끝 4자리
        last = collect_4digits("마지막 네 자리를 말씀해 주세요. 예시로 일이일육")
        if last is None:
            break

        phone = f"010-{middle[:4]}-{last[:4]}"

        if confirm_value("전화번호", phone):
            return phone
        # 틀렸다면 처음부터 다시

    # 키보드 폴백
    print("\n음성 입력이 어려우시면 직접 입력해 주세요. (건너뛰려면 Enter)")
    keyboard_input = input("번호 입력 (예: 010-2895-1216): ").strip()

    if keyboard_input:
        phone = normalize_phone_number(keyboard_input)
        return phone if phone else keyboard_input

    # 헬프미 스텁
    print("\n📞 상담원을 연결해 드릴게요.")
    trigger_helpme_bridge()
    return None


# ══════════════════════════════════════════════════════════
# 8-2. O/X 질문 수집 (예/아니요)
# ══════════════════════════════════════════════════════════

_YES_TOKENS = {"네", "예", '에', "응", "어", "맞아", "맞아요", "맞습니다", "이용해요",
               "사용해요", "써요", "하고있어요", "하고있어", "해요", "해"}
_NO_TOKENS  = {"아니요", "아니", "없어요", "안해요", "안 해요", "안해", "안씁니다",
               "모릅니다", "모르겠어요", "몰라요" , '아뇨', '아니예' , '아녜'}


def _parse_yes_no(text: str) -> bool | None:
    normalized = text.strip().replace(" ", "")
    # NO를 먼저, 긴 토큰 우선 — "아니네요"에서 "네"가 YES로 오인식되는 것 방지
    for token in sorted(_NO_TOKENS, key=len, reverse=True):
        if token.replace(" ", "") in normalized:
            return False
    for token in sorted(_YES_TOKENS, key=len, reverse=True):
        if token.replace(" ", "") in normalized:
            return True
    return None


def _show_ox_screen(question: str) -> None:
    print(f"\n{'='*44}")
    print(f"  ❓ {question}")
    print(f"{'─'*44}")
    print("          ⭕  네            ❌  아니요")
    print(f"{'='*44}")


def collect_yes_no(question: str, tts_prompt: str) -> bool | None:
    """
    O/X 화면 표시 후 음성으로 예/아니요 수집.
    최대 3회 재시도, 실패 시 None 반환.
    """
    for attempt in range(1, 4):
        _show_ox_screen(question)
        stt_result = stt_with_retry(prompt_message=tts_prompt, duration=4, min_len=1)

        if not stt_result["success"]:
            return None

        answer = _parse_yes_no(stt_result["text"])
        if answer is not None:
            label = "네" if answer else "아니요"
            speak(f"{label}, 확인했습니다.")
            return answer

        if attempt < 3:
            speak("죄송해요, '네' 또는 '아니요'로 말씀해 주세요.")

    # 3회 실패 시 키보드 폴백
    _show_ox_screen(question)
    speak("키보드로 선택해 주세요.")
    raw = input("  [Enter] 네   [n] 아니요\n  > ").strip().lower()
    if raw in ("n", "no", "아니요", "아니"):
        return False
    return True


# ══════════════════════════════════════════════════════════
# 9. 전체 온보딩 실행
# ══════════════════════════════════════════════════════════

def run_onboarding() -> dict:
    print("\n" + "="*40)
    speak("안녕하세요! 카카오뱅크 말동무 가입입니다. 말씀만 하시면 제가 도와드릴게요.")
    print("="*40)

    collected = {}

    for slot_name in ["이름", "생년월일"]:
        value = collect_slot(slot_name)
        if value is None:
            print(f"\n[{slot_name}] 수집 중단")
            return collected
        collected[slot_name] = value
        print(f"✔ {slot_name} 저장 완료")

    phone = collect_phone_number()
    if phone is None:
        print("\n[전화번호] 수집 중단")
        return collected
    collected["전화번호"] = phone
    print("✔ 전화번호 저장 완료")

    internet_banking = collect_yes_no(
        question="인터넷 뱅킹을 이용하고 계신가요?",
        tts_prompt="평소에 인터넷 뱅킹이나 앱 뱅킹을 이용하고 계신가요? 네 또는 아니요로 말씀해 주세요.",
    )
    if internet_banking is None:
        print("\n[인터넷뱅킹 이용여부] 수집 중단")
        return collected
    collected["인터넷뱅킹이용여부"] = internet_banking
    print(f"✔ 인터넷뱅킹 이용여부 저장 완료: {'이용' if internet_banking else '미이용'}")

    print("\n" + "="*40)
    print("📋 수집된 정보")
    for k, v in collected.items():
        if isinstance(v, bool):
            print(f"  {k}: {'이용' if v else '미이용'}")
        else:
            print(f"  {k}: {v}")
    print("="*40)

    return collected


if __name__ == "__main__":
    run_onboarding()
