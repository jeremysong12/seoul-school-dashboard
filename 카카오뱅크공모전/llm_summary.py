"""
LLM 자연어 요약 모듈
분류된 거래 내역 → 시니어 친화적 음성 브리핑 문장 생성
페르소나: 'grandson'(손자) | 'banker'(은행원)
"""

from datetime import datetime, timedelta
from google import genai

GEMINI_API_KEY = "AIzaSyBuiidaccWmWIy4IYGh9nwKlPFgTiNvgAs"
MODEL = "gemini-2.5-flash"

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


# ─── 페르소나별 시스템 프롬프트 ────────────────────────────

PERSONA_GRANDSON = """너는 할머니(혹은 할아버지)를 사랑하는 손자야.
어르신이 걱정하지 않도록 따뜻하고 귀엽게 거래 내역을 설명해줘.

규칙:
- 말투: 친근하고 다정하게 (예: ~하셨어요, 할머니~, 오늘도 잘 챙겨 드셨네요!)
- 금액은 쉽게 풀어서 (20000원 → 이만 원)
- 가맹점명은 자연스럽게 (노량진내과의원 → 병원, 이마트 노량진점 → 이마트 , 스타벅스 -> 커피)
- 입금은 누가 보내줬는지 강조 (예: OO님이 십만 원 보내주셨어요!)
- 공감 한 마디 포함 (예: 오늘 병원 다녀오셨군요, 몸은 좀 어떠세요?)
- 전체 2~4문장, 너무 길지 않게
- 숫자 읽기: 100000 → 십만, 50000 → 오만, 20000 → 이만"""

PERSONA_BANKER = """당신은 카카오뱅크 시니어 전담 여자 은행원입니다.
고객은 60~70대 어르신이며, 신뢰감 있고 명확하게 거래 내역을 안내해드려야 합니다.

규칙:
- 말투: 정중하고 전문적으로 (예: ~하셨습니다, ~확인되셨습니다)
- 금액은 한국어 구어체로 (20000원 → 이만 원)
- 가맹점명은 자연스럽게 (노량진내과의원 → 내과 병원)
- 입금은 송금인을 명확히 (예: OO님께서 십만 원 송금하셨습니다)
- 감정 표현 없이 사실 중심으로 간결하게
- 전체 2~4문장
- 숫자 읽기: 100000 → 십만, 50000 → 오만, 20000 → 이만"""

PERSONAS = {
    "grandson": PERSONA_GRANDSON,
    "banker":   PERSONA_BANKER,
}


# ─── 유틸 ─────────────────────────────────────────────────

def _format_amount(won: int) -> str:
    if won >= 100000:
        return f"{won // 10000}만 원"
    elif won >= 10000:
        remainder = won % 10000
        if remainder == 0:
            return f"{won // 10000}만 원"
        return f"{won // 10000}만 {remainder // 1000}천 원"
    else:
        return f"{won:,}원"


def filter_yesterday_today(transactions: list[dict]) -> tuple[list[dict], str, "datetime.date"]:
    """
    어제 + 오늘 거래 필터링.
    실제 오늘/어제 데이터가 없으면 데이터 내 최신 날짜를 오늘로 간주.
    반환: (filtered, period 레이블, reference_date)
    """
    today     = datetime.now().date()
    yesterday = today - timedelta(days=1)
    filtered  = [tx for tx in transactions if tx["날짜"].date() in (today, yesterday)]

    if filtered:
        return filtered, "어제와 오늘", today

    # 샘플 데이터 대응: 데이터 내 가장 최근 날짜를 오늘로 간주
    if transactions:
        ref_today = max(tx["날짜"].date() for tx in transactions)
        ref_yesterday = ref_today - timedelta(days=1)
        filtered = [tx for tx in transactions if tx["날짜"].date() in (ref_today, ref_yesterday)]
        return filtered, "어제와 오늘", ref_today

    return [], "어제와 오늘", today


# ─── 핵심 요약 함수 ───────────────────────────────────────

