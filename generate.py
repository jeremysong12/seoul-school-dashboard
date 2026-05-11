"""
generate.py
===========
CSV 데이터를 읽어 dashboard.html을 생성하는 스크립트

필요 파일 (같은 폴더에 위치):
  - template.html                       : HTML 템플릿 (placeholder 포함)
  - 학교별_폐교위험_요약.csv             : 학교별 최종 위험등급 및 연도 정보 (최신)
  - 학교_신입생예측_final.csv            : 학교별 연도별 신입생 예측 (최신)
  - 폐교위험학교_군집결과.csv            : 폐교위험 학교 군집 분석 결과 (최신)
  - yearly_risk_school_clusters_1km.csv : 위경도 좌표 조회용 (위치 데이터만 사용)
  - facilities.json                     : 시설 위치 좌표 (도서관·청소년·노인)

실행:
  python generate.py

출력:
  dashboard.html
"""

import json
import math
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, mapping

# ── 설정 ──────────────────────────────────────────────────────────────────
RISK_YEARS   = [2027, 2028, 2029, 2030, 2031, 2032, 2033]
ALL_YEARS    = [2027, 2028, 2029, 2030, 2031, 2032, 2033]
TOTAL        = 565

# 폐교위험 등급 제외 학교 (폐교위험학교_군집결과.csv 기준 + 수동 제외)
# 위례초(B000002172): 군집결과 미포함, 진관초(B000001884): 군집결과 있으나 제외
DANGER_EXCLUSIONS = {"B000002172", "B000001884"}

# ── 데이터 로드 ───────────────────────────────────────────────────────────
print("데이터 로딩 중...")
df_risk     = pd.read_csv("학교별_폐교위험_요약.csv",              encoding="utf-8-sig")
df_pred     = pd.read_csv("학교_신입생예측_final.csv",             encoding="utf-8-sig")
df_clus     = pd.read_csv("폐교위험학교_군집결과.csv",             encoding="utf-8-sig")
df_coord_raw= pd.read_csv("yearly_risk_school_clusters_1km.csv",  encoding="utf-8-sig")

with open("facilities.json", encoding="utf-8") as f:
    fac_data = json.load(f)

# 위경도: 전 연도 통합 (위험학교), 나머지는 NaN
coords = (
    df_coord_raw[["학교ID","위도","경도"]]
    .drop_duplicates("학교ID")
    .set_index("학교ID")
)

# ── 행정동 GeoJSON 로드 + point-in-polygon 헬퍼 ──────────────────────────
print("행정동 GeoJSON 로딩 중...")
gdf_dong = gpd.read_file("seoul_dong.geojson").set_index("ADM_NM")

# 군집결과.csv 동명 → GeoJSON ADM_NM 보정
NAME_FIX = {"종로56가동": "종로5·6가동"}

def get_dong_nm(lat, lng):
    """위경도 좌표 → 행정동 이름 (point-in-polygon)"""
    if lat is None or lng is None or (isinstance(lat, float) and math.isnan(lat)):
        return None
    pt = Point(lng, lat)
    hits = gdf_dong[gdf_dong.geometry.contains(pt)]
    return hits.index[0] if len(hits) > 0 else None

# 군집결과의 동명도 보정하여 딕셔너리화
clus_dong = {
    row["학교ID"]: NAME_FIX.get(row["동명"], row["동명"])
    for _, row in df_clus.iterrows()
}

# 예측 파일에서 연도별 신입생 컬럼 목록
pred_year_cols = {y: f"{y}_신입생_할당" for y in ALL_YEARS}

# ═══════════════════════════════════════════════════════════════════════════
# 1. RAW.schools
#    [학교ID, 학교명, 최종등급, 기준연도, 최초폐교위험연도, 최초고위험연도,
#     위도, 경도, 동이름, 최소신입생수, 최소신입생연도]
# ═══════════════════════════════════════════════════════════════════════════
print("schools 빌드 중...")
df_base = df_risk.merge(
    df_pred[["학교ID"] + list(pred_year_cols.values())].copy(),
    on="학교ID", how="inner"   # 공립(신입생 예측 데이터 있는 학교)만 포함
)

# hakgudo_nm을 동 이름으로 활용 (없으면 빈 문자열)
if "hakgudo_nm" not in df_base.columns:
    df_base["hakgudo_nm"] = ""

