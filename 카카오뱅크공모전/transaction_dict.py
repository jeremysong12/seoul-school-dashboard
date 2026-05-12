"""
시니어 거래 적요 사전 (Transaction Description Dictionary)

L1 (6개 테마)
  income   : 수입 — 연금, 정부지원금, 입금
  living   : 생활 — 식비, 마트/시장, 공과금, 통신, 카페, 온라인, 복지관/노인회/종교이체
  medical  : 의료 — 의원, 약국
  transport: 교통 — 버스, 지하철, 택시
  finance  : 금융 — 보험, 대출, 적금, 건강보험, 카드대금
  transfer : 이체/출금 — 개인간 이체, ATM 현금인출, 카카오페이 송금

is_fixed : 고정비성 여부 (자동이체·정기 반복 항목)
tx_type  : 'income' | 'expense' | 'both'
priority : 낮을수록 먼저 적용 (동명이의어 해소)
"""

import re
from dataclasses import dataclass, field


@dataclass
class TxCategory:
    id: str
    L1: str
    L2: str
    L3: str
    L4: str
    L5: list
    keywords: list
    patterns: list
    is_fixed: bool
    tx_type: str
    priority: int = 50
    _compiled: list = field(default_factory=list, init=False, repr=False)

    def __post_init__(self):
        self._compiled = [re.compile(p, re.IGNORECASE) for p in self.patterns]


# ── income (수입) ─────────────────────────────────────────
INCOME_CATEGORIES = [
    TxCategory(
        id="INC_PENSION_NATIONAL",
        L1="income", L2="급여성수입", L3="연금", L4="국민연금", L5=["국민연금"],
        keywords=["국민연금"],
        patterns=[r"국민연금(?!공단)"],
        is_fixed=True, tx_type="income", priority=10,
    ),
    TxCategory(
        id="INC_PENSION_BASIC",
        L1="income", L2="급여성수입", L3="연금", L4="기초연금", L5=[],
        keywords=["기초연금", "노령연금"],
        patterns=[r"기초연금|노령연금"],
        is_fixed=True, tx_type="income", priority=10,
    ),
    TxCategory(
        id="INC_GOV_SUPPORT",
        L1="income", L2="급여성수입", L3="정부지원금", L4="복지급여", L5=[],
        keywords=["정부지원", "복지급여", "지원금", "보조금", "바우처"],
        patterns=[r"정부.*지원|복지.*급여|보조금|바우처"],
        is_fixed=False, tx_type="income", priority=15,
    ),
]

# ── finance (금융) ────────────────────────────────────────
FINANCE_CATEGORIES = [
    TxCategory(
        id="FIN_INSURANCE",
        L1="finance", L2="보험", L3="민간보험", L4="보험료",
        L5=["삼성화재", "현대해상", "한화생명", "교보생명", "삼성생명"],
        keywords=["보험료", "삼성화재", "현대해상", "kb손해보험", "한화생명",
                  "교보생명", "삼성생명", "동양생명", "메리츠"],
        patterns=[r"보험료|삼성화재|현대해상|KB손해보험|한화생명|교보생명|삼성생명|동양생명|메리츠"],
        is_fixed=True, tx_type="expense", priority=10,
    ),
    TxCategory(
        id="FIN_HEALTH_INS",
        L1="finance", L2="사회보험", L3="건강보험", L4="자동이체", L5=["국민건강보험"],
        keywords=["국민건강보험", "건강보험"],
        patterns=[r"국민건강보험|건강보험\s*자동이체"],
        is_fixed=True, tx_type="expense", priority=10,
    ),
    TxCategory(
        id="FIN_PENSION_OUT",
        L1="finance", L2="사회보험", L3="국민연금(납부)", L4="자동이체", L5=["국민연금공단"],
        keywords=["국민연금공단"],
        patterns=[r"국민연금공단"],
        is_fixed=True, tx_type="expense", priority=10,
    ),
    TxCategory(
        id="FIN_LOAN",
        L1="finance", L2="대출", L3="대출이자", L4="자동이체", L5=[],
        keywords=["대출이자", "이자출금", "원리금"],
        patterns=[r"대출이자|이자출금|원리금"],
        is_fixed=True, tx_type="expense", priority=10,
    ),
    TxCategory(
        id="FIN_SAVINGS",
        L1="finance", L2="적금", L3="적금", L4="자동이체", L5=[],
        keywords=["적금"],
        patterns=[r"적금\s*자동|자동납부.*적금"],
        is_fixed=True, tx_type="expense", priority=10,
    ),
    TxCategory(
        id="FIN_CARD",
        L1="finance", L2="카드대금", L3="신용/체크카드", L4="자동이체",
        L5=["하나카드", "신한카드", "삼성카드", "현대카드"],
        keywords=["하나카드", "신한카드", "삼성카드", "현대카드", "kb카드", "우리카드", "카드대금"],
        patterns=[r"(하나|신한|삼성|현대|KB|우리|롯데|BC)카드\s*(대금|결제|자동납부)?"],
        is_fixed=True, tx_type="expense", priority=10,
    ),
]

