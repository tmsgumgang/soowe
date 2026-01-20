import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import platform
import time

# ---------------------------------------------------------
# 1. 기본 설정
# ---------------------------------------------------------
st.set_page_config(page_title="금강 수계 수위-수질 통합 분석", layout="wide")

try:
    system_name = platform.system()
    if system_name == 'Darwin': plt.rc('font', family='AppleGothic') 
    elif system_name == 'Windows': plt.rc('font', family='Malgun Gothic') 
    else: plt.rc('font', family='NanumGothic')
    plt.rc('axes', unicode_minus=False)
except: pass

try:
    API_KEY = st.secrets["public_api_key"]
except:
    st.error("API 키가 설정되지 않았습니다.")
    st.stop()

# ---------------------------------------------------------
# 2. [핵심] 측정소 목록 (API가 없어서 직접 만듦)
# ---------------------------------------------------------

@st.cache_data(ttl=86400)
def get_kwater_station_list():
    """
    K-water 수위 관측소 목록 (주요 지점 수동 정의)
    """
    # 금강 수계 주요 수위 관측소 (이름, 댐코드, 관측소코드)
    stations = [
        {'name': '[공주보] 공주보', 'dam': '3012110', 'wal': '3012110'},
        {'name': '[세종보] 세종보', 'dam': '3012120', 'wal': '3012120'},
        {'name': '[백제보] 백제보', 'dam': '3012130', 'wal': '3012130'},
        {'name': '[대청댐] 대청댐', 'dam': '1003110', 'wal': '1003660'}, # 대청댐 본체
        {'name': '[갑천] 대전시(갑천교)', 'dam': '3009660', 'wal': '3009660'}, # 갑천 수위
        {'name': '[옥천] 옥천군(이원교)', 'dam': '3008680', 'wal': '3008680'}, # 이원 근처 수위
    ]
    return pd.DataFrame(stations)

@st.cache_data(ttl=86400)
def get_quality_station_list():
    """
    환경공단 수질 측정소 목록 (주요 지점 수동 정의)
    * API 목록 조회가 불가능하여 직접 코드를 매핑했습니다.
    """
    stations = [
        # 보 구간
        {'name': '공주보', 'code': '2015A30'},
        {'name': '세종보', 'code': '2015A40'},
        {'name': '백제보', 'code': '2015A35'},
        
        # 대청호 구간 (이원 포함)
        {'name': '대청호(추소)', 'code': '1003A05'},
        {'name': '대청호(문의)', 'code': '1003A08'},
        {'name': '대청호(회남)', 'code': '1003A25'},
        {'name': '이원(대청호 상류)', 'code': '1003A07'}, # 이원 지점
        
        # 갑천 구간
        {'name': '갑천1', 'code': '2014A20'},
        {'name': '갑천2', 'code': '2014A22'},
        {'name': '갑천5', 'code': '2014A50'},
    ]
    return pd.DataFrame(stations)