schools_list = []
for _, row in df_base.iterrows():
    sid = row["학교ID"]
    lat = coords.loc[sid, "위도"]  if sid in coords.index else None
    lng = coords.loc[sid, "경도"]  if sid in coords.index else None

    # 최소신입생수 = 예측 연도 중 최솟값
    pred_vals = [row[pred_year_cols[y]] for y in ALL_YEARS
                 if pd.notna(row.get(pred_year_cols[y]))]
    min_students = round(min(pred_vals), 1) if pred_vals else None

    sid = row["학교ID"]
    danger_yr = None if (pd.isna(row["최초_폐교위험연도"]) or sid in DANGER_EXCLUSIONS) else int(row["최초_폐교위험연도"])
    high_yr   = None if pd.isna(row["최초_고위험연도"])   else int(row["최초_고위험연도"])

    pred_list = [
        round(float(row[pred_year_cols[y]]), 1) if pd.notna(row.get(pred_year_cols[y])) else None
        for y in ALL_YEARS
    ]

    # 행정동 이름: 군집결과 우선, 없으면 좌표로 계산
    dong_nm = clus_dong.get(sid) or get_dong_nm(
        coords.loc[sid, "위도"] if sid in coords.index else None,
        coords.loc[sid, "경도"] if sid in coords.index else None,
    )

    schools_list.append([
        sid,                              # 0 학교ID
        row["학교명"],                    # 1 학교명
        row["최종_폐교위험등급"],          # 2 최종등급
        danger_yr,                        # 3 최초폐교위험연도
        high_yr,                          # 4 최초고위험연도
        round(lat, 6) if lat else None,   # 5 위도
        round(lng, 6) if lng else None,   # 6 경도
        row.get("hakgudo_nm", ""),        # 7 통학구역 이름 (표시용)
        min_students,                     # 8 최소신입생수
        int(row["최소_신입생수_연도"]) if pd.notna(row["최소_신입생수_연도"]) else None,  # 9 최소신입생연도
        pred_list,                        # 10 연도별 신입생 예측
        dong_nm,                          # 11 행정동 이름 (동 경계 필터용)
    ])

# ═══════════════════════════════════════════════════════════════════════════
# 2. RAW.risk
#    { "2026": { 학교ID: { g, yi, ci, oi, mi, di, yc, cc, oc, mc, dc,
#                          cl, cn, r1, r2, r3 } } }
#    - 등급: 학교별_위험도.csv 의 최초_고위험연도 / 최초_폐교위험연도로 파생
#    - 시설: 폐교위험학교_군집결과.csv (유아/청소년/노인/다문화/장애인)
# ═══════════════════════════════════════════════════════════════════════════
print("risk 빌드 중...")

def safe_int(v):
    return int(v) if pd.notna(v) else 0

def safe_float(v, decimals=3):
    return round(float(v), decimals) if pd.notna(v) else 0.0

def get_grade(row, year):
    sid       = row["학교ID"]
    danger_yr = row["최초_폐교위험연도"]
    high_yr   = row["최초_고위험연도"]
    if sid not in DANGER_EXCLUSIONS and pd.notna(danger_yr) and year >= int(danger_yr):
        return "폐교위험"
    if pd.notna(high_yr) and year >= int(high_yr):
        return "고위험"
    return "안전"

# 군집 시설 데이터 { 학교ID -> dict }
cluster_fac = {}
for _, row in df_clus.iterrows():
    cluster_fac[row["학교ID"]] = {
        "yi": safe_float(row["유아_부족지수"]),
        "ci": safe_float(row["청소년_부족지수"]),
        "oi": safe_float(row["노인_부족지수"]),
        "mi": safe_float(row["다문화_부족지수"]),
        "di": safe_float(row["장애인_부족지수"]),
        "yc": safe_int(row["유아_시설수"]),
        "cc": safe_int(row["청소년_시설수"]),
        "oc": safe_int(row["노인_시설수"]),
        "mc": safe_int(row["다문화_시설수"]),
        "dc": safe_int(row["장애인_시설수"]),
        "cl": int(row["cluster"]),
        "cn": row["cluster_name"],
        "r1": row["추천시설_1순위"],
        "r2": row["추천시설_2순위"],
        "r3": row["추천시설_3순위"],
    }

risk_dict = {}
for year in ALL_YEARS:
    year_dict = {}
    for _, row in df_risk.iterrows():
        sid   = row["학교ID"]
        grade = get_grade(row, year)
        if grade != "안전":
            entry = {"g": grade}
            if sid in cluster_fac:
                entry.update(cluster_fac[sid])
            year_dict[sid] = entry
    risk_dict[str(year)] = year_dict

# ═══════════════════════════════════════════════════════════════════════════
# 3. RAW 조립 (시설에 dong_nm 포함)
# ═══════════════════════════════════════════════════════════════════════════
print("시설 동 계산 중...")
youths_with_dong = [
    [f[0], f[2], f[3], get_dong_nm(f[2], f[3])]   # [name, lat, lng, dong_nm]
    for f in fac_data["youths"]
]
elderlys_with_dong = [
    [f[0], f[1], f[2], get_dong_nm(f[1], f[2])]   # [name, lat, lng, dong_nm]
    for f in fac_data["elderlys"]
]

raw = {
    "schools":    schools_list,
    "risk":       risk_dict,
    "youths":     youths_with_dong,
    "elderlys":   elderlys_with_dong,
    "age_totals": fac_data["age_totals"],
}

# ═══════════════════════════════════════════════════════════════════════════
# 3-b. DONG_GEO  { dong_nm: GeoJSON geometry }
#      학교가 속한 동들의 경계 폴리곤 (동 경계 표시용)
# ═══════════════════════════════════════════════════════════════════════════
print("동 경계 geometry 추출 중...")
school_dong_names = {s[11] for s in schools_list if s[11] is not None}
dong_geo = {}
for dong_nm in school_dong_names:
    if dong_nm in gdf_dong.index:
        geom = gdf_dong.loc[dong_nm, "geometry"]
        dong_geo[dong_nm] = mapping(geom)  # GeoJSON-호환 dict