def summarize_transactions(
    transactions: list[dict],
    period: str = "오늘",
    persona: str = "banker",
    reference_date: "datetime.date | None" = None,
) -> str:
    """
    분류된 거래 목록 → 시니어 친화적 자연어 요약 문장

    Parameters
    ----------
    transactions   : load_transactions()의 반환값
    period         : '어제와 오늘', '이번 주' 등 기간 레이블
    persona        : 'grandson' | 'banker'
    reference_date : 오늘 기준 날짜 (None이면 실제 오늘, 테스트 시 지정)
    """
    if not transactions:
        return f"{period} 거래 내역이 없어요."

    system_prompt = PERSONAS.get(persona, PERSONA_BANKER)

    # 어제/오늘 분리
    today         = reference_date or datetime.now().date()
    yesterday     = today - timedelta(days=1)
    yesterday_txs = [tx for tx in transactions if tx["날짜"].date() == yesterday]
    today_txs     = [tx for tx in transactions if tx["날짜"].date() == today]
    other_txs     = [tx for tx in transactions
                     if tx["날짜"].date() not in (today, yesterday)]

    yesterday_total = sum(tx["금액"] for tx in yesterday_txs)
    today_total     = sum(tx["금액"] for tx in today_txs)
    grand_total     = sum(tx["금액"] for tx in transactions)

    def _tx_lines(txs: list[dict]) -> str:
        return "\n".join(
            f"  - {tx['가맹점명']} ({tx.get('분류', {}).get('L2', '기타')}) {_format_amount(tx['금액'])}"
            for tx in txs
        )

    sections = []
    if yesterday_txs:
        sections.append(
            f"[어제 거래 — 합계 {_format_amount(yesterday_total)}]\n{_tx_lines(yesterday_txs)}"
        )
    if today_txs:
        sections.append(
            f"[오늘 거래 — 합계 {_format_amount(today_total)}]\n{_tx_lines(today_txs)}"
        )
    if other_txs:
        sections.append(f"[기타 거래]\n{_tx_lines(other_txs)}")

    sections.append(f"[어제+오늘 합계: {_format_amount(grand_total)}]")
    tx_text = "\n\n".join(sections)

    prompt = f"""거래 내역입니다:
{tx_text}

아래 형식을 반드시 지켜서 브리핑을 작성해주세요.
다른 형식은 절대 사용하지 마세요.

[형식 예시]
어제는 병원에서 이만 원, 약국에서 팔천 원을 사용하셨습니다. 어제 총 이만 팔천 원 지출하셨습니다.
오늘은 이마트에서 삼만 원, 버스 이용에 천이백오십 원을 사용하셨습니다. 오늘 총 삼만 천이백오십 원 지출하셨습니다.
어제와 오늘 합쳐서 총 오만 구천이백오십 원 사용하셨습니다.

[규칙]
- 어제 거래가 없으면 어제 부분은 생략
- 오늘 거래가 없으면 오늘 부분은 생략
- 금액은 반드시 한국어 구어체로 (20000 → 이만 원)
- 가맹점명은 자연스럽게 풀어서"""

    try:
        resp = _get_client().models.generate_content(
            model=MODEL,
            contents=prompt,
            config={"system_instruction": system_prompt},
        )
        return resp.text.strip()
    except Exception:
        return _fallback_summary(transactions, period)


def _fallback_summary(transactions: list[dict], period: str) -> str:
    """LLM 실패 시 규칙 기반 폴백"""
    from collections import defaultdict
    cats  = defaultdict(int)
    total = 0
    for tx in transactions:
        L2 = tx.get("분류", {}).get("L2", "기타")
        cats[L2] += tx["금액"]
        total    += tx["금액"]

    top   = sorted(cats.items(), key=lambda x: -x[1])[:2]
    lines = [f"{period} 총 {_format_amount(total)} 지출하셨어요."]
    for cat, amt in top:
        lines.append(f"{cat}에 {_format_amount(amt)} 사용하셨어요.")
    return " ".join(lines)


# ─── 실행 테스트 ──────────────────────────────────────────
if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from financial_advisor import load_transactions

    txs = load_transactions()

    # 샘플 데이터 기준 오늘 = 05.08, 어제 = 05.07
    fake_today = datetime(2026, 5, 8).date()
    sample = [tx for tx in txs if tx["날짜"].date() in (fake_today, fake_today - timedelta(days=1))]

    print("[ 입력 거래 내역 ]")
    for tx in sample:
        print(f"  {tx['날짜_str']}  {tx['가맹점명']:<25} {tx['금액']:>8,}원  {tx['분류']['L2']}")

    print("\n[ 손자 페르소나 ]")
    print(summarize_transactions(sample, period="어제와 오늘", persona="grandson", reference_date=fake_today))

    print("\n[ 은행원 페르소나 ]")
    print(summarize_transactions(sample, period="어제와 오늘", persona="banker", reference_date=fake_today))