# ---------------------------------------------------------
# 3. 데이터 조회 (실제 API 호출)
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def get_data(dam_code, wal_code, quality_code, start, end):
    
    # [1] 수위 데이터
    url_wal = "https://apis.data.go.kr/B500001/dam/excllncobsrvt/hourwal/hourwallist"
    params_wal = {
        "serviceKey": API_KEY, "_type": "json", "numOfRows": "999", "pageNo": "1",
        "sdate": start.strftime("%Y-%m-%d"), "stime": "00",
        "edate": end.strftime("%Y-%m-%d"), "etime": "23",
        "damcode": dam_code, "wal": wal_code
    }
    
    df_wal = pd.DataFrame()
    try:
        res = requests.get(url_wal, params=params_wal, verify=False).json()
        items = res['response']['body']['items']['item']
        if items:
            if isinstance(items, dict): items = [items]
            df_wal = pd.DataFrame(items)
            df_wal['datetime'] = pd.to_datetime(df_wal['obsrdt'])
            df_wal['water_level'] = pd.to_numeric(df_wal['flux'])
            df_wal = df_wal[['datetime', 'water_level']].sort_values('datetime')
    except: pass

    # [2] 수질 데이터 (TN, TP, TOC 등)
    url_qual = "http://apis.data.go.kr/1480523/WaterQualityService/getWaterMeasuringList"
    
    qual_items = []
    curr_date = start
    while curr_date <= end:
        params_qual = {
            "serviceKey": API_KEY, "numOfRows": "100", "pageNo": "1", "returnType": "json",
            "ptNo": quality_code,
            "wmyr": curr_date.strftime("%Y"),
            "wmmd": curr_date.strftime("%m%d")
        }
        try:
            q_res = requests.get(url_qual, params=params_qual, timeout=3)
            q_data = q_res.json()
            if 'getWaterMeasuringList' in q_data and 'item' in q_data['getWaterMeasuringList']:
                day_items = q_data['getWaterMeasuringList']['item']
                if isinstance(day_items, dict): day_items = [day_items]
                qual_items.extend(day_items)
        except: pass
        curr_date += timedelta(days=1)
    
    df_qual = pd.DataFrame()
    if qual_items:
        df_qual = pd.DataFrame(qual_items)
        df_qual['hour_str'] = df_qual['wmht'].astype(str).str.zfill(2) 
        df_qual['date_str'] = df_qual['wmyr'] + "-" + df_qual['wmmd'].str[:2] + "-" + df_qual['wmmd'].str[2:]
        df_qual['datetime'] = pd.to_datetime(df_qual['date_str'] + " " + df_qual['hour_str'] + ":00", errors='coerce')
        
        # 주요 수질 항목 파싱
        mapping = {'ph': 'pH', 'do': 'DO', 'toc': 'TOC', 'tn': 'TN', 'tp': 'TP'}
        for k, v in mapping.items():
            if k in df_qual.columns:
                df_qual[v] = pd.to_numeric(df_qual[k], errors='coerce')
        
        df_qual = df_qual.dropna(subset=['datetime']).sort_values('datetime')

    return df_wal, df_qual

# ---------------------------------------------------------
# 4. 메인 UI
# ---------------------------------------------------------
st.title("🌊 금강 수계 통합 대시보드")

with st.sidebar:
    st.header("1️⃣ 지점 선택")
    
    # 수위
    w_df = get_kwater_station_list()
    w_name = st.selectbox("수위 관측소", w_df['name'])
    w_row = w_df[w_df['name'] == w_name].iloc[0]
    
    # 수질
    q_df = get_quality_station_list()
    q_name = st.selectbox("수질 측정소", q_df['name'])
    q_code = q_df[q_df['name'] == q_name].iloc[0]['code']
    
    st.divider()
    target_q = st.selectbox("분석 항목", ["TOC", "TP", "TN", "DO", "pH"])
    start_date = st.date_input("시작", datetime.now() - timedelta(days=3))
    end_date = st.date_input("종료", datetime.now())

if st.button("분석 시작", type="primary"):
    with st.spinner("데이터 조회 중..."):
        df_wal, df_qual = get_data(w_row['dam'], w_row['wal'], q_code, start_date, end_date)
        
        if df_wal.empty or df_qual.empty:
            st.error("데이터를 불러오지 못했습니다.")
        else:
            df_merged = pd.merge_asof(df_wal, df_qual, on='datetime', direction='nearest', tolerance=pd.Timedelta('1H'))
            
            # 차트
            fig, ax1 = plt.subplots(figsize=(12, 5))
            sns.lineplot(data=df_merged, x='datetime', y='water_level', ax=ax1, color='blue', label='수위(m)')
            ax1.set_ylabel('수위 (m)', color='blue')
            ax2 = ax1.twinx()
            sns.lineplot(data=df_merged, x='datetime', y=target_q, ax=ax2, color='orange', label=target_q)
            ax2.set_ylabel(target_q, color='orange')
            st.pyplot(fig)
