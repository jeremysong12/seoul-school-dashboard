import csv
from datetime import datetime
from collections import defaultdict
from transaction_dict import classify, fixed_summary, filter_fixed

CSV_PATH = "시니어_거래데이터_샘플.csv"

# ─── 레거시 키워드 사전 (하위 호환 유지용) ──────────────────────
CATEGORY_RULES = {
    "가족": [
        "아들", "딸", "손자", "손녀", "며느리", "사위", "용돈", "생일선물",
        "가족송금", "자녀", "어린이날",
    ],
    "노인회": [
        "노인회", "노인지부", "경로당", "어르신", "노령",
    ],
    "종교": [
        "성당", "교회", "절", "사찰", "헌금", "봉헌", "십일조", "법당",
    ],
    "보험": [
        "삼성화재", "현대해상", "kb손해보험", "메리츠", "한화생명",
        "교보생명", "삼성생명", "동양생명", "보험료",
    ],
    "공과금": [
        "도시가스", "전기요금", "한국전력", "수도요금", "관리비",
        "통신비", "kt 통신", "skt", "lg유플러스", "건강보험",
        "국민건강보험", "kbs수신료",
    ],
    "의료": [
        "내과", "정형외과", "한의원", "안과", "의원", "병원", "치과",
        "이비인후과", "외과", "신경과", "피부과", "재활",
    ],
    "약국": [
        "약국", "한약", "약방",
    ],
    "교통": [
        "버스", "지하철", "택시", "교통카드", "t머니", "기차", "ktx",
    ],
    "카페": [
        "이디야", "스타벅스", "투썸", "빽다방", "할리스", "탐앤탐스",
        "엔젤리너스", "메가커피", "컴포즈", "카페온니",
    ],
    "복지관/여가": [
        "복지관", "문화강좌", "요가", "수영", "헬스", "문화센터", "동호회",
        "경로", "강좌",
    ],
    "시장/마트": [
        "전통시장", "이마트24", "이마트", "홈플러스", "롯데마트",
        "씨유", "gs25", "세븐일레븐", "미니스톱", "마트", "시장",
    ],
    "식비": [
        "설렁탕", "김밥", "국수", "순대국", "삼겹살", "백반", "식당", "밥집",
        "분식", "냉면", "갈비", "치킨", "피자", "햄버거", "떡볶이",
        "일미", "반찬", "계단집",
    ],
    "온라인쇼핑": [
        "쿠팡", "마켓컬리", "지마켓", "옥션", "11번가", "위메프", "티몬",
        "배달의민족", "요기요", "배민",
    ],
}

# 우선순위: 앞에 나올수록 높음
_PRIORITY_ORDER = list(CATEGORY_RULES.keys())

# 키워드 → 카테고리 역방향 인덱스
_KEYWORD_INDEX: dict[str, str] = {}
for _cat, _keywords in CATEGORY_RULES.items():
    for _kw in _keywords:
        _KEYWORD_INDEX[_kw.lower()] = _cat


def classify_transaction(description: str) -> str:
    """
    가맹점명 → 카테고리.
    우선순위 높은 카테고리 내에서 긴 키워드 우선 매칭, 없으면 '기타'.
    """
    desc_lower = description.lower()

    matched = [
        (kw, cat)
        for kw, cat in _KEYWORD_INDEX.items()
        if kw in desc_lower
    ]
    if not matched:
        return "기타"

    # 우선순위(카테고리 선언 순) → 키워드 길이 내림차순
    matched.sort(key=lambda x: (_PRIORITY_ORDER.index(x[1]), -len(x[0])))
    return matched[0][1]


# ─── CSV 로더 ─────────────────────────────────────────────────

def _parse_amount(raw: str) -> int:
    """'1,450' → 1450"""
    return int(raw.replace(",", "").strip())


def load_transactions(filepath: str = CSV_PATH) -> list[dict]:
    """
    실제 CSV(거래일시, 매출금액, 가맹점명)를 읽어
    5단계 계층 분류 + 고정비 여부 포함해 반환.
    """
    transactions = []
    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["가맹점명"].strip()
            amount = _parse_amount(row["매출금액"])
            date_str = row["거래일시"].strip()[:10]
            date = datetime.strptime(date_str, "%Y.%m.%d")

            result = classify(name, tx_type_hint="expense")
            transactions.append({
                "날짜": date,
                "날짜_str": date_str,
                "가맹점명": name,
                "금액": amount,
                "카테고리": result["L2"],          # 기존 호환
                "is_fixed": result["is_fixed"],
                "분류": result,                    # 전체 5단계
            })
    return transactions


# ─── 집계 ─────────────────────────────────────────────────────

def summarize_by_category(transactions: list[dict]) -> dict[str, dict]:
    summary = defaultdict(lambda: {"총액": 0, "건수": 0, "내역": []})
    for tx in transactions:
        cat = tx["카테고리"]
        summary[cat]["총액"] += tx["금액"]
        summary[cat]["건수"] += 1
        summary[cat]["내역"].append(tx["가맹점명"])
    return dict(summary)


