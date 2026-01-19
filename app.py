import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import platform

# ---------------------------------------------------------
# 1. 기본 설정
# ---------------------------------------------------------
st.set_page_config(page_title="금강 수계 예측 대시보드", layout="wide")

# 한글 폰트 설정
try:
    system_name = platform.system()
    if system_name == 'Darwin': plt.rc('font', family='AppleGothic') 
    elif system_name == 'Windows': plt.rc('font', family='Malgun Gothic') 
    else: plt.rc('font', family='NanumGothic')
    plt.rc('axes', unicode_minus=False)
except: pass

# API 키 설정
try:
    API_KEY = st.secrets["public_api_key"]
except:
    st.error("API 키가 설정되지 않았습니다.")
    st.stop()

# ---------------------------------------------------------
# 2. 관측소 목록 가져오기 (동적 드롭다운용)
# ---------------------------------------------------------

@st.cache_data(ttl=86400) # 하루에 한 번만 실행 (속도 향상)
def get_kwater_station_list():
    """
    금강 수계 주요 댐/보를 순회하며 수위 관측소 목록을 모두 수집합니다.
    """
    # 금강 수계 주요 댐/보 코드 리스트 (부모 코드)
    # 대청댐(1003110), 용담댐(1001110), 공주보(3012110), 세종보(3012120), 백제보(3012130) 등
    target_dams = [
        ('1003110', '대청댐'), ('1001110', '용담댐'), 
        ('3012110', '공주보'), ('3012120', '세종보'), ('3012130', '백제보')
    ]
    
    url = "http://apis.data.go.kr/B500001/dam/excllncobsrvt/wal/wallist"
    all_stations = []

    for dam_code, dam_name in target_dams:
        params = {"serviceKey": API_KEY, "_type": "json", "damcode": dam_code}
        try:
            response = requests.get(url, params=params, verify=False)
            data = response.json()
            items = data['response']['body']['items']['item']
            if isinstance(items, dict): items = [items]
            
            for item in items:
                # 댐 정보도 같이 저장
                item['parent_dam_code'] = dam_code
                item['parent_dam_name'] = dam_name
                all_stations.append(item)
        except:
            continue
            
    if all_stations:
        df = pd.DataFrame(all_stations)
        # 드롭다운 표시용 이름 생성 (예: [공주보] 공주보상류)
        df['display_name'] = "[" + df['parent_dam_name'] + "] " + df['obsrvtNm']
        return df
    else:
        return pd.DataFrame()

@st.cache_data(ttl=86400)
def get_quality_station_list():
    """
    환경공단 수질측정소 목록을 가져옵니다.
    (API 키 권한 문제 시 더미 리스트 반환)
    """
    # 실제 수질측정소 조회 API
    url = "http://apis.data.go.kr/1480523/WaterQualityService/getMsrstnList"
    params = {"serviceKey": API_KEY, "numOfRows": "200", "pageNo": "1", "returnType": "json"}
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        items = data['getMsrstnList']['item']
        return pd.DataFrame(items)
    except:
        # API 호출 실패 시 (키 권한 없음 등), 사용자가 직접 선택할 수 있도록 주요 지점 수동 리스트 제공
        dummy_data = [
            {'ptNo': '2015A30', 'ptNm': '공주보1'},
            {'ptNo': '2015A40', 'ptNm': '세종보1'},
            {'ptNo': '1003A05', 'ptNm': '대청댐1'},
            {'ptNo': '3012640', 'ptNm': '백제보1'}
        ]
        return pd.DataFrame(dummy_data)

# ---------------------------------------------------------
# 3. 데이터 조회 함수
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def get_data(dam_code, wal_code, quality_code, start, end):
    # 1. 수위 데이터 조회
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
        if isinstance(items, dict): items = [items]
        df_wal = pd.DataFrame(items)
        df_wal['datetime'] = pd.to_datetime(df_wal['obsrdt'])
        df_wal['water_level'] = pd.to_numeric(df_wal['flux'])
        df_wal = df_wal[['datetime', 'water_level']].sort_values('datetime')
    except:
        pass

    # 2. 수질 데이터 조회 (테스트용 더미 생성 - 실제 API 연동 시 교체)
    # 실제로는 quality_code(ptNo)를 이용해 API 호출해야 함
    dates = pd.date_range(start=start, end=end + timedelta(hours=23), freq='H')
    import numpy as np
    dummy_qual = []
    for d in dates:
        dummy_qual.append({
            'datetime': d,
            'chla': np.random.uniform(5.0, 45.0) # 랜덤 조류 농도
        })
    df_qual = pd.DataFrame(dummy_qual)

    return df_wal, df_qual