# ── living (생활) ─────────────────────────────────────────
LIVING_CATEGORIES = [
    TxCategory(
        id="LIV_GAS",
        L1="living", L2="공과금", L3="도시가스", L4="자동이체", L5=["서울도시가스"],
        keywords=["도시가스"],
        patterns=[r"도시가스"],
        is_fixed=True, tx_type="expense", priority=10,
    ),
    TxCategory(
        id="LIV_ELECTRIC",
        L1="living", L2="공과금", L3="전기요금", L4="자동이체", L5=["한국전력"],
        keywords=["전기요금", "한국전력", "한전"],
        patterns=[r"전기요금|한국전력|한전"],
        is_fixed=True, tx_type="expense", priority=10,
    ),
    TxCategory(
        id="LIV_WATER",
        L1="living", L2="공과금", L3="수도요금", L4="자동이체", L5=[],
        keywords=["수도요금", "상수도"],
        patterns=[r"수도요금|상수도"],
        is_fixed=True, tx_type="expense", priority=10,
    ),
    TxCategory(
        id="LIV_RENT",
        L1="living", L2="주거", L3="월세", L4="자동이체", L5=[],
        keywords=["월세", "임대료"],
        patterns=[r"\d{1,2}월\s*월세|월세\s*자동이체|임대료"],
        is_fixed=True, tx_type="expense", priority=10,
    ),
    TxCategory(
        id="LIV_MGMT",
        L1="living", L2="주거", L3="관리비", L4="자동이체", L5=[],
        keywords=["관리비"],
        patterns=[r"관리비"],
        is_fixed=True, tx_type="expense", priority=10,
    ),
    TxCategory(
        id="LIV_TELECOM",
        L1="living", L2="통신", L3="모바일/인터넷", L4="통신비",
        L5=["KT", "SKT", "LG유플러스"],
        keywords=["통신비", "kt 통신", "skt", "lg유플러스"],
        patterns=[r"통신비|KT\s*통신|SKT|LG유플러스"],
        is_fixed=True, tx_type="expense", priority=10,
    ),
    TxCategory(
        id="LIV_MART",
        L1="living", L2="시장/마트", L3="대형마트/편의점", L4="카드결제",
        L5=["이마트", "씨유", "GS25", "이마트24"],
        keywords=["전통시장", "이마트24", "이마트", "홈플러스", "롯데마트",
                  "씨유", "gs25", "세븐일레븐", "마트", "시장"],
        patterns=[r"이마트24|이마트|전통시장|씨유|GS25|홈플러스|롯데마트"],
        is_fixed=False, tx_type="expense", priority=30,
    ),
    TxCategory(
        id="LIV_FOOD",
        L1="living", L2="식비", L3="외식", L4="일반음식점", L5=[],
        keywords=["설렁탕", "김밥", "국수", "순대국", "삼겹살", "백반", "식당",
                  "냉면", "갈비", "치킨", "피자", "분식", "반찬", "일미", "계단집"],
        patterns=[r"설렁탕|김밥|국수나무|순대국|삼겹살|백반|냉면|갈비|치킨"],
        is_fixed=False, tx_type="expense", priority=30,
    ),
    TxCategory(
        id="LIV_CAFE",
        L1="living", L2="카페", L3="카페", L4="카드결제",
        L5=["이디야", "스타벅스", "카페온니"],
        keywords=["이디야", "스타벅스", "투썸", "빽다방", "카페온니", "메가커피", "컴포즈"],
        patterns=[r"이디야|스타벅스|투썸|빽다방|카페온니|메가커피"],
        is_fixed=False, tx_type="expense", priority=30,
    ),
    TxCategory(
        id="LIV_ONLINE",
        L1="living", L2="온라인쇼핑", L3="이커머스", L4="카드결제",
        L5=["쿠팡", "마켓컬리"],
        keywords=["쿠팡", "마켓컬리", "지마켓", "옥션", "11번가"],
        patterns=[r"쿠팡|마켓컬리|지마켓|옥션|11번가"],
        is_fixed=False, tx_type="expense", priority=30,
    ),
    TxCategory(
        id="LIV_COMMUNITY",
        L1="living", L2="지역활동", L3="복지관/노인회/종교", L4="수강비/회비/헌금이체", L5=[],
        keywords=["복지관", "문화강좌", "요가", "수영", "노인회", "노인지부", "성당", "교회", "헌금"],
        patterns=[r"복지관|문화강좌|요가|수영|노인회|노인지부|성당|교회|헌금"],
        is_fixed=False, tx_type="expense", priority=40,
    ),
]

