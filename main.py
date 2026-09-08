import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import re
from datetime import date


# ============================================================
# 페이지 기본 설정
# ============================================================

st.set_page_config(
    page_title="학교 급식 칼로리 비교",
    page_icon="🐷",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# 기본 설정
# ============================================================

API_BASE = "https://open.neis.go.kr/hub"


# 당곡고등학교
DANGGOK = {
    "학교명": "당곡고등학교",
    "교육청코드": "B10",
    "학교코드": "7010073",
    "주소": "서울특별시 관악구"
}


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .stApp {
        background-color: #f7f8fc;
    }

    .main-title {
        font-size: 42px;
        font-weight: 800;
        color: #252938;
        margin-bottom: 5px;
    }

    .main-subtitle {
        font-size: 17px;
        color: #707684;
        margin-bottom: 20px;
    }

    .section-title {
        font-size: 25px;
        font-weight: 800;
        color: #252938;
        margin-top: 25px;
        margin-bottom: 10px;
    }

    .small-text {
        color: #777d89;
        font-size: 14px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# API KEY
# ============================================================

try:
    API_KEY = st.secrets["NEIS_API_KEY"]
except Exception:
    API_KEY = ""


if not API_KEY:

    st.error("🔑 NEIS API 인증키가 설정되지 않았습니다.")

    st.info(
        """
        Streamlit Cloud의

        **Settings → Secrets**

        에 아래 형식으로 입력해주세요.

        ```toml
        NEIS_API_KEY = "발급받은_인증키"
        ```
        """
    )

    st.stop()


# ============================================================
# 학교 목록 초기화
# ============================================================

if "school_catalog" not in st.session_state:

    st.session_state.school_catalog = {
        "당곡고등학교": DANGGOK
    }


if "selected_schools" not in st.session_state:

    st.session_state.selected_schools = [
        "당곡고등학교"
    ]


# ============================================================
# 학교 검색 API
# ============================================================

@st.cache_data(ttl=3600)
def search_school(
    school_name,
    api_key
):

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

        rows = data[
            "schoolInfo"
        ][1].get(
            "row",
            []
        )

        result = []

        for row in rows:

            if row.get(
                "SCHUL_KND_SC_NM",
                ""
            ) != "고등학교":

                continue

            result.append(
                {
                    "학교명": row.get(
                        "SCHUL_NM",
                        ""
                    ),
                    "교육청": row.get(
                        "ATPT_OFCDC_SC_NM",
                        ""
                    ),
                    "교육청코드": row.get(
                        "ATPT_OFCDC_SC_CODE",
                        ""
                    ),
                    "학교코드": row.get(
                        "SD_SCHUL_CODE",
                        ""
                    ),
                    "주소": row.get(
                        "ORG_RDNMA",
                        ""
                    )
                }
            )

        return pd.DataFrame(result)

    except Exception:

        return pd.DataFrame()


# ============================================================
# 급식 데이터 API
# ============================================================

@st.cache_data(ttl=1800)
def get_meal_data(
    school_code,
    office_code,
    start_date,
    end_date,
    api_key
):

    url = f"{API_BASE}/mealServiceDietInfo"

    params = {
        "KEY": api_key,
        "Type": "json",
        "pIndex": 1,
        "pSize": 1000,
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,

        # 중요:
        # 중식만 가져오지 않고
        # 조식 / 중식 / 석식을 모두 가져온다.
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

        return pd.DataFrame()

    if "mealServiceDietInfo" not in data:

        return pd.DataFrame()

    try:

        rows = data[
            "mealServiceDietInfo"
        ][1].get(
            "row",
            []
        )

    except Exception:

        return pd.DataFrame()

    result = []

    for row in rows:

        # ----------------------------------------------------
        # 칼로리
        # ----------------------------------------------------

        calorie_text = str(
            row.get(
                "CAL_INFO",
                ""
            )
        )

        match = re.search(
            r"([\d,]+(?:\.\d+)?)",
            calorie_text
        )

        if not match:

            continue

        try:

            calorie = float(
                match.group(1).replace(
                    ",",
                    ""
                )
            )

        except Exception:

            continue

        # ----------------------------------------------------
        # 날짜
        # ----------------------------------------------------

        meal_date = pd.to_datetime(
            row.get(
                "MLSV_YMD",
                ""
            ),
            format="%Y%m%d",
            errors="coerce"
        )

        if pd.isna(meal_date):

            continue

        # ----------------------------------------------------
        # 식사 종류
        # ----------------------------------------------------

        meal_code = str(
            row.get(
                "MMEAL_SC_CODE",
                ""
            )
        )

        meal_name = str(
            row.get(
                "MMEAL_SC_NM",
                ""
            )
        )

        if meal_code == "1":
            meal_type = "조식"
            meal_emoji = "🌅"

        elif meal_code == "2":
            meal_type = "중식"
            meal_emoji = "🌞"

        elif meal_code == "3":
            meal_type = "석식"
            meal_emoji = "🌙"

        else:
            meal_type = meal_name
            meal_emoji = "🍽️"

        # ----------------------------------------------------
        # 저장
        # ----------------------------------------------------

        result.append(
            {
                "학교명": row.get(
                    "SCHUL_NM",
                    ""
                ),
                "급식일자": meal_date,
                "식사코드": meal_code,
                "식사": meal_type,
                "식사표시": f"{meal_emoji} {meal_type}",
                "칼로리": calorie,
                "메뉴": row.get(
                    "DDISH_NM",
                    ""
                ),
                "영양정보": row.get(
                    "NTR_INFO",
                    ""
                )
            }
        )

    return pd.DataFrame(result)


# ============================================================
# 계절 함수
# ============================================================

def get_season(month):

    if month in [3, 4, 5]:

        return "🌸 봄"

    elif month in [6, 7, 8]:

        return "☀️ 여름"

    elif month in [9, 10, 11]:

        return "🍂 가을"

    else:

        return "❄️ 겨울"


# ============================================================
# 제목
# ============================================================

st.markdown(
    '<div class="main-title">🍱 학교 급식 칼로리 비교 🐷</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="main-subtitle">'
    'NEIS 데이터를 활용하여 학교·계절·식사 종류에 따른 급식 칼로리 차이를 분석해보세요.'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# 사용 방법 안내
# ============================================================

with st.container(border=True):

    st.subheader("🐷 이 앱에서 무엇을 알아볼 수 있나요?")

    col1, col2 = st.columns(2)

    with col1:

        st.write(
            "🏫 **학교 비교**  \n"
            "어느 학교의 평균 급식 칼로리가 높을까?"
        )

        st.write(
            "🌸 **계절 비교**  \n"
            "계절에 따라 급식 칼로리가 달라질까?"
        )

    with col2:

        st.write(
            "🌞🌙 **중식 vs 석식**  \n"
            "어느 식사의 평균 칼로리가 높을까?"
        )

        st.write(
            "📈 **날짜별 변화**  \n"
            "날짜에 따라 급식 칼로리는 어떻게 변할까?"
        )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ 분석 설정")

    # --------------------------------------------------------
    # 기간
    # --------------------------------------------------------

    st.subheader("📅 분석 기간")

    today = date.today()

    # 계절 비교가 가능하도록 올해 1월 1일을 기본값으로 설정
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
            "시작일은 종료일보다 빠르거나 같아야 합니다."
        )

        st.stop()

    # --------------------------------------------------------
    # 기본 분석 식사
    # --------------------------------------------------------

    st.subheader("🍽️ 기본 분석 식사")

    analysis_meal = st.radio(
        "학교 평균·계절 분석에 사용할 식사",
        [
            "중식",
            "석식",
            "전체"
        ],
        index=0
    )

    st.caption(
        "💡 학교 간 비교는 식사 종류를 통일하는 것이 공정합니다."
    )

    # --------------------------------------------------------
    # 학교 검색
    # --------------------------------------------------------

    st.divider()

    st.subheader("🏫 학교 추가")

    school_search = st.text_input(
        "학교명을 검색하세요",
        placeholder="예: 서울고등학교"
    )

    if school_search:

        search_result = search_school(
            school_search,
            API_KEY
        )

        if search_result.empty:

            st.warning(
                "🔎 검색된 고등학교가 없습니다."
            )

        else:

            # 학교명 + 교육청을 표시해서 같은 이름의 학교 구분
            search_result = search_result.copy()

            search_result["표시명"] = (
                search_result["학교명"]
                + " · "
                + search_result["교육청"]
            )

            display_options = search_result[
                "표시명"
            ].tolist()

            selected_display = st.selectbox(
                "검색 결과",
                display_options
            )

            selected_row = search_result[
                search_result["표시명"]
                == selected_display
            ].iloc[0]

            st.caption(
                f"📍 {selected_row['주소']}"
            )

            if st.button(
                "➕ 비교 학교에 추가",
                use_container_width=True
            ):

                school_name = selected_row[
                    "학교명"
                ]

                school_data = {
                    "학교명": school_name,
                    "교육청코드": selected_row[
                        "교육청코드"
                    ],
                    "학교코드": selected_row[
                        "학교코드"
                    ],
                    "주소": selected_row[
                        "주소"
                    ]
                }

                st.session_state.school_catalog[
                    school_name
                ] = school_data

                if school_name not in st.session_state.selected_schools:

                    st.session_state.selected_schools.append(
                        school_name
                    )

                    st.success(
                        f"🐷 {school_name} 추가 완료!"
                    )

    # --------------------------------------------------------
    # 학교 선택
    # --------------------------------------------------------

    st.divider()

    st.subheader("🐷 비교할 학교")

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
            "💡 3개 이상의 학교를 선택하면 "
            "학교 간 비교가 더 의미있습니다."
        )

    # --------------------------------------------------------
    # 분석 버튼
    # --------------------------------------------------------

    st.divider()

    analyze_button = st.button(
        "🔍 급식 데이터 분석하기",
        type="primary",
        use_container_width=True
    )


# ============================================================
# 분석 실행
# ============================================================

if analyze_button:

    if len(selected_schools) == 0:

        st.error(
            "🏫 비교할 학교를 최소 1개 선택해주세요."
        )

        st.stop()

    all_data = []

    progress = st.progress(0)

    status = st.empty()

    total = len(
        selected_schools
    )

    for i, school_name in enumerate(
        selected_schools
    ):

        school = st.session_state.school_catalog[
            school_name
        ]

        status.write(
            f"📡 {school_name}의 급식 데이터를 가져오는 중..."
        )

        data = get_meal_data(
            school_code=school[
                "학교코드"
            ],
            office_code=school[
                "교육청코드"
            ],
            start_date=start_date,
            end_date=end_date,
            api_key=API_KEY
        )

        if not data.empty:

            all_data.append(data)

        progress.progress(
            (i + 1) / total
        )

    progress.empty()

    status.empty()

    if not all_data:

        st.error(
            "😥 해당 기간에 급식 데이터를 찾지 못했습니다."
        )

        st.info(
            "분석 기간을 넓혀서 다시 시도해주세요."
        )

        st.stop()

    df = pd.concat(
        all_data,
        ignore_index=True
    )

    # --------------------------------------------------------
    # 계절 추가
    # --------------------------------------------------------

    df["계절"] = df[
        "급식일자"
    ].dt.month.apply(
        get_season
    )

    # --------------------------------------------------------
    # 계절 정렬용 순서
    # --------------------------------------------------------

    season_order = [
        "🌸 봄",
        "☀️ 여름",
        "🍂 가을",
        "❄️ 겨울"
    ]

    df["계절"] = pd.Categorical(
        df["계절"],
        categories=season_order,
        ordered=True
    )

    # 날짜순 정렬
    df = df.sort_values(
        ["급식일자", "학교명"]
    )

    # 저장
    st.session_state.meal_data = df


# ============================================================
# 분석 결과
# ============================================================

if "meal_data" in st.session_state:

    df = st.session_state.meal_data.copy()

    # ========================================================
    # 기본 분석 데이터
    # ========================================================

    if analysis_meal == "중식":

        analysis_df = df[
            df["식사"] == "중식"
        ].copy()

    elif analysis_meal == "석식":

        analysis_df = df[
            df["식사"] == "석식"
        ].copy()

    else:

        analysis_df = df.copy()


    # ========================================================
    # 데이터가 없는 경우
    # ========================================================

    if analysis_df.empty:

        st.error(
            f"😥 선택한 기간에 {analysis_meal} 데이터가 없습니다."
        )

        st.stop()


    # ========================================================
    # 결과 제목
    # ========================================================

    st.markdown(
        '<div class="section-title">'
        '📊 분석 결과 한눈에 보기'
        '</div>',
        unsafe_allow_html=True
    )


    # ========================================================
    # 학교별 통계
    # ========================================================

    summary = (
        analysis_df
        .groupby("학교명")
        .agg(
            평균칼로리=("칼로리", "mean"),
            최고칼로리=("칼로리", "max"),
            최저칼로리=("칼로리", "min"),
            급식일수=("급식일자", "nunique")
        )
        .reset_index()
    )

    summary["평균칼로리"] = (
        summary["평균칼로리"].round(1)
    )

    summary["최고칼로리"] = (
        summary["최고칼로리"].round(1)
    )

    summary["최저칼로리"] = (
        summary["최저칼로리"].round(1)
    )

    summary = summary.sort_values(
        "평균칼로리",
        ascending=False
    ).reset_index(
        drop=True
    )


    # ========================================================
    # 핵심 지표
    # ========================================================

    highest_school = summary.iloc[0]

    lowest_school = summary.iloc[-1]

    overall_average = analysis_df[
        "칼로리"
    ].mean()

    total_meals = len(
        analysis_df
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "🏆 평균 칼로리 1위",
            highest_school["학교명"],
            f"{highest_school['평균칼로리']:.1f} kcal"
        )

    with col2:

        st.metric(
            "🌱 평균 칼로리 최저",
            lowest_school["학교명"],
            f"{lowest_school['평균칼로리']:.1f} kcal"
        )

    with col3:

        st.metric(
            f"🍽️ {analysis_meal} 전체 평균",
            f"{overall_average:.1f} kcal"
        )

    with col4:

        st.metric(
            "📊 분석한 급식",
            f"{total_meals}개"
        )


    # ========================================================
    # 돼지 분석 요약
    # ========================================================

    st.markdown("---")

    st.subheader("🐷 이번 분석의 핵심 결과")

    if len(summary) >= 2:

        difference = (
            highest_school["평균칼로리"]
            - lowest_school["평균칼로리"]
        )

        st.success(
            f"🐷 **{highest_school['학교명']}**의 "
            f"{analysis_meal} 평균 칼로리가 "
            f"**{highest_school['평균칼로리']:.1f} kcal**로 "
            f"가장 높았습니다."
        )

        st.info(
            f"📌 가장 높은 학교와 가장 낮은 학교의 "
            f"평균 칼로리 차이는 "
            f"**{difference:.1f} kcal**입니다."
        )

    else:

        st.info(
            "학교가 1개만 선택되어 학교 간 순위 비교는 할 수 없습니다."
        )


    # ========================================================
    # 당곡고등학교 분석
    # ========================================================

    danggok_data = summary[
        summary["학교명"]
        == "당곡고등학교"
    ]

    if not danggok_data.empty:

        danggok_avg = danggok_data.iloc[0][
            "평균칼로리"
        ]

        rank = (
            summary.index[
                summary["학교명"]
                == "당곡고등학교"
            ][0]
            + 1
        )

        st.subheader(
            "🐷 당곡고등학교 결과"
        )

        col1, col2 = st.columns(2)

        with col1:

            st.metric(
                "당곡고등학교 평균",
                f"{danggok_avg:.1f} kcal"
            )

        with col2:

            st.metric(
                "비교 학교 중 순위",
                f"{rank}위 / {len(summary)}개"
            )

        if rank == 1:

            st.success(
                "🐷 당곡고등학교의 평균 칼로리가 "
                "비교 학교 중 가장 높습니다!"
            )

        elif rank == len(summary):

            st.info(
                "🐷 당곡고등학교의 평균 칼로리가 "
                "비교 학교 중 가장 낮습니다."
            )

        else:

            higher_count = rank - 1

            lower_count = (
                len(summary) - rank
            )

            st.info(
                f"🐷 당곡고등학교보다 평균 칼로리가 높은 학교는 "
                f"**{higher_count}개**, 낮은 학교는 "
                f"**{lower_count}개**입니다."
            )


    # ========================================================
    # ① 학교별 평균 칼로리
    # ========================================================

    st.markdown("---")

    st.markdown(
        '<div class="section-title">'
        '🏫 1. 학교별 평균 급식 칼로리'
        '</div>',
        unsafe_allow_html=True
    )

    fig_bar = px.bar(
        summary,
        x="학교명",
        y="평균칼로리",
        text="평균칼로리",
        labels={
            "학교명": "학교",
            "평균칼로리": "평균 칼로리 (kcal)"
        },
        title=f"{analysis_meal} 학교별 평균 급식 칼로리"
    )

    fig_bar.update_traces(
        texttemplate="%{text:.1f} kcal",
        textposition="outside"
    )

    fig_bar.update_layout(
        height=500,
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(
            l=30,
            r=30,
            t=70,
            b=30
        )
    )

    st.plotly_chart(
        fig_bar,
        use_container_width=True
    )


    # ========================================================
    # ② 계절별 칼로리 비교
    # ========================================================

    st.markdown("---")

    st.markdown(
        '<div class="section-title">'
        '🌸 2. 계절별 급식 칼로리 비교'
        '</div>',
        unsafe_allow_html=True
    )

    season_summary = (
        analysis_df
        .groupby("계절", observed=False)
        .agg(
            평균칼로리=("칼로리", "mean"),
            급식일수=("급식일자", "nunique")
        )
        .reset_index()
    )

    season_summary["평균칼로리"] = (
        season_summary["평균칼로리"]
        .round(1)
    )

    season_summary = season_summary[
        season_summary["급식일수"] > 0
    ]

    if len(season_summary) >= 2:

        fig_season = px.bar(
            season_summary,
            x="계절",
            y="평균칼로리",
            text="평균칼로리",
            labels={
                "계절": "계절",
                "평균칼로리": "평균 칼로리 (kcal)"
            },
            title=f"{analysis_meal} 계절별 평균 급식 칼로리"
        )

        fig_season.update_traces(
            texttemplate="%{text:.1f} kcal",
            textposition="outside"
        )

        fig_season.update_layout(
            height=480,
            plot_bgcolor="white",
            paper_bgcolor="white"
        )

        st.plotly_chart(
            fig_season,
            use_container_width=True
        )

        season_high = season_summary.loc[
            season_summary["평균칼로리"].idxmax()
        ]

        season_low = season_summary.loc[
            season_summary["평균칼로리"].idxmin()
        ]

        season_difference = (
            season_high["평균칼로리"]
            - season_low["평균칼로리"]
        )

        st.success(
            f"🐷 **계절별 분석:** "
            f"평균 칼로리가 가장 높은 계절은 "
            f"**{season_high['계절']} "
            f"({season_high['평균칼로리']:.1f} kcal)**이고, "
            f"가장 낮은 계절은 "
            f"**{season_low['계절']} "
            f"({season_low['평균칼로리']:.1f} kcal)**입니다."
        )

        st.caption(
            f"두 계절의 평균 칼로리 차이는 "
            f"{season_difference:.1f} kcal입니다."
        )

    else:

        st.info(
            "💡 계절을 2개 이상 포함하는 기간을 선택해야 "
            "계절별 비교가 가능합니다."
        )


    # ========================================================
    # ③ 중식 vs 석식
    # ========================================================

    st.markdown("---")

    st.markdown(
        '<div class="section-title">'
        '🌞🌙 3. 중식 vs 석식 칼로리 비교'
        '</div>',
        unsafe_allow_html=True
    )

    meal_compare = (
        df[
            df["식사"].isin(
                ["중식", "석식"]
            )
        ]
        .groupby("식사")
        .agg(
            평균칼로리=("칼로리", "mean"),
            급식수=("칼로리", "count")
        )
        .reset_index()
    )

    meal_order = [
        "중식",
        "석식"
    ]

    meal_compare["식사"] = pd.Categorical(
        meal_compare["식사"],
        categories=meal_order,
        ordered=True
    )

    meal_compare = meal_compare.sort_values(
        "식사"
    )

    if len(meal_compare) >= 2:

        fig_meal = px.bar(
            meal_compare,
            x="식사",
            y="평균칼로리",
            text="평균칼로리",
            labels={
                "식사": "식사 종류",
                "평균칼로리": "평균 칼로리 (kcal)"
            },
            title="중식과 석식의 평균 칼로리 비교"
        )

        fig_meal.update_traces(
            texttemplate="%{text:.1f} kcal",
            textposition="outside"
        )

        fig_meal.update_layout(
            height=450,
            plot_bgcolor="white",
            paper_bgcolor="white"
        )

        st.plotly_chart(
            fig_meal,
            use_container_width=True
        )

        meal_high = meal_compare.loc[
            meal_compare["평균칼로리"].idxmax()
        ]

        meal_low = meal_compare.loc[
            meal_compare["평균칼로리"].idxmin()
        ]

        meal_difference = (
            meal_high["평균칼로리"]
            - meal_low["평균칼로리"]
        )

        st.success(
            f"🐷 **식사별 분석:** "
            f"**{meal_high['식사']}**의 평균 칼로리가 "
            f"**{meal_high['평균칼로리']:.1f} kcal**로 "
            f"더 높았습니다."
        )

        st.caption(
            f"{meal_high['식사']}와 {meal_low['식사']}의 "
            f"평균 칼로리 차이는 "
            f"{meal_difference:.1f} kcal입니다."
        )

    elif len(meal_compare) == 1:

        only_meal = meal_compare.iloc[0]

        st.info(
            f"현재 기간에는 **{only_meal['식사']}** 데이터만 "
            "확인되어 중식과 석식을 비교할 수 없습니다."
        )

    else:

        st.info(
            "현재 기간에 중식·석식 데이터가 없습니다."
        )


    # ========================================================
    # ④ 날짜별 변화
    # ========================================================

    st.markdown("---")

    st.markdown(
        '<div class="section-title">'
        '📈 4. 날짜별 급식 칼로리 변화'
        '</div>',
        unsafe_allow_html=True
    )

    fig_line = px.line(
        analysis_df,
        x="급식일자",
        y="칼로리",
        color="학교명",
        markers=True,
        labels={
            "급식일자": "급식 날짜",
            "칼로리": "칼로리 (kcal)",
            "학교명": "학교"
        },
        title=f"{analysis_meal} 날짜별 급식 칼로리 변화"
    )

    fig_line.update_layout(
        height=520,
        plot_bgcolor="white",
        paper_bgcolor="white",
        hovermode="x unified"
    )

    st.plotly_chart(
        fig_line,
        use_container_width=True
    )


    # ========================================================
    # ⑤ 칼로리 분포
    # ========================================================

    st.markdown("---")

    st.markdown(
        '<div class="section-title">'
        '📦 5. 학교별 칼로리 분포'
        '</div>',
        unsafe_allow_html=True
    )

    fig_box = px.box(
        analysis_df,
        x="학교명",
        y="칼로리",
        color="학교명",
        points="all",
        labels={
            "학교명": "학교",
            "칼로리": "칼로리 (kcal)"
        },
        title=f"{analysis_meal} 학교별 급식 칼로리 분포"
    )

    fig_box.update_layout(
        height=520,
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False
    )

    st.plotly_chart(
        fig_box,
        use_container_width=True
    )


    # ========================================================
    # ⑥ 학교별 상세표
    # ========================================================

    st.markdown("---")

    st.markdown(
        '<div class="section-title">'
        '📋 6. 학교별 상세 분석'
        '</div>',
        unsafe_allow_html=True
    )

    display_summary = summary.copy()

    display_summary.columns = [
        "학교명",
        "평균 칼로리 (kcal)",
        "최고 칼로리 (kcal)",
        "최저 칼로리 (kcal)",
        "급식일수"
    ]

    st.dataframe(
        display_summary,
        use_container_width=True,
        hide_index=True
    )


    # ========================================================
    # ⑦ 가장 칼로리가 높은 급식
    # ========================================================

    st.markdown("---")

    st.markdown(
        '<div class="section-title">'
        '🔥 7. 가장 칼로리가 높았던 급식'
        '</div>',
        unsafe_allow_html=True
    )

    highest_meal = analysis_df.loc[
        analysis_df["칼로리"].idxmax()
    ]

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "🏫 학교",
            highest_meal["학교명"]
        )

    with col2:

        st.metric(
            "🔥 칼로리",
            f"{highest_meal['칼로리']:.1f} kcal"
        )

    with col3:

        st.metric(
            "🍽️ 식사",
            highest_meal["식사"]
        )

    st.write(
        f"📅 **급식 날짜:** "
        f"{highest_meal['급식일자'].strftime('%Y년 %m월 %d일')}"
    )

    with st.expander("🍚 해당 급식 메뉴 보기"):

        menu = str(
            highest_meal["메뉴"]
        )

        menu = menu.replace(
            "<br/>",
            "\n"
        )

        st.write(menu)


    # ========================================================
    # 원자료
    # ========================================================

    with st.expander(
        "🔎 원자료 확인하기"
    ):

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )


else:

    # ========================================================
    # 분석 전 화면
    # ========================================================

    st.markdown("---")

    with st.container(border=True):

        st.subheader(
            "🐷 급식 분석을 시작해볼까요?"
        )

        st.write(
            "왼쪽에서 분석 기간과 비교할 학교를 선택한 후 "
            "**🔍 급식 데이터 분석하기** 버튼을 눌러주세요."
        )

        st.write("")

        st.write(
            "🏫 **학교 비교** — 어느 학교의 평균 칼로리가 높을까?"
        )

        st.write(
            "🌸 **계절 비교** — 계절에 따라 칼로리가 달라질까?"
        )

        st.write(
            "🌞🌙 **중식 vs 석식** — 어느 식사의 칼로리가 높을까?"
        )

        st.write(
            "📈 **날짜별 변화** — 급식 칼로리는 어떻게 변할까?"
        )

        st.write("")

        st.info(
            "💡 계절별 분석을 위해 기본 기간은 올해 1월 1일부터 오늘까지로 설정되어 있습니다."
        )


# ============================================================
# Footer
# ============================================================

st.markdown("---")

st.caption(
    "🐷 학교 급식 칼로리 비교 | "
    "교육부·시도교육청 NEIS 학교급식 데이터 활용"
)