# ═══════════════════════════════════════════════════════════════════════════
# 4. CLUSTER_META  (새 군집 기준: 장애인/노인/청소년 수요군)
# ═══════════════════════════════════════════════════════════════════════════
print("cluster_meta 빌드 중...")

CLUSTER_DEFS = {
    0: {"color":"#ef4444", "desc":"장애인 시설 수요가 가장 높은 그룹. 장애인복지관 전환 우선 고려"},
    1: {"color":"#f97316", "desc":"노인 시설 수요가 가장 높은 그룹. 경로당·노인복지센터 전환 적합"},
    2: {"color":"#3b82f6", "desc":"청소년 시설 수요가 가장 높은 그룹. 청소년센터·방과후 시설 전환 적합"},
}

FAC_IDX_COLS = ["유아_부족지수","청소년_부족지수","노인_부족지수","다문화_부족지수","장애인_부족지수"]

cluster_meta = []
for c_id, c_def in CLUSTER_DEFS.items():
    sub = df_clus[df_clus["cluster"] == c_id]
    n_schools = len(sub)
    radar = [round(sub[col].mean(), 3) for col in FAC_IDX_COLS]
    name  = sub["cluster_name"].iloc[0] if len(sub) > 0 else f"클러스터 {c_id}"
    r1    = sub["추천시설_1순위"].mode()[0] if len(sub) > 0 else ""
    cluster_meta.append({
        "id":      c_id,
        "name":    name,
        "schools": n_schools,
        "radar":   radar,
        "color":   c_def["color"],
        "desc":    c_def["desc"],
        "top":     r1,
    })

# ═══════════════════════════════════════════════════════════════════════════
# 5. SCHOOL_CLUSTER  { 학교ID: cluster_id }
# ═══════════════════════════════════════════════════════════════════════════
print("school_cluster 빌드 중...")
school_cluster = {}
for _, row in df_clus.iterrows():
    school_cluster[row["학교ID"]] = int(row["cluster"])

# ═══════════════════════════════════════════════════════════════════════════
# 6. 연도별 추이 카운트
# ═══════════════════════════════════════════════════════════════════════════
print("trend counts 빌드 중...")

def count_at_year(df_r, year):
    df_e = df_r[~df_r["학교ID"].isin(DANGER_EXCLUSIONS)]
    danger = int(((df_e["최초_폐교위험연도"].notna()) & (df_e["최초_폐교위험연도"] <= year)).sum())
    high   = int(((df_e["최초_고위험연도"].notna())   & (df_e["최초_고위험연도"]   <= year) &
                  ~((df_e["최초_폐교위험연도"].notna()) & (df_e["최초_폐교위험연도"] <= year))).sum())
    return danger, high

danger_counts = []
high_counts   = []
for y in ALL_YEARS:
    d, h = count_at_year(df_risk, y)
    danger_counts.append(d)
    high_counts.append(h)

# ═══════════════════════════════════════════════════════════════════════════
# 7. JS 문자열 생성
# ═══════════════════════════════════════════════════════════════════════════
print("JS 직렬화 중...")

def to_js(obj):
    """Python 객체를 JS 리터럴로 직렬화 (None → null)"""
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))

raw_js          = f"const RAW = {to_js(raw)};"
cluster_meta_js = f"const CLUSTER_META = {to_js(cluster_meta)};"
school_cluster_js = f"const SCHOOL_CLUSTER = {to_js(school_cluster)};"
trend_js = (
    f"const years={to_js(ALL_YEARS)};\n"
    f"const dangerCounts={to_js(danger_counts)};\n"
    f"const highCounts={to_js(high_counts)};"
)
dong_geo_js = f"const DONG_GEO = {to_js(dong_geo)};"

# ═══════════════════════════════════════════════════════════════════════════
# 8. template.html → dashboard.html
# ═══════════════════════════════════════════════════════════════════════════
print("HTML 주입 중...")
with open("template.html", encoding="utf-8") as f:
    template = f.read()

result = template
result = result.replace("/*__CLUSTER_META__*/",   cluster_meta_js)
result = result.replace("/*__SCHOOL_CLUSTER__*/", school_cluster_js)
result = result.replace("/*__RAW__*/",            raw_js)
result = result.replace("/*__TREND_COUNTS__*/",   trend_js)
result = result.replace("/*__DONG_GEO__*/",       dong_geo_js)

with open("dashboard.html", "w", encoding="utf-8") as f:
    f.write(result)

print(f"\n완료! dashboard.html 생성 ({len(result):,} bytes)")
print(f"  학교 수: {len(schools_list)}")
print(f"  위험 데이터 연도: {list(risk_dict.keys())}")
print(f"  클러스터 매핑: {len(school_cluster)}개 학교")
print(f"  폐교위험 추이: {danger_counts}")
print(f"  고위험 추이:   {high_counts}")