# ── medical (의료) ────────────────────────────────────────
MEDICAL_CATEGORIES = [
    TxCategory(
        id="MED_CLINIC",
        L1="medical", L2="의원/병원", L3="진료", L4="카드결제", L5=[],
        keywords=["내과", "정형외과", "한의원", "안과", "치과", "이비인후과",
                  "외과", "신경과", "피부과", "의원", "병원", "재활"],
        patterns=[r"(내과|정형외과|한의원|안과|치과|이비인후과|신경과|피부과|재활)"],
        is_fixed=False, tx_type="expense", priority=20,
    ),
    TxCategory(
        id="MED_PHARMACY",
        L1="medical", L2="약국/한약", L3="조제/한약", L4="카드결제", L5=[],
        keywords=["약국", "한약", "약방"],
        patterns=[r"약국|한약|약방"],
        is_fixed=False, tx_type="expense", priority=20,
    ),
]

# ── transport (교통) ──────────────────────────────────────
TRANSPORT_CATEGORIES = [
    TxCategory(
        id="TRN_TRANSIT_FIXED",
        L1="transport", L2="대중교통", L3="정기이용", L4="N건 묶음", L5=["티머니"],
        keywords=[],
        patterns=[r"\d{1,2}월\s*(버스|지하철|교통)\s*\d+건"],
        is_fixed=True, tx_type="expense", priority=10,
    ),
    TxCategory(
        id="TRN_TRANSIT_VAR",
        L1="transport", L2="대중교통", L3="단건", L4="카드결제", L5=[],
        keywords=["버스", "지하철", "택시"],
        patterns=[],
        is_fixed=False, tx_type="expense", priority=35,
    ),
]

# ── transfer (이체/출금) ──────────────────────────────────
TRANSFER_CATEGORIES = [
    TxCategory(
        id="TRF_ATM",
        L1="transfer", L2="현금출금", L3="ATM", L4="현금인출", L5=[],
        keywords=["atm출금", "현금인출", "cd출금"],
        patterns=[r"ATM\s*출금|현금인출|CD\s*출금"],
        is_fixed=False, tx_type="expense", priority=10,
    ),
    TxCategory(
        id="TRF_PERSONAL",
        L1="transfer", L2="개인이체", L3="개인간송금", L4="카카오페이/계좌이체", L5=[],
        keywords=["아들", "딸", "손자", "손녀", "카카오페이", "토스", "어린이날"],
        patterns=[r"(아들|딸|손자|손녀|어린이날).*(송금|용돈|선물|이체|카카오)?|카카오페이|토스송금"],
        is_fixed=False, tx_type="expense", priority=15,
    ),
    # 한글 2~4글자 단독 → 사람 이름으로 추정, 개인이체 처리
    # 음성 브리핑 시 "김정현 씨에게 보내셨어요" 형태로 읽어주면 사용자가 판단
    TxCategory(
        id="TRF_NAME",
        L1="transfer", L2="개인이체", L3="이름추정", L4="계좌이체", L5=[],
        keywords=[],
        patterns=[r"^[가-힣]{2,4}$"],
        is_fixed=False, tx_type="both", priority=50,
    ),
]

