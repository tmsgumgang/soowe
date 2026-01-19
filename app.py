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
# 2. 관측소 목록 가져오기 (API + 수동 추가 하이브리드)
# ---------------------------------------------------------

@st.cache_data(ttl=86400)
def get_kwater_station_list():
    """
    1. API로 대청댐 등 하위 관측소가 있는 댐의 목록을 가져옵니다.
    2. API 결과가 없는 보(공주보, 세종보 등)는 수동으로 리스트에 추가합니다.
    """
    # 1. API 조회 대상 (하위 관측소가 있을 것으로 예상되는 큰 댐)
    api_targets = [
        ('1003110', '대청댐'), 
        ('1001110', '용담댐')
    ]
    
    # 2. 수동 추가 대상 (API 목록 조회가 안 되는 보 - 코드 추정값 적용)
    # 보통 보의 경우 [댐코드]와 [관측소코드(wal)]가 동일한 경우가 많습니다.
    manual_targets = [
        {'obsrvtNm': '공주보 (본체)', 'walobsrvtcode': '3012110', 'parent_dam_code': '3012110', 'parent_dam_name': '공주보'},
        {'obsrvtNm': '세종보 (본체)', 'walobsrvtcode': '3012120', 'parent_dam_code': '3012120', 'parent_dam_name': '세종보'},
        {'obsrvtNm': '백제보 (본체)', 'walobsrvtcode': '3012130', 'parent_dam_code': '3012130', 'parent_dam_name': '백제보'}
    ]
    
    url = "http://apis.data.go.kr/B500001/dam/excllncobsrvt/wal/wallist"
    all_stations = []

    # API 조회 루프
    for dam_code, dam_name in api_targets:
        params = {"serviceKey": API_KEY, "_type": "json", "damcode": dam_code}
        try:
            response = requests.get(url, params=params, verify=False)
            data = response.json()
            items = data['response']['body']['items']['item']
            if isinstance(items, dict): items = [items]
            
            for item in items:
                item['parent_dam_code'] = dam_code
                item['parent_dam_name'] = dam_name
                all_stations.append(item)
        except:
            continue
    
    # 수동 대상 추가
    all_stations.extend(manual_targets)
            
    if all_stations:
        df = pd.DataFrame(all_stations)
        # 드롭다운용 이름 생성
        df['display_name'] = "[" + df['parent_dam_name'] + "] " + df['obsrvtNm']
        return df
    else:
        return pd.DataFrame()