# ---------------------------------------------------------
# 4. 메인 화면 UI
# ---------------------------------------------------------
st.title("🌊 금강 수계 수위-수질 분석기")
st.caption("API를 통해 실시간으로 관측소 목록을 불러와 선택합니다.")

# 사이드바: 동적 드롭다운
with st.sidebar:
    st.header("1️⃣ 관측소 선택")
    
    # 1. 수위 관측소 목록 로딩
    with st.spinner("수위 관측소 목록 갱신 중..."):
        df_wal_stations = get_kwater_station_list()
    
    if not df_wal_stations.empty:
        # 드롭다운 생성 (보여주는 건 이름, 실제 값은 전체 행 데이터)
        selected_wal_name = st.selectbox(
            "수위 관측소 (K-water)", 
            df_wal_stations['display_name'].unique()
        )
        # 선택된 관측소의 코드 정보 추출
        selected_wal_row = df_wal_stations[df_wal_stations['display_name'] == selected_wal_name].iloc[0]
        sel_dam_code = selected_wal_row['parent_dam_code']
        sel_wal_code = selected_wal_row['walobsrvtcode']
    else:
        st.error("수위 관측소 목록을 불러오지 못했습니다.")
        st.stop()
        
    # 2. 수질 측정소 목록 로딩
    with st.spinner("수질 측정소 목록 갱신 중..."):
        df_qual_stations = get_quality_station_list()
        
    if not df_qual_stations.empty:
        selected_qual_name = st.selectbox(
            "수질 측정소 (환경공단)",
            df_qual_stations['ptNm'].unique()
        )
        # 선택된 측정소의 코드 추출
        selected_qual_row = df_qual_stations[df_qual_stations['ptNm'] == selected_qual_name].iloc[0]
        sel_qual_code = selected_qual_row['ptNo']
    else:
        st.warning("수질 측정소 목록 로드 실패 (기본값 사용)")
        sel_qual_code = "TEST"

    st.divider()
    st.header("2️⃣ 조회 설정")
    start_date = st.date_input("시작일", datetime.now() - timedelta(days=7))
    end_date = st.date_input("종료일", datetime.now())
    alert_th = st.slider("경보 기준 (Chl-a)", 0, 100, 25)

# 메인 실행
if st.button("분석 시작", type="primary"):
    # 선택된 코드(sel_dam_code, sel_wal_code)를 사용해 데이터 조회
    df_level, df_quality = get_data(sel_dam_code, sel_wal_code, sel_qual_code, start_date, end_date)
    
    if df_level.empty:
        st.error("선택하신 수위 관측소의 데이터가 없습니다.")
    else:
        # 데이터 병합 및 시각화
        df_merged = pd.merge_asof(
            df_level.sort_values('datetime'), 
            df_quality.sort_values('datetime'), 
            on='datetime', direction='nearest', tolerance=pd.Timedelta('1H')
        )
        
        st.success(f"**{selected_wal_name}** 와 **{selected_qual_name}** 데이터를 분석합니다.")
        
        # 차트 그리기
        fig, ax1 = plt.subplots(figsize=(12, 5))
        sns.lineplot(data=df_merged, x='datetime', y='water_level', ax=ax1, color='blue', label='수위')
        ax1.set_ylabel('수위 (m)', color='blue')
        
        ax2 = ax1.twinx()
        sns.lineplot(data=df_merged, x='datetime', y='chla', ax=ax2, color='green', label='Chl-a')
        ax2.axhline(alert_th, color='red', linestyle='--', label='경보 기준')
        ax2.set_ylabel('조류농도', color='green')
        
        st.pyplot(fig)
