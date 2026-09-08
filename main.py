import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import re
from datetime import date, timedelta


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="학교 급식 칼로리 연구소",
    page_icon="🐷",
    layout="wide",
    initial_sidebar_state="expanded"
)

API_BASE = "https://open.neis.go.kr/hub"

DANGGOK = {
    "학교명": "당곡고등학교",
    "교육청코드": "B10",
    "학교코드": "7010073",
    "주소": "서울특별시 관악구"
}


# =========================================================
# 디자인
# =========================================================

st.markdown("""
<style>

.stApp {
    background-color: #f7f8fc;
}

.main-title {
    font-size: 43px;
    font-weight: 850;
    color: #202534;
    margin-bottom: 4px;
}

.main-subtitle {
    font-size: 17px;
    color: #747987;
    margin-bottom: 25px;
}

.intro-card {
    background: white;
    padding: 24px 28px;
    border-radius: 20px;
    border: 1px solid #e9ebf2;
    box-shadow: 0 4px 16px rgba(0,0,0,0.04);
    margin-bottom: 22px;
}

.result-card {
    background: white;
    padding: 21px;
    border-radius: 18px;
    border: 1px solid #e7e9f0;
    box-shadow: 0 3px 12px rgba(0,0,0,0.04);
    min-height: 135px;
}

.result-title {
    font-size: 14px;
    color: #777d8a;
    margin-bottom: 8px;
}

.result-value {
    font-size: 25px;
    font-weight: 800;
    color: #252938;
}

.result-small {
    font-size: 13px;
    color: #888e9b;
    margin-top: 6px;
}

.summary-box {
    background: linear-gradient(
        135deg,
        #fff6ed 0%,
        #fffdfa 100%
    );
    border: 1px solid #f0dcc9;
    border-radius: 20px;
    padding: 25px 28px;
    margin: 18px 0 25px 0;
}

.summary-title {
    font-size: 23px;
    font-weight: 800;
    margin-bottom: 12px;
}

.summary-text {
    font-size: 16px;
    line-height: 1.85;
    color: #424754;
}

.info-box {
    background: white;
    border: 1px solid #e7e9f0;
    border-radius: 18px;
    padding: 20px 24px;
    margin: 12px 0;
}

.section-title {
    font-size: 25px;
    font-weight: 800;
    color: #252938;
    margin-top: 30px;
    margin-bottom: 14px;
}

section[data-testid="stSidebar"] {
    background-color: white;
}

.stButton > button {
    border-radius: 12px;
    font-weight: 700;
}

div[data-baseweb="select"] > div {
    border-radius: 12px;
}

.footer {
    text-align: center;
    color: #969ba7;
    font-size: 13px;
    padding: 35px 0 15px 0;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# API KEY
# =========================================================

try:
    API_KEY = st.secrets["NEIS_API_KEY"]
except Exception:
    API_KEY = ""

if not API_KEY:

    st.error("🔑 NEIS API 인증키가 설정되지 않았습니다.")

    st.info("""
    Streamlit Cloud의 **Settings → Secrets**에 다음과 같이 입력하세요.

    ```toml
    NEIS_API_KEY = "발급받은_인증키"
    ```
    """)

    st.stop()


# =========================================================
# Session State
# =========================================================

if "school_catalog" not in st.session_state:

    st.session_state.school_catalog = {
        "당곡고등학교": DANGGOK
    }

if "selected_schools" not in st.session_state:

    st.session_state.selected_schools = [
        "당곡고등학교"
    ]


# =========================================================
# 학교 검색
# =========================================================

@st.cache_data(ttl=3600)
def search_school_api(school_name, api_key):

    url = f"{API_BASE}/schoolInfo"

    params = {
        "KEY": api_key,
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "SCHUL_NM": school_name
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        response.raise_for_status()
        data = response.json()

        if "schoolInfo" not in data:
            return pd.DataFrame()

        rows = data["schoolInfo"][1].get("row", [])

        result = []

        for row in rows:

            if row.get("SCHUL_KND_SC_NM") != "고등학교":
                continue

            result.append({
                "학교명": row.get("SCHUL_NM", ""),
                "교육청": row.get("ATPT_OFCDC_SC_NM", ""),
                "교육청코드": row.get("ATPT_OFCDC_SC_CODE", ""),
                "학교코드": row.get("SD_SCHUL_CODE", ""),
                "주소": row.get("ORG_RDNMA", "")
            })

        return pd.DataFrame(result)

    except Exception:

        return pd.DataFrame()


# =========================================================
# 계절 판별
# =========================================================

def get_season(month):

    if month in [3, 4, 5]:
        return "🌸 봄"

    elif month in [6, 7, 8]:
        return "☀️ 여름"

    elif month in [9, 10, 11]:
        return "🍂 가을"

    else:
        return "❄️ 겨울"


# =========================================================
# 급식 API
# =========================================================

@st.cache_data(ttl=1800)
def get_meal_data(
    school_code,
    office_code,
    start_date,
    end_date,
    api_key
):

    url = f"{API_BASE}/mealServiceDietInfo"

    all_rows = []
    page = 1

    while True:

        params = {
            "KEY": api_key,
            "Type": "json",
            "pIndex": page,
            "pSize": 1000,
            "ATPT_OFCDC_SC_CODE": office_code,
            "SD_SCHUL_CODE": school_code,

            # 중요!
            # MMEAL_SC_CODE를 지정하지 않아서
            # 중식/석식 등을 모두 가져옴

            "MLSV_FROM_YMD": start_date.strftime("%Y%m%d"),
            "MLSV_TO_YMD": end_date.strftime("%Y%m%d")
        }

        try:

            response = requests.get(
                url,
                params=params,
                timeout=20
            )

            response.raise_for_status()
            data = response.json()

        except Exception:

            break

        if "mealServiceDietInfo" not in data:
            break

        try:
            rows = data[
                "mealServiceDietInfo"
            ][1].get("row", [])
        except Exception:
            break

        if not rows:
            break

        all_rows.extend(rows)

        if len(rows) < 1000:
            break

        page += 1

        if page > 10:
            break


    result = []

    for row in all_rows:

        calorie_text = row.get(
            "CAL_INFO",
            ""
        )

        match = re.search(
            r"([\d,]+(?:\.\d+)?)",
            calorie_text
        )

        if not match:
            continue

        try:

            calorie = float(
                match.group(1).replace(",", "")
            )

        except Exception:

            continue

        meal_date = pd.to_datetime(
            row.get("MLSV_YMD"),
            format="%Y%m%d",
            errors="coerce"
        )

        if pd.isna(meal_date):
            continue

        meal_name = row.get(
            "MMEAL_SC_NM",
            ""
        )

        result.append({
            "학교명": row.get("SCHUL_NM", ""),
            "급식일자": meal_date,
            "급식명": meal_name,
            "칼로리": calorie,
            "메뉴": row.get("DDISH_NM", ""),
            "영양정보": row.get("NTR_INFO", "")
        })

    return pd.DataFrame(result)


# =========================================================
# 제목
# =========================================================

st.markdown(
    '<div class="main-title">'
    '🍱 학교 급식 칼로리 연구소 🐷'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="main-subtitle">'
    'NEIS 데이터를 이용해 학교 · 계절 · 중식과 석식에 따른 '
    '급식 칼로리의 차이를 분석해보세요.'
    '</div>',
    unsafe_allow_html=True
)

st.markdown("""
<div class="intro-card">

<b>🐷 어떤 것을 알아볼 수 있나요?</b><br><br>

🏫 어느 학교의 평균 급식 칼로리가 높을까?<br>
🌸 계절에 따라 급식 칼로리가 달라질까?<br>
🍱 중식과 🌙 석식 중 어느 쪽의 칼로리가 높을까?<br>
📈 날짜에 따라 급식 칼로리는 어떻게 변할까?

</div>
""", unsafe_allow_html=True)


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown("## ⚙️ 분석 설정")

    st.markdown("### 📅 분석 기간")

    today = date.today()

    # 계절 비교를 위해 기본 기간을
    # 현재 연도 1월 1일부터 오늘까지로 설정
    default_start = date(
        today.year,
        1,
        1
    )

    start_date = st.date_input(
        "시작일",
        value=default_start
    )

    end_date = st.date_input(
        "종료일",
        value=today
    )

    if start_date > end_date:

        st.error(
            "시작일이 종료일보다 늦습니다."
        )

        st.stop()


    st.markdown("---")

    st.markdown("### 🏫 학교 추가")

    school_search = st.text_input(
        "학교명을 검색하세요",
        placeholder="예: 서울고등학교"
    )

    if school_search:

        search_result = search_school_api(
            school_search,
            API_KEY
        )

        if search_result.empty:

            st.warning(
                "검색된 고등학교가 없습니다."
            )

        else:

            # 같은 이름 학교가 있을 수 있으므로
            # 학교명 + 주소 표시
            search_result = search_result.copy()

            search_result["표시명"] = (
                search_result["학교명"]
                + " · "
                + search_result["주소"]
            )

            selected_display = st.selectbox(
                "검색 결과",
                search_result["표시명"].tolist()
            )

            selected_info = search_result[
                search_result["표시명"]
                == selected_display
            ].iloc[0]

            st.caption(
                f"📍 {selected_info['주소']}"
            )

            if st.button(
                "➕ 비교 학교에 추가",
                use_container_width=True
            ):

                school_name = selected_info[
                    "학교명"
                ]

                school_data = {
                    "학교명": school_name,
                    "교육청코드": selected_info[
                        "교육청코드"
                    ],
                    "학교코드": selected_info[
                        "학교코드"
                    ],
                    "주소": selected_info[
                        "주소"
                    ]
                }

                st.session_state.school_catalog[
                    school_name
                ] = school_data

                if (
                    school_name
                    not in
                    st.session_state.selected_schools
                ):

                    st.session_state.selected_schools.append(
                        school_name
                    )

                    st.success(
                        f"🐷 {school_name} 추가 완료!"
                    )


    st.markdown("---")

    st.markdown("### 🐷 비교할 학교")

    available_schools = list(
        st.session_state.school_catalog.keys()
    )

    selected_schools = st.multiselect(
        "학교를 선택하세요",
        options=available_schools,
        default=[
            school
            for school
            in st.session_state.selected_schools
            if school in available_schools
        ]
    )

    st.session_state.selected_schools = (
        selected_schools
    )

    st.caption(
        f"현재 {len(selected_schools)}개 학교 선택"
    )

    if len(selected_schools) < 3:

        st.warning(
            "💡 학교 비교는 3개 이상을 선택하면 "
            "더 의미 있게 볼 수 있어요."
        )


    st.markdown("---")

    analyze_button = st.button(
        "🔍 급식 데이터 분석하기",
        type="primary",
        use_container_width=True
    )


# =========================================================
# 데이터 수집
# =========================================================

if analyze_button:

    if len(selected_schools) == 0:

        st.error(
            "학교를 최소 1개 선택해주세요."
        )

        st.stop()

    all_data = []

    progress = st.progress(0)
    status = st.empty()

    total = len(selected_schools)

    for index, school_name in enumerate(
        selected_schools
    ):

        school = st.session_state.school_catalog[
            school_name
        ]

        status.write(
            f"📡 {school_name} 급식 데이터를 가져오는 중..."
        )

        data = get_meal_data(
            school["학교코드"],
            school["교육청코드"],
            start_date,
            end_date,
            API_KEY
        )

        if not data.empty:
            all_data.append(data)

        progress.progress(
            (index + 1) / total
        )

    progress.empty()
    status.empty()

    if not all_data:

        st.error(
            "😥 해당 기간의 급식 데이터를 찾지 못했습니다."
        )

        st.stop()

    df = pd.concat(
        all_data,
        ignore_index=True
    )

    df["계절"] = df[
        "급식일자"
    ].dt.month.apply(
        get_season
    )

    df = df.sort_values(
        ["급식일자", "학교명"]
    )

    st.session_state.meal_data = df


# =========================================================
# 결과
# =========================================================

if "meal_data" in st.session_state:

    df = st.session_state.meal_data.copy()


    # =====================================================
    # 중식 데이터
    # =====================================================

    lunch_df = df[
        df["급식명"].str.contains(
            "중식",
            na=False
        )
    ].copy()


    # =====================================================
    # 학교별 평균
    # 학교 비교는 중식 기준으로 통일
    # =====================================================

    if not lunch_df.empty:

        school_base_df = lunch_df

    else:

        school_base_df = df


    summary = (
        school_base_df
        .groupby("학교명")
        .agg(
            평균칼로리=("칼로리", "mean"),
            최고칼로리=("칼로리", "max"),
            최저칼로리=("칼로리", "min"),
            급식일수=("급식일자", "nunique")
        )
        .reset_index()
    )

    for col in [
        "평균칼로리",
        "최고칼로리",
        "최저칼로리"
    ]:

        summary[col] = (
            summary[col].round(1)
        )

    summary = summary.sort_values(
        "평균칼로리",
        ascending=False
    ).reset_index(drop=True)


    # =====================================================
    # 핵심 결과
    # =====================================================

    st.markdown(
        '<div class="section-title">'
        '📊 분석 결과 한눈에 보기'
        '</div>',
        unsafe_allow_html=True
    )

    highest_school = summary.iloc[0]
    lowest_school = summary.iloc[-1]

    overall_average = (
        school_base_df["칼로리"].mean()
    )

    total_meals = len(df)

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.markdown(
            f"""
            <div class="result-card">
                <div class="result-title">
                    🏆 평균 칼로리 1위
                </div>
                <div class="result-value">
                    {highest_school["학교명"]}
                </div>
                <div class="result-small">
                    {highest_school["평균칼로리"]:.1f} kcal
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col2:

        st.markdown(
            f"""
            <div class="result-card">
                <div class="result-title">
                    🌱 평균 칼로리 최저
                </div>
                <div class="result-value">
                    {lowest_school["학교명"]}
                </div>
                <div class="result-small">
                    {lowest_school["평균칼로리"]:.1f} kcal
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col3:

        st.markdown(
            f"""
            <div class="result-card">
                <div class="result-title">
                    🍽️ 전체 평균
                </div>
                <div class="result-value">
                    {overall_average:.1f} kcal
                </div>
                <div class="result-small">
                    학교 비교 기준
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col4:

        st.markdown(
            f"""
            <div class="result-card">
                <div class="result-title">
                    📚 분석 데이터
                </div>
                <div class="result-value">
                    {total_meals}건
                </div>
                <div class="result-small">
                    수집된 급식 기록
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


    # =====================================================
    # 자동 분석
    # =====================================================

    danggok = summary[
        summary["학교명"]
        == "당곡고등학교"
    ]

    if not danggok.empty:

        danggok_avg = danggok.iloc[0][
            "평균칼로리"
        ]

        difference = (
            highest_school["평균칼로리"]
            - danggok_avg
        )

        if (
            highest_school["학교명"]
            == "당곡고등학교"
        ):

            message = (
                "🐷 <b>당곡고등학교가 비교 학교 중 "
                "평균 급식 칼로리가 가장 높았습니다.</b>"
                f"<br><br>평균은 "
                f"<b>{danggok_avg:.1f} kcal</b>입니다."
            )

        else:

            message = (
                f"🐷 당곡고등학교의 평균 급식 칼로리는 "
                f"<b>{danggok_avg:.1f} kcal</b>입니다."
                f"<br><br>가장 높은 학교는 "
                f"<b>{highest_school['학교명']}</b>이며 "
                f"당곡고등학교보다 "
                f"<b>{difference:.1f} kcal</b> 높았습니다."
            )

        st.markdown(
            f"""
            <div class="summary-box">
                <div class="summary-title">
                    🐷 이번 분석의 핵심 결과
                </div>
                <div class="summary-text">
                    {message}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


    # =====================================================
    # TAB
    # =====================================================

    tab1, tab2, tab3, tab4 = st.tabs([
        "🏫 학교 비교",
        "🌸 계절 비교",
        "🍱 중식 vs 석식",
        "🔎 상세 데이터"
    ])


    # =====================================================
    # TAB 1 : 학교
    # =====================================================

    with tab1:

        st.markdown(
            "### 🏫 학교별 평균 급식 칼로리"
        )

        st.caption(
            "학교 간 공정한 비교를 위해 "
            "중식 데이터를 기준으로 비교합니다."
        )

        fig_school = px.bar(
            summary,
            x="학교명",
            y="평균칼로리",
            text="평균칼로리",
            labels={
                "학교명": "학교",
                "평균칼로리": "평균 칼로리 (kcal)"
            },
            title="학교별 평균 중식 칼로리"
        )

        fig_school.update_traces(
            texttemplate="%{text:.1f} kcal",
            textposition="outside"
        )

        fig_school.update_layout(
            height=520,
            plot_bgcolor="white",
            paper_bgcolor="white"
        )

        st.plotly_chart(
            fig_school,
            use_container_width=True
        )


        st.markdown(
            "### 📈 날짜별 칼로리 변화"
        )

        fig_line = px.line(
            school_base_df,
            x="급식일자",
            y="칼로리",
            color="학교명",
            markers=True,
            labels={
                "급식일자": "날짜",
                "칼로리": "칼로리 (kcal)",
                "학교명": "학교"
            }
        )

        fig_line.update_layout(
            height=500,
            plot_bgcolor="white",
            paper_bgcolor="white",
            hovermode="x unified"
        )

        st.plotly_chart(
            fig_line,
            use_container_width=True
        )


        st.markdown(
            "### 📋 학교별 통계"
        )

        display_summary = summary.copy()

        display_summary.columns = [
            "학교명",
            "평균 칼로리",
            "최고 칼로리",
            "최저 칼로리",
            "급식일수"
        ]

        st.dataframe(
            display_summary,
            use_container_width=True,
            hide_index=True
        )


    # =====================================================
    # TAB 2 : 계절
    # =====================================================

    with tab2:

        st.markdown(
            "## 🌸☀️🍂❄️ 계절별 칼로리 비교"
        )

        st.write(
            "급식 날짜를 기준으로 봄·여름·가을·겨울을 "
            "나누어 평균 칼로리를 비교합니다."
        )

        st.caption(
            "🌸 봄: 3~5월 · ☀️ 여름: 6~8월 · "
            "🍂 가을: 9~11월 · ❄️ 겨울: 12~2월"
        )


        # 중식 기준 계절 분석
        season_source = (
            lunch_df
            if not lunch_df.empty
            else df
        )

        season_order = [
            "🌸 봄",
            "☀️ 여름",
            "🍂 가을",
            "❄️ 겨울"
        ]

        season_summary = (
            season_source
            .groupby("계절")
            .agg(
                평균칼로리=("칼로리", "mean"),
                급식수=("칼로리", "count")
            )
            .reset_index()
        )

        season_summary[
            "평균칼로리"
        ] = season_summary[
            "평균칼로리"
        ].round(1)

        season_summary["계절"] = pd.Categorical(
            season_summary["계절"],
            categories=season_order,
            ordered=True
        )

        season_summary = (
            season_summary
            .sort_values("계절")
        )


        if not season_summary.empty:

            season_high = (
                season_summary
                .sort_values(
                    "평균칼로리",
                    ascending=False
                )
                .iloc[0]
            )

            season_low = (
                season_summary
                .sort_values(
                    "평균칼로리"
                )
                .iloc[0]
            )

            c1, c2 = st.columns(2)

            with c1:

                st.metric(
                    "🔥 평균 칼로리가 가장 높은 계절",
                    str(season_high["계절"]),
                    f"{season_high['평균칼로리']:.1f} kcal"
                )

            with c2:

                st.metric(
                    "🌱 평균 칼로리가 가장 낮은 계절",
                    str(season_low["계절"]),
                    f"{season_low['평균칼로리']:.1f} kcal"
                )


            st.markdown(
                f"""
                <div class="summary-box">
                    <div class="summary-title">
                        🌸 계절 분석 결과
                    </div>

                    <div class="summary-text">

                    선택한 기간의 데이터에서는
                    <b>{season_high["계절"]}</b>의 평균 급식 칼로리가
                    <b>{season_high["평균칼로리"]:.1f} kcal</b>로
                    가장 높았습니다.

                    <br><br>

                    반대로 <b>{season_low["계절"]}</b>은
                    <b>{season_low["평균칼로리"]:.1f} kcal</b>로
                    가장 낮았습니다.

                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )


            fig_season = px.bar(
                season_summary,
                x="계절",
                y="평균칼로리",
                text="평균칼로리",
                category_orders={
                    "계절": season_order
                },
                labels={
                    "계절": "계절",
                    "평균칼로리": "평균 칼로리 (kcal)"
                },
                title="🌸 계절별 평균 급식 칼로리"
            )

            fig_season.update_traces(
                texttemplate="%{text:.1f} kcal",
                textposition="outside"
            )

            fig_season.update_layout(
                height=500,
                plot_bgcolor="white",
                paper_bgcolor="white"
            )

            st.plotly_chart(
                fig_season,
                use_container_width=True
            )


            # 학교 + 계절 비교
            st.markdown(
                "### 🏫 학교별 계절 변화"
            )

            school_season = (
                season_source
                .groupby(
                    ["학교명", "계절"]
                )["칼로리"]
                .mean()
                .reset_index()
            )

            school_season[
                "칼로리"
            ] = school_season[
                "칼로리"
            ].round(1)

            school_season[
                "계절"
            ] = pd.Categorical(
                school_season["계절"],
                categories=season_order,
                ordered=True
            )

            school_season = (
                school_season
                .sort_values("계절")
            )

            fig_school_season = px.line(
                school_season,
                x="계절",
                y="칼로리",
                color="학교명",
                markers=True,
                category_orders={
                    "계절": season_order
                },
                labels={
                    "칼로리": "평균 칼로리 (kcal)",
                    "학교명": "학교"
                },
                title="학교별 계절 평균 칼로리 변화"
            )

            fig_school_season.update_layout(
                height=520,
                plot_bgcolor="white",
                paper_bgcolor="white"
            )

            st.plotly_chart(
                fig_school_season,
                use_container_width=True
            )

        else:

            st.warning(
                "계절 분석에 사용할 데이터가 없습니다."
            )


    # =====================================================
    # TAB 3 : 중식 VS 석식
    # =====================================================

    with tab3:

        st.markdown(
            "## 🍱 중식 vs 🌙 석식"
        )

        st.write(
            "같은 분석 기간에 제공된 중식과 석식의 "
            "평균 칼로리를 비교합니다."
        )


        meal_compare = df[
            df["급식명"].str.contains(
                "중식|석식",
                regex=True,
                na=False
            )
        ].copy()


        if meal_compare.empty:

            st.warning(
                "중식 또는 석식 데이터가 없습니다."
            )

        else:

            meal_summary = (
                meal_compare
                .groupby("급식명")
                .agg(
                    평균칼로리=("칼로리", "mean"),
                    급식수=("칼로리", "count")
                )
                .reset_index()
            )

            meal_summary[
                "평균칼로리"
            ] = meal_summary[
                "평균칼로리"
            ].round(1)


            lunch_result = meal_summary[
                meal_summary["급식명"].str.contains(
                    "중식",
                    na=False
                )
            ]

            dinner_result = meal_summary[
                meal_summary["급식명"].str.contains(
                    "석식",
                    na=False
                )
            ]


            c1, c2 = st.columns(2)

            with c1:

                if not lunch_result.empty:

                    lunch_avg = (
                        lunch_result.iloc[0][
                            "평균칼로리"
                        ]
                    )

                    st.metric(
                        "🍱 중식 평균",
                        f"{lunch_avg:.1f} kcal"
                    )

                else:

                    st.metric(
                        "🍱 중식 평균",
                        "데이터 없음"
                    )


            with c2:

                if not dinner_result.empty:

                    dinner_avg = (
                        dinner_result.iloc[0][
                            "평균칼로리"
                        ]
                    )

                    st.metric(
                        "🌙 석식 평균",
                        f"{dinner_avg:.1f} kcal"
                    )

                else:

                    st.metric(
                        "🌙 석식 평균",
                        "데이터 없음"
                    )


            # 자동 비교 문장
            if (
                not lunch_result.empty
                and
                not dinner_result.empty
            ):

                difference = abs(
                    lunch_avg - dinner_avg
                )

                if dinner_avg > lunch_avg:

                    meal_message = (
                        f"🌙 석식의 평균 칼로리가 "
                        f"중식보다 <b>{difference:.1f} kcal</b> "
                        f"높았습니다."
                    )

                elif lunch_avg > dinner_avg:

                    meal_message = (
                        f"🍱 중식의 평균 칼로리가 "
                        f"석식보다 <b>{difference:.1f} kcal</b> "
                        f"높았습니다."
                    )

                else:

                    meal_message = (
                        "🍱 중식과 🌙 석식의 평균 칼로리가 "
                        "같았습니다."
                    )

                st.markdown(
                    f"""
                    <div class="summary-box">

                        <div class="summary-title">
                            🐷 중식·석식 분석 결과
                        </div>

                        <div class="summary-text">

                            {meal_message}

                            <br><br>

                            🍱 중식 평균:
                            <b>{lunch_avg:.1f} kcal</b><br>

                            🌙 석식 평균:
                            <b>{dinner_avg:.1f} kcal</b>

                        </div>

                    </div>
                    """,
                    unsafe_allow_html=True
                )


            fig_meal = px.bar(
                meal_summary,
                x="급식명",
                y="평균칼로리",
                text="평균칼로리",
                labels={
                    "급식명": "식사",
                    "평균칼로리": "평균 칼로리 (kcal)"
                },
                title="🍱 중식과 🌙 석식 평균 칼로리 비교"
            )

            fig_meal.update_traces(
                texttemplate="%{text:.1f} kcal",
                textposition="outside"
            )

            fig_meal.update_layout(
                height=500,
                plot_bgcolor="white",
                paper_bgcolor="white"
            )

            st.plotly_chart(
                fig_meal,
                use_container_width=True
            )


            # 학교별 중식/석식
            st.markdown(
                "### 🏫 학교별 중식·석식 비교"
            )

            school_meal = (
                meal_compare
                .groupby(
                    ["학교명", "급식명"]
                )["칼로리"]
                .mean()
                .reset_index()
            )

            school_meal[
                "칼로리"
            ] = school_meal[
                "칼로리"
            ].round(1)

            fig_school_meal = px.bar(
                school_meal,
                x="학교명",
                y="칼로리",
                color="급식명",
                barmode="group",
                text_auto=".1f",
                labels={
                    "학교명": "학교",
                    "칼로리": "평균 칼로리 (kcal)",
                    "급식명": "식사"
                },
                title="학교별 중식·석식 평균 칼로리"
            )

            fig_school_meal.update_layout(
                height=520,
                plot_bgcolor="white",
                paper_bgcolor="white"
            )

            st.plotly_chart(
                fig_school_meal,
                use_container_width=True
            )


            # 학교별 데이터 표
            st.dataframe(
                school_meal,
                use_container_width=True,
                hide_index=True
            )


    # =====================================================
    # TAB 4 : 상세 데이터
    # =====================================================

    with tab4:

        st.markdown(
            "## 🔎 상세 데이터"
        )

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )


        # 최고 칼로리 급식
        highest_meal = df.loc[
            df["칼로리"].idxmax()
        ]

        st.markdown(
            "### 🔥 가장 칼로리가 높았던 급식"
        )

        st.write(
            f"🏫 **{highest_meal['학교명']}**"
        )

        st.write(
            f"📅 **{highest_meal['급식일자'].strftime('%Y-%m-%d')}**"
        )

        st.write(
            f"🍽️ **{highest_meal['급식명']}**"
        )

        st.write(
            f"🔥 **{highest_meal['칼로리']:.1f} kcal**"
        )

        st.markdown(
            "#### 🍚 메뉴"
        )

        menu_text = str(
            highest_meal["메뉴"]
        ).replace(
            "<br/>",
            " · "
        )

        st.write(menu_text)


# =========================================================
# 분석 전
# =========================================================

else:

    st.markdown("""
    <div class="summary-box">

        <div class="summary-title">
            🐷 급식 분석을 시작해볼까요?
        </div>

        <div class="summary-text">

            왼쪽에서 분석 기간과 학교를 선택한 후
            <b>🔍 급식 데이터 분석하기</b>를 눌러주세요.

            <br><br>

            🏫 <b>학교 비교</b> — 어느 학교의 평균 칼로리가 높을까?<br>
            🌸 <b>계절 비교</b> — 계절에 따라 칼로리가 달라질까?<br>
            🍱 <b>중식 vs 석식</b> — 어느 식사의 칼로리가 높을까?<br>
            📈 <b>날짜별 변화</b> — 급식 칼로리는 어떻게 변할까?

        </div>

    </div>
    """, unsafe_allow_html=True)


# =========================================================
# Footer
# =========================================================

st.markdown("""
<div class="footer">

🐷 학교 급식 칼로리 연구소<br>
NEIS 학교급식 데이터 활용 · 교육부 및 시도교육청 제공

</div>
""", unsafe_allow_html=True)