@st.cache_data(ttl=86400)
def get_quality_station_list():
    """
    환경공단 수질측정소 목록 조회 (실패 시 주요 지점 수동 반환)
    """
    url = "http://apis.data.go.kr/1480523/WaterQualityService/getMsrstnList"
    params = {"serviceKey": API_KEY, "numOfRows": "200", "pageNo": "1", "returnType": "json"}
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        items = data['getMsrstnList']['item']
        return pd.DataFrame(items)
    except:
        # API 권한 문제 등으로 실패 시 사용할 백업 리스트
        dummy_data = [
            {'ptNo': '2015A30', 'ptNm': '공주보(수질)'},
            {'ptNo': '2015A40', 'ptNm': '세종보(수질)'},
            {'ptNo': '1003A05', 'ptNm': '대청댐(수질)'},
            {'ptNo': '2015A35', 'ptNm': '백제보(수질)'}
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
        
        # 데이터가 없거나 1건일 때 처리
        if not items:
            pass # 빈 데이터프레임 반환
        else:
            if isinstance(items, dict): items = [items]
            df_wal = pd.DataFrame(items)
            df_wal['datetime'] = pd.to_datetime(df_wal['obsrdt'])
            df_wal['water_level'] = pd.to_numeric(df_wal['flux'])
            df_wal = df_wal[['datetime', 'water_level']].sort_values('datetime')
    except Exception as e:
        # 에러 발생 시 로그만 남기고 빈 DF 반환 (앱 중단 방지)
        print(f"수위 데이터 조회 에러: {e}")

    # 2. 수질 데이터 조회 (테스트용 더미)
    # 실제 API 연결 시 quality_code 사용
    dates = pd.date_range(start=start, end=end + timedelta(hours=23), freq='H')
    import numpy as np
    dummy_qual = []
    for d in dates:
        dummy_qual.append({
            'datetime': d,
            'chla': np.random.uniform(5.0, 45.0) 
        })
    df_qual = pd.DataFrame(dummy_qual)

    return df_wal, df_qual

# ---------------------------------------------------------
# 4. 메인 화면 UI
# ---------------------------------------------------------
st.title("🌊 금강 수계 수위-수질 분석기")

# 사이드바
with st.sidebar:
    st.header("1️⃣ 지점 선택")
    
    # 수위 관측소 로딩
    df_wal_stations = get_kwater_station_list()
    
    if not df_wal_stations.empty:
        wal_names = df_wal_stations['display_name'].unique()
        # 공주보를 기본값으로 설정 시도
        default_idx = 0
        for i, name in enumerate(wal_names):
            if "공주보" in name: default_idx = i; break
            
        selected_wal_name = st.selectbox("수위 관측소", wal_names, index=default_idx)
        
        # 선택된 정보 추출
        row = df_wal_stations[df_wal_stations['display_name'] == selected_wal_name].iloc[0]
        sel_dam = row['parent_dam_code']
        sel_wal = row['walobsrvtcode']
    else:
        st.error("관측소 목록 로드 실패")
        st.stop()
        
    # 수질 측정소 로딩
    df_qual_stations = get_quality_station_list()
    if not df_qual_stations.empty:
        selected_qual_name = st.selectbox("수질 측정소", df_qual_stations['ptNm'].unique())
        q_row = df_qual_stations[df_qual_stations['ptNm'] == selected_qual_name].iloc[0]
        sel_qual = q_row['ptNo']
    else:
        sel_qual = "TEST"

    st.divider()
    st.header("2️⃣ 기간 설정")
    start_date = st.date_input("시작", datetime.now() - timedelta(days=7))
    end_date = st.date_input("종료", datetime.now())
    alert_th = st.slider("경보 기준 (Chl-a)", 0, 100, 25)

# 메인 실행
if st.button("분석 시작", type="primary"):
    with st.spinner(f"Running... [{selected_wal_name}]"):
        df_level, df_quality = get_data(sel_dam, sel_wal, sel_qual, start_date, end_date)
        
        if df_level.empty:
            st.error(f"❌ '{selected_wal_name}'의 수위 데이터가 없습니다.")
            st.info("Tip: 해당 지점이 K-water 관리 구간이 아니거나, API 코드가 다를 수 있습니다.")
        else:
            # 병합 및 시각화
            df_merged = pd.merge_asof(
                df_level, df_quality, on='datetime', direction='nearest', tolerance=pd.Timedelta('1H')
            )
            
            st.success(f"데이터 {len(df_merged)}건 분석 완료")
            
            # 차트
            fig, ax1 = plt.subplots(figsize=(12, 5))
            sns.lineplot(data=df_merged, x='datetime', y='water_level', ax=ax1, color='#1f77b4', label='수위(EL.m)')
            ax1.set_ylabel('수위 (m)', color='#1f77b4', fontweight='bold')
            ax1.grid(True, alpha=0.3)
            
            ax2 = ax1.twinx()
            sns.lineplot(data=df_merged, x='datetime', y='chla', ax=ax2, color='#2ca02c', label='Chl-a')
            ax2.axhline(alert_th, color='red', linestyle='--', label='경보 기준')
            ax2.set_ylabel('조류농도', color='#2ca02c', fontweight='bold')
            
            # 범례 통합
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
            
            st.pyplot(fig)
            
            with st.expander("원본 데이터"):
                st.dataframe(df_merged)