def summarize_by_month(transactions: list[dict]) -> dict[str, dict]:
    """월별 집계 (YYYY-MM 키)."""
    monthly: dict[str, list] = defaultdict(list)
    for tx in transactions:
        key = tx["날짜"].strftime("%Y-%m")
        monthly[key].append(tx)
    return {month: summarize_by_category(txs) for month, txs in sorted(monthly.items())}


# ─── 리포트 출력 ──────────────────────────────────────────────

def print_report(transactions: list[dict], month_filter: str | None = None) -> None:
    """
    월 전체 또는 특정 월(YYYY-MM) 지출 리포트 터미널 출력.
    """
    if month_filter:
        transactions = [
            tx for tx in transactions
            if tx["날짜"].strftime("%Y-%m") == month_filter
        ]
    summary = summarize_by_category(transactions)

    label = f"{month_filter} 지출 분석" if month_filter else "전체 지출 분석"
    print(f"\n{'='*52}")
    print(f"  📊 {label}")
    print(f"{'='*52}")

    sorted_cats = sorted(summary.items(), key=lambda x: -x[1]["총액"])
    total = sum(d["총액"] for d in summary.values())

    for cat, data in sorted_cats:
        bar = "█" * min(data["총액"] // 10000, 20)
        print(f"  {cat:<10} {data['총액']:>9,}원  ({data['건수']:>2}건)  {bar}")

    print(f"{'─'*52}")
    print(f"  {'합계':<10} {total:>9,}원")
    print(f"{'='*52}")


def print_fixed_report(transactions: list[dict]) -> None:
    """고정비성 항목만 뽑아서 집중 분석 출력."""
    fixed = filter_fixed(transactions)
    summary = fixed_summary(fixed)

    total = sum(d["총액"] for d in summary.values())
    grand_total = sum(tx["금액"] for tx in transactions)
    ratio = total / grand_total * 100 if grand_total else 0

    print(f"\n{'='*52}")
    print(f"  🔒 고정비 분석  (전체 지출 대비 {ratio:.1f}%)")
    print(f"{'='*52}")
    for L2, data in sorted(summary.items(), key=lambda x: -x[1]["총액"]):
        bar = "█" * min(data["총액"] // 10000, 20)
        items = ", ".join(set(data["항목"]))
        print(f"  {L2:<10} {data['총액']:>9,}원  ({data['건수']:>2}건)  {bar}")
        print(f"    └ {items}")
    print(f"{'─'*52}")
    print(f"  고정비 합계   {total:>9,}원  /  전체 {grand_total:,}원")
    print(f"{'='*52}")


def print_unclassified(transactions: list[dict]) -> None:
    """기타(미분류) 항목만 출력해 키워드 추가 여부 확인용."""
    others = [tx for tx in transactions if tx["카테고리"] == "기타"]
    if not others:
        print("\n✅ 미분류 항목 없음")
        return
    print(f"\n⚠️  미분류 항목 ({len(others)}건)")
    for tx in others:
        print(f"  {tx['날짜_str']}  {tx['가맹점명']:<25}  {tx['금액']:>7,}원")


# ─── TTS 브리핑 ───────────────────────────────────────────────

def generate_tts_briefing(transactions: list[dict], month_filter: str | None = None) -> str:
    """
    월별 상위 3개 카테고리 중심 TTS 브리핑 문자열 생성.
    """
    if month_filter:
        transactions = [
            tx for tx in transactions
            if tx["날짜"].strftime("%Y-%m") == month_filter
        ]

    summary = summarize_by_category(transactions)
    top3 = sorted(summary.items(), key=lambda x: -x[1]["총액"])[:3]
    total = sum(d["총액"] for d in summary.values())

    lines = [f"이번 달 총 지출은 {total:,}원입니다."]
    for i, (cat, data) in enumerate(top3, 1):
        lines.append(
            f"지출 {i}위는 {cat}으로, {data['총액']:,}원 사용하셨어요."
        )
    return " ".join(lines)


# ─── 실행 ────────────────────────────────────────────────────
if __name__ == "__main__":
    txs = load_transactions()

    # 4월 전체 리포트
    print_report(txs, month_filter="2026-04")

    # 4월 고정비 집중 분석
    apr = [tx for tx in txs if tx["날짜"].strftime("%Y-%m") == "2026-04"]
    print_fixed_report(apr)

    # 미분류 확인
    print_unclassified(txs)

    # TTS 브리핑
    print("\n[ 4월 TTS 브리핑 ]")
    print(generate_tts_briefing(txs, month_filter="2026-04"))

    # 전체 분류 결과 (5단계 포함)
    print("\n[ 전체 분류 결과 ]")
    print(f"  {'날짜':<12} {'가맹점명':<28} {'L1':<10} {'L2':<12} {'고정비'}")
    print("  " + "─" * 72)
    for tx in txs:
        d = tx["분류"]
        print(f"  {tx['날짜_str']:<12} {tx['가맹점명']:<28} "
              f"{d['L1']:<10} {d['L2']:<12} {'🔒' if tx['is_fixed'] else '  '}")
