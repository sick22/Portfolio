# ─────────────────────────────────────────────────────────────────────────────
#  app.py – “전국 노인쉼터(경로당) 대시보드” (CSV 버전, 대한민국 줌 맞춘 지도)
#  과제 조건:
#    ① 공공데이터 활용 (CSV)
#    ② Input Widget 2종 이상
#    ③ 위젯 변경 시 차트 동적 반응
#    ④ 시각화 컴포넌트 ≤ 2 (Bar Chart + Map(pydeck))
# ─────────────────────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd
import pydeck as pdk

# 0. 기본 설정 ────────────────────────────────────────────────────────────────
CSV_PATH  = "senior_centers.csv"             # 같은 폴더에 둔 CSV
ENCODINGS = ["utf-8-sig", "cp949", "euc-kr"]  # 인코딩 후보

st.set_page_config(page_title="노인쉼터(경로당) 현황", layout="wide")
st.title("🇰🇷 전국 노인쉼터(경로당) 현황 대시보드")

# 1. CSV 로드 ────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="📂 CSV 불러오는 중...")
def load_csv(path: str) -> pd.DataFrame:
    last_err = None
    for enc in ENCODINGS:
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError as e:
            last_err = e
    raise RuntimeError(f"CSV 인코딩 감지 실패: {last_err}")

df_raw = load_csv(CSV_PATH)

# 2. 컬럼 이름 정규화 ────────────────────────────────────────────────────────
rename_map = {
    "FLCT_NM": "시설명",
    "LCTN_ROAD_NM_ADDR": "도로명주소",
    "LCTN_LOTNO_ADDR": "지번주소",
    "LAT": "lat", "위도": "lat",
    "LOT": "lon", "경도": "lon",
    "경로당명": "시설명",
    "소재지도로명주소": "도로명주소",
    "소재지지번주소": "지번주소",
}
df_raw.rename(
    columns={k: v for k, v in rename_map.items() if k in df_raw.columns},
    inplace=True,
)

# 3. 주소 컬럼(시·도) 자동 탐색 ─────────────────────────────────────────────
road_cols = [c for c in df_raw.columns if "도로명" in c and "주소" in c]
lot_cols  = [c for c in df_raw.columns if "지번"  in c and "주소" in c]

if road_cols:
    addr_col = road_cols[0]
elif lot_cols:
    addr_col = lot_cols[0]
else:
    st.error(
        "⚠️ CSV에서 주소 계열 컬럼을 찾지 못했습니다.\n"
        f"컬럼 목록: {list(df_raw.columns)}"
    )
    st.stop()

df_raw["시도"] = df_raw[addr_col].astype(str).str.split().str[0]

# 4. 위‧경도 컬럼을 lat / lon 으로 통일 ────────────────────────────────────
lat_candidates = [c for c in df_raw.columns if c.lower() in {"lat", "latitude", "위도"}]
lon_candidates = [c for c in df_raw.columns if c.lower() in {"lon", "long", "lng", "longitude", "경도"}]

if lat_candidates and lon_candidates:
    df_raw.rename(
        columns={lat_candidates[0]: "lat", lon_candidates[0]: "lon"},
        inplace=True,
    )

df_raw[["lat", "lon"]] = df_raw[["lat", "lon"]].apply(
    pd.to_numeric, errors="coerce"
)

# 5. Input Widgets (시·도 + 키워드) ─────────────────────────────────────────
c1, c2 = st.columns([1, 2])
with c1:
    sel_sido = st.selectbox(
        "시·도 선택",
        ["(전국)"] + sorted(df_raw["시도"].dropna().unique()),
    )
with c2:
    keyword = st.text_input("키워드(시설명/주소) 검색", "")

# 6. 필터링 ────────────────────────────────────────────────────────────────
df = df_raw.copy()
if sel_sido != "(전국)":
    df = df[df["시도"] == sel_sido]

if keyword:
    mask = (
        df["시설명"].str.contains(keyword, na=False, case=False)
        | df[addr_col].str.contains(keyword, na=False, case=False)
    )
    df = df[mask]

st.caption(f"🔎 필터링 결과: **{len(df):,} 개소**")

# 7. 시각화 (Bar Chart + Pydeck Map) ──────────────────────────────────────
# 7-1 Bar Chart (시·도별 개수)
bar = df.groupby("시도").size().sort_values(ascending=False)
st.bar_chart(bar)

# 7-2 Map — 대한민국에 맞춰 초기 줌/중심 설정
if {"lat", "lon"} <= set(df.columns):
    # 한반도 좌표 범위로 이상치 제거
    korea = df.query("33 <= lat <= 39 and 124 <= lon <= 132").dropna(subset=["lat", "lon"])
    if korea.empty:
        st.info("⚠️ 한반도 범위 내 위·경도 데이터가 없어 지도를 표시할 수 없습니다.")
    else:
        view_state = pdk.ViewState(
            latitude=korea["lat"].mean(),
            longitude=korea["lon"].mean(),
            zoom=7,         # 6~8 사이로 조정해 보세요
            pitch=0,
        )

        layer = pdk.Layer(
            "ScatterplotLayer",
            data=korea,
            get_position="[lon, lat]",
            get_radius=200,
            get_fill_color=[0, 128, 255],
            pickable=True,
        )

        tooltip = {"text": "{시설명}\n{도로명주소}"}
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip))
else:
    st.info("⚠️ 위·경도 정보가 없어 지도를 표시할 수 없습니다.")

# 8. CSV 다운로드 (옵션) ───────────────────────────────────────────────────
st.download_button(
    label="💾 현재 결과 CSV 내려받기",
    data=df.to_csv(index=False).encode("utf-8-sig"),
    file_name="senior_centers_filtered.csv",
    mime="text/csv",
)