# ─── 전체 사전 ────────────────────────────────────────────
ALL_CATEGORIES = (
    INCOME_CATEGORIES
    + FINANCE_CATEGORIES
    + LIVING_CATEGORIES
    + MEDICAL_CATEGORIES
    + TRANSPORT_CATEGORIES
    + TRANSFER_CATEGORIES
)
ALL_CATEGORIES.sort(key=lambda c: c.priority)


# ════════════════════════════════════════════════════════════
# 분류 엔진
# ════════════════════════════════════════════════════════════

def _is_auto_transfer(description):
    return bool(re.search(r"자동이체|자동납부|\d{1,2}월\s*(버스|지하철|교통)\s*\d+건", description, re.IGNORECASE))


def classify(description, tx_type_hint="expense"):
    desc_lower = description.lower()
    auto = _is_auto_transfer(description)

    candidates = []
    for cat in ALL_CATEGORIES:
        if cat.tx_type != "both" and cat.tx_type != tx_type_hint:
            continue
        for pattern in cat._compiled:
            if pattern.search(description):
                candidates.append((cat, "pattern", len(pattern.pattern)))
                break
        else:
            for kw in cat.keywords:
                if kw.lower() in desc_lower:
                    candidates.append((cat, "keyword", len(kw)))
                    break

    if not candidates:
        if auto:
            return _r("FIXED_UNKNOWN", "living", "고정비(미분류)", "자동이체", "기타", [], True, tx_type_hint, "fallback")
        return _r("UNKNOWN", "기타", "미분류", "-", "-", [], False, tx_type_hint, "fallback")

    candidates.sort(key=lambda x: (x[0].priority, -x[2]))
    best, method, _ = candidates[0]
    return _r(best.id, best.L1, best.L2, best.L3, best.L4, best.L5,
              best.is_fixed or auto, best.tx_type, method)


def _r(id_, L1, L2, L3, L4, L5, is_fixed, tx_type, method):
    return {"id": id_, "L1": L1, "L2": L2, "L3": L3, "L4": L4, "L5": L5,
            "is_fixed": is_fixed, "tx_type": tx_type, "matched_by": method}


# ════════════════════════════════════════════════════════════
# 고정비 유틸
# ════════════════════════════════════════════════════════════

def filter_fixed(transactions):
    return [tx for tx in transactions if tx.get("분류", {}).get("is_fixed")]


def fixed_summary(transactions):
    from collections import defaultdict
    summary = defaultdict(lambda: {"총액": 0, "건수": 0, "항목": []})
    for tx in filter_fixed(transactions):
        L2 = tx["분류"]["L2"]
        summary[L2]["총액"] += tx["금액"]
        summary[L2]["건수"] += 1
        summary[L2]["항목"].append(tx["가맹점명"])
    return dict(summary)


# ════════════════════════════════════════════════════════════
# 자가 점검
# ════════════════════════════════════════════════════════════

CSV_PATH = "시니어_거래데이터_샘플.csv"


def run_self_test(csv_path=CSV_PATH):
    import csv
    from collections import defaultdict

    rows = []
    with open(csv_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    unclassified = []
    l1_counts = defaultdict(int)

    print(f"\n[ 전체 거래 분류 결과 — {csv_path} ({len(rows)}건) ]")
    print(f"  {'날짜':<12} {'가맹점명':<28} {'L1':<12} {'L2':<12} {'고정비'}")
    print("  " + "─" * 72)

    for row in rows:
        name = row["가맹점명"].strip()
        date = row["거래일시"].strip()[:10]
        r = classify(name, "expense")
        fixed = "🔒" if r["is_fixed"] else "  "
        l1_counts[r["L1"]] += 1
        if r["L1"] == "기타":
            unclassified.append(name)
        print(f"  {date:<12} {name:<28} {r['L1']:<12} {r['L2']:<12} {fixed}")

    print(f"\n[ L1 분포 ]")
    for l1, cnt in sorted(l1_counts.items(), key=lambda x: -x[1]):
        bar = "█" * cnt
        print(f"  {l1:<12} {cnt:>3}건  {bar}")

    if unclassified:
        print(f"\n[ ⚠️  미분류 항목 ({len(unclassified)}건) — 키워드 추가 검토 ]")
        for name in unclassified:
            print(f"  - {name}")
    else:
        print(f"\n✅ 미분류 항목 없음")


if __name__ == "__main__":
    run_self_test()
