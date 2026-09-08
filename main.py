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
    page_title="학교 급식 칼로리 비교",
    page_icon="🍱",
    layout="wide"
)

API_URL = "https://open.neis.go.kr/hub"

# 당곡고등학교 기본 정보
DANGGOK = {
    "학교명": "당곡고등학교",
    "교육청코드": "B10",
    "학교코드": "7010073"
}


# =========================================================
# CSS
# =========================================================

st.markdown("""
<style>

.main-title {
    font-size: 42px;
    font-weight: 800;
    margin-bottom: 5px;
}

.sub-title {
    font-size: 18px;
    color: #666;
    margin-bottom: 25px;
}

.info-box {
    padding: 20px;
    border-radius: 15px;
    background-color: #f7f9fc;
    border: 1px solid #e5e7eb;
    margin-bottom: 15px;
}

.metric-card {
    padding: 20px;
    border-radius: 15px;
    background-color: #f8fafc;
    border: 1px solid #e5e7eb;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# API 함수
# =========================================================

def get_api_key():
    """
    Streamlit Secrets에서 NEIS API KEY 가져오기
    """
    try:
        return st.secrets["NEIS_API_KEY"]
    except Exception:
        return ""


@st.cache_data(ttl=3600)
def search_schools(school_name, api_key):
    """
    학교명으로 NEIS 학교기본정보 검색
    """

    url = f"{API_URL}/schoolInfo"

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
            timeout=10
        )

        response.raise_for_status()
        data = response.json()

        if "schoolInfo" not in data:
            return pd.DataFrame()

        rows = data["schoolInfo"][1]["row"]

        result = []

        for row in rows:

            # 고등학교만 표시
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


@st.cache_data(ttl=1800)
def get_meal_data(
    school_code,
    office_code,
    start_date,
    end_date,
    api_key
):
    """
    특정 학교의 기간별 급식 데이터 조회
    """

    url = f"{API_URL}/mealServiceDietInfo"

    params = {
        "KEY": api_key,
        "Type": "json",
        "pIndex": 1,
        "pSize": 1000,
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "MMEAL_SC_CODE": "2",  # 중식
        "MLSV_FROM_YMD": start_date.strftime("%Y%m%d"),
        "MLSV_TO_YMD": end_date.strftime("%Y%m%d")
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        response.raise_for_status()
        data = response.json()

        if "mealServiceDietInfo" not in data:
            return pd.DataFrame()

        rows = data["mealServiceDietInfo"][1]["row"]

        result = []

        for row in rows:

            calorie_text = row.get("CAL_INFO", "")

            # "845.5 Kcal" 같은 형태에서 숫자만 추출
            match = re.search(
                r"([\d,]+(?:\.\d+)?)",
                calorie_text
            )

            if not match:
                continue

            calorie = float(
                match.group(1).replace(",", "")
            )

            result.append({
                "학교명": row.get("SCHUL_NM", ""),
                "급식일자": pd.to_datetime(
                    row.get("MLSV_YMD"),
                    format="%Y%m%d",
                    errors="coerce"
                ),
                "급식명": row.get("MMEAL_SC_NM", ""),
                "칼로리": calorie,
                "메뉴": row.get("DDISH_NM", ""),
                "영양정보": row.get("NTR_INFO", "")
            })

        return pd.DataFrame(result)

    except Exception:
        return pd.DataFrame()


# =========================================================
# 제목
# =========================================================

st.markdown(
    '<div class="main-title">🍱 학교 급식 칼로리 비교</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="sub-title">'
    'NEIS 급식 데이터를 이용해 학교별 평균 급식 칼로리를 비교해보세요.'
    '</div>',
    unsafe_allow_html=True
)


# =========================================================
# API KEY 확인
# =========================================================

API_KEY = get_api_key()

if not API_KEY:

    st.error(
        "NEIS API 인증키가 설정되지 않았습니다."
    )

    st.info(
        """
        Streamlit Cloud의 **Settings → Secrets**에 다음과 같이 입력하세요.

        ```toml
        NEIS_API_KEY = "여기에_발급받은_API_KEY"
        ```
        """
    )

    st.stop()


# =========================================================
# 사이드바
# =========================================================

st.sidebar.header("⚙️ 분석 설정")

st.sidebar.markdown(
    "### ① 분석 기간"
)

today = date.today()

default_start = today - timedelta(days=30)

start_date = st.sidebar.date_input(
    "시작일",
    value=default_start
)

end_date = st.sidebar.date_input(
    "종료일",
    value=today
)

if start_date > end_date:
    st.sidebar.error(
        "시작일은 종료일보다 빠르거나 같아야 합니다."
    )
    st.stop()


st.sidebar.markdown("---")

st.sidebar.markdown(
    "### ② 학교 추가"
)

school_search = st.sidebar.text_input(
    "학교명을 입력하세요",
    placeholder="예: 서울고등학교"
)

if "school_list" not in st.session_state:

    # 당곡고등학교를 기본 선택
    st.session_state.school_list = [
        DANGGOK
    ]


# =========================================================
# 학교 검색
# =========================================================

if school_search:

    search_result = search_schools(
        school_search,
        API_KEY
    )

    if not search_result.empty:

        selected_school = st.sidebar.selectbox(
            "검색 결과",
            search_result["학교명"].tolist()
        )

        selected_row = search_result[
            search_result["학교명"] == selected_school
        ].iloc[0]

        if st.sidebar.button(
            "➕ 학교 추가",
            use_container_width=True
        ):

            new_school = {
                "학교명": selected_row["학교명"],
                "교육청코드": selected_row["교육청코드"],
                "학교코드": selected_row["학교코드"],
                "주소": selected_row["주소"]
            }

            # 중복 방지
            existing_codes = [
                s["학교코드"]
                for s in st.session_state.school_list
            ]

            if new_school["학교코드"] not in existing_codes:

                st.session_state.school_list.append(
                    new_school
                )

                st.sidebar.success(
                    f"{selected_school} 추가 완료!"
                )

                st.rerun()

    else:

        st.sidebar.warning(
            "학교를 찾을 수 없습니다."
        )


# =========================================================
# 선택된 학교 표시
# =========================================================

st.sidebar.markdown("---")

st.sidebar.markdown(
    "### 📚 분석 학교"
)

for i, school in enumerate(
    st.session_state.school_list
):

    col1, col2 = st.sidebar.columns(
        [4, 1]
    )

    col1.write(
        f"**{school['학교명']}**"
    )

    # 당곡고등학교는 기본 학교라 삭제 가능
    if col2.button(
        "×",
        key=f"delete_{i}"
    ):

        if len(st.session_state.school_list) > 1:

            st.session_state.school_list.pop(i)

            st.rerun()


# =========================================================
# 데이터 수집
# =========================================================

if st.button(
    "🔍 급식 데이터 분석하기",
    type="primary",
    use_container_width=True
):

    all_data = []

    progress = st.progress(0)

    total = len(
        st.session_state.school_list
    )

    for i, school in enumerate(
        st.session_state.school_list
    ):

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
            (i + 1) / total
        )

    progress.empty()

    if not all_data:

        st.error(
            "해당 기간에 급식 데이터를 찾을 수 없습니다."
        )

        st.stop()

    df = pd.concat(
        all_data,
        ignore_index=True
    )

    st.session_state.meal_data = df


# =========================================================
# 분석 결과
# =========================================================

if "meal_data" in st.session_state:

    df = st.session_state.meal_data.copy()

    # 날짜순 정렬
    df = df.sort_values(
        ["급식일자", "학교명"]
    )

    st.markdown("---")

    st.subheader(
        "📊 학교별 평균 급식 칼로리"
    )

    # 학교별 평균
    summary = (
        df.groupby("학교명")
        .agg(
            평균칼로리=("칼로리", "mean"),
            급식일수=("급식일자", "nunique")
        )
        .reset_index()
    )

    summary["평균칼로리"] = summary[
        "평균칼로리"
    ].round(1)

    summary = summary.sort_values(
        "평균칼로리",
        ascending=False
    )

    # =====================================================
    # 핵심 지표
    # =====================================================

    max_school = summary.iloc[0]

    min_school = summary.iloc[-1]

    danggok_data = summary[
        summary["학교명"] == "당곡고등학교"
    ]

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "평균 칼로리가 가장 높은 학교",
            max_school["학교명"],
            f"{max_school['평균칼로리']:.1f} kcal"
        )

    with col2:

        st.metric(
            "평균 칼로리가 가장 낮은 학교",
            min_school["학교명"],
            f"{min_school['평균칼로리']:.1f} kcal"
        )

    with col3:

        if not danggok_data.empty:

            danggok_avg = danggok_data.iloc[0][
                "평균칼로리"
            ]

            st.metric(
                "당곡고등학교 평균",
                f"{danggok_avg:.1f} kcal"
            )

        else:

            st.metric(
                "당곡고등학교 평균",
                "데이터 없음"
            )


    # =====================================================
    # 막대그래프
    # =====================================================

    st.markdown("### 🏫 학교별 평균 칼로리")

    fig_bar = px.bar(
        summary,
        x="학교명",
        y="평균칼로리",
        text="평균칼로리",
        labels={
            "학교명": "학교",
            "평균칼로리": "평균 칼로리 (kcal)"
        },
        title="학교별 평균 급식 칼로리"
    )

    fig_bar.update_traces(
        texttemplate="%{text:.1f} kcal",
        textposition="outside"
    )

    fig_bar.update_layout(
        height=500,
        hovermode="x unified"
    )

    st.plotly_chart(
        fig_bar,
        use_container_width=True
    )


    # =====================================================
    # 날짜별 변화
    # =====================================================

    st.markdown("### 📈 날짜별 급식 칼로리 변화")

    fig_line = px.line(
        df,
        x="급식일자",
        y="칼로리",
        color="학교명",
        markers=True,
        labels={
            "급식일자": "급식 날짜",
            "칼로리": "칼로리 (kcal)",
            "학교명": "학교"
        },
        title="날짜에 따른 급식 칼로리 변화"
    )

    fig_line.update_layout(
        height=500,
        hovermode="x unified"
    )

    st.plotly_chart(
        fig_line,
        use_container_width=True
    )


    # =====================================================
    # 데이터 표
    # =====================================================

    st.markdown("### 📋 분석 결과")

    display_df = summary.copy()

    display_df.columns = [
        "학교명",
        "평균 칼로리 (kcal)",
        "급식일수"
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )


    # =====================================================
    # 가장 높은 급식
    # =====================================================

    st.markdown(
        "### 🔥 가장 칼로리가 높은 급식"
    )

    highest = df.loc[
        df["칼로리"].idxmax()
    ]

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "학교",
            highest["학교명"]
        )

        st.metric(
            "칼로리",
            f"{highest['칼로리']:.1f} kcal"
        )

    with col2:

        st.write(
            f"**급식 날짜:** "
            f"{highest['급식일자'].strftime('%Y-%m-%d')}"
        )

        st.write(
            "**메뉴**"
        )

        st.write(
            highest["메뉴"]
        )


    # =====================================================
    # 원자료
    # =====================================================

    with st.expander(
        "🔎 원자료 확인하기"
    ):

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# 안내
# =========================================================

st.markdown("---")

st.caption(
    "※ 본 서비스는 NEIS 학교급식 데이터를 활용합니다. "
    "급식이 제공되지 않는 날이나 데이터가 등록되지 않은 날은 "
    "평균 계산에서 제외될 수 있습니다."
)
