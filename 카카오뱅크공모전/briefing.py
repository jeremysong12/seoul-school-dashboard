"""
AI 금융 브리핑 파이프라인
거래 데이터 로드 → 분류 → LLM 요약 → TTS 재생
"""

from datetime import datetime, timedelta
from financial_advisor import load_transactions
from llm_summary import summarize_transactions, filter_yesterday_today
from onboarding import speak


def _filter_by_days(transactions: list[dict], days: int) -> list[dict]:
    cutoff = datetime.now() - timedelta(days=days)
    return [tx for tx in transactions if tx["날짜"] >= cutoff]


def run_briefing(
    days: int = 7,
    csv_path: str = "시니어_거래데이터_샘플.csv",
    persona: str = "banker",
    yesterday_today: bool = False,
) -> dict:
    """
    메인 브리핑 실행 함수

    1. 거래 데이터 로드 + 분류
    2. 최근 N일 필터링
    3. LLM 자연어 요약 생성
    4. TTS 음성 재생

    Returns
    -------
    {
        "period"      : 기간 레이블,
        "tx_count"    : 거래 건수,
        "total_amount": 총 지출액,
        "summary_text": LLM 요약 문장,
        "transactions": 거래 목록,
    }
    """
    # 1. 로드 + 분류
    all_txs = load_transactions(csv_path)

    # 2. 기간 필터
    reference_date = None
    if yesterday_today:
        recent, period, reference_date = filter_yesterday_today(all_txs)
    else:
        recent = _filter_by_days(all_txs, days)
        if not recent:
            recent = all_txs[-min(days * 3, len(all_txs)):]
        period = f"최근 {days}일"

    total = sum(tx["금액"] for tx in recent)

    # 3. LLM 요약
    print(f"\n⏳ {period} 거래 {len(recent)}건 분석 중... (페르소나: {persona})")
    speak("잠시만 기다려 주세요.")
    summary_text = summarize_transactions(recent, period=period, persona=persona, reference_date=reference_date)

    # 4. TTS 재생 — 금융 정보는 천천히
    speak(summary_text, rate="-15%")

    return {
        "period"       : period,
        "tx_count"     : len(recent),
        "total_amount" : total,
        "summary_text" : summary_text,
        "transactions" : recent,
    }


def run_briefing_with_prompt(csv_path: str = "시니어_거래데이터_샘플.csv") -> dict | None:
    """
    가계부 진입 시 전체 플로우 (터미널 시뮬레이션 — 추후 HTML 버튼으로 교체)

    1. "어제와 오늘 거래 내역을 알려드릴까요?" → O/X
    2. O → "손자 / 은행원 누가 설명해드릴까요?" → 선택
    3. 선택한 페르소나로 브리핑 실행
    X → 가계부 화면으로 이동 (터미널에서는 종료)
    """
    speak("어제와 오늘 거래 내역을 알려드릴까요?")
    print("\n  ⭕ [Enter] 네     ❌ [n] 아니요")
    answer = input("  > ").strip().lower()

    if answer in ("n", "no", "아니요", "아니"):
        speak("알겠어요. 가계부 화면으로 이동할게요.")
        return None

    # 페르소나 선택
    print("\n" + "="*44)
    print("  누가 설명해드리길 원하세요?")
    print("  [1] 👦 손자    [2] 👩‍💼 은행원")
    print("="*44)
    choice = input("  > ").strip()

    persona = "grandson" if choice == "1" else "banker"
    name, suffix = ("손자", "가") if persona == "grandson" else ("은행원", "이")
    speak(f"네, {name}{suffix} 설명해드릴게요.")

    return run_briefing(csv_path=csv_path, persona=persona, yesterday_today=True)


# ─── 실행 ─────────────────────────────────────────────────
if __name__ == "__main__":
    result = run_briefing_with_prompt()

    if result:
        print(f"\n{'='*50}")
        print(f"  기간     : {result['period']}")
        print(f"  거래 건수 : {result['tx_count']}건")
        print(f"  총 지출   : {result['total_amount']:,}원")
        print(f"\n  [ 브리핑 문구 ]")
        print(f"  {result['summary_text']}")
        print(f"{'='*50}")
