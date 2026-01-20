import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import platform

# ---------------------------------------------------------
# 1. 기본 설정 및 키 설정
# ---------------------------------------------------------
st.set_page_config(page_title="금강 수계 수위-수질 통합 분석", layout="wide")

# 한글 폰트 설정
try:
    system_name = platform.system()
    if system_name == 'Darwin': plt.rc('font', family='AppleGothic') 
    elif system_name == 'Windows': plt.rc('font', family='Malgun Gothic') 
    else: plt.rc('font', family='NanumGothic')
    plt.rc('axes', unicode_minus=False)
except: pass

# [키 설정]
# 1. 한강홍수통제소 (수위용)
HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"

# 2. 공공데이터포털 (수질용)
try:
    DATA_GO_KEY = st.secrets["public_api_key"]
except:
    DATA_GO_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

# ---------------------------------------------------------
# 2. 지점 목록 정의 (수동 매핑) - 에러 수정된 부분
# ---------------------------------------------------------
@st.cache_data(ttl=86400)
def get_station_mapping():
    """
    수위 관측소(한강홍수통제소)와 수질 측정소(환경공단) 매핑
    """
    stations = [
        {
            "name": "공주보", 
            "wal_code": "3012640", 
            "qual_code": "2015A30"
        },
        {
            "name": "세종보", 
            "wal_code": "3012650", 
            "qual_code": "2015A40"
        },
        {
            "name": "백제보", 
            "wal_code": "3012620", 
            "qual_code": "2015A35"
        },
        {
            "name": "대전 갑천 (갑천교)", 
            "wal_code": "3009660", 
            "qual_code": "2014A20"
        },
        {
            "name": "옥천 이원 (이원교)", 
            "wal_code": "3008680", 
            "qual_code": "1003A07"
        },
        {
            "name": "대청댐 (본체)", 
            "wal_code": "1003660", 
            "qual_code": "1003A05"
        }
    ] # 여기가 잘 닫혔는지 확인하세요!
    return pd.DataFrame(stations)

# ---------------------------------------------------------
# 3. 데이터 조회 함수 (API 호출)
# ---------------------------------------------------------

@st.cache_data(ttl=3600)
def get_hrfco_water_level(station_code, start_date, end_date):
    """
    한강홍수통제소 수위 데이터 조회
    """
    s_str = start_date.strftime("%Y%m%d") + "0000"
    e_str = end_date.strftime("%Y%m%d") + "2359"
    
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list/1H/{station_code}/{s_str}/{e_str}.json"
    
    try:
        response = requests.get(url, verify=False)
        data = response.json()
        
        if 'content' in data:
            items = data['content']
            df = pd.DataFrame(items)
            df['datetime'] = pd.to_datetime(df['ymdhm'], format='%Y%m%d%H%M')
            df['water_level'] = pd.to_numeric(df['wl'], errors='coerce')
            return df[['datetime', 'water_level']].sort_values('datetime')
        else:
            return pd.DataFrame()
    except:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_quality_data(qual_code, start_date, end_date):
    """
    환경공단 수질 데이터 조회
    """
    url = "http://apis.data.go.kr/1480523/WaterQualityService/getWaterMeasuringList"
    
    qual_items = []
    curr_date = start_date
    
    while curr_date <= end_date:
        params = {
            "serviceKey": DATA_GO_KEY,
            "numOfRows": "100", "pageNo": "1", "returnType": "json",
            "ptNo": qual_code,
            "wmyr": curr_date.strftime("%Y"),
            "wmmd": curr_date.strftime("%m%d")
        }
        try:
            res = requests.get(url, params=params, timeout=3)
            data = res.json()
            if 'getWaterMeasuringList' in data and 'item' in data['getWaterMeasuringList']:
                items = data['getWaterMeasuringList']['item']
                if isinstance(items, dict): items = [items]
                qual_items.extend(items)
        except: pass
        curr_date += timedelta(days=1)
        
    if qual_items:
        df = pd.DataFrame(qual_items)
        df['hour_str'] = df['wmht'].astype(str).str.zfill(2)
        df['date_str'] = df['wmyr'] + "-" + df['wmmd'].str[:2] + "-" + df['wmmd'].str[2:]
        df['datetime'] = pd.to_datetime(df['date_str'] + " " + df['hour_str'] + ":00", errors='coerce')
        
        mapping = {'ph': 'pH', 'do': 'DO', 'toc': 'TOC', 'tn': 'TN', 'tp': 'TP'}
        for k, v in mapping.items():
            if k in df.columns: df[v] = pd.to_numeric(df[k], errors='coerce')
                
        return df.dropna(subset=['datetime']).sort_values('datetime')
    else:
        return pd.DataFrame()

# ---------------------------------------------------------
# 4. 메인 화면 UI
# ---------------------------------------------------------
st.title("🌊 금강 수계 통합 분석 (HRFCO + 환경공단)")
st.caption("수위: 한강홍수통제소 / 수질: 환경공단")

with st.sidebar:
    st.header("1️⃣ 지점 선택")
    
    station_df = get_station_mapping()
    selected_name = st.selectbox("분석 지점", station_df['name'])
    
    row = station_df[station_df['name'] == selected_name].iloc[0]
    sel_wal_code = row['wal_code']
    sel_qual_code = row['qual_code']
    
    st.info(f"선택지점 코드:\n- 수위: {sel_wal_code}\n- 수질: {sel_qual_code}")
    st.divider()
    
    target_q = st.selectbox("수질 항목", ["TOC", "TP", "TN", "DO", "pH"])
    start_date = st.date_input("시작", datetime.now() - timedelta(days=3))
    end_date = st.date_input("종료", datetime.now())

if st.button("분석 시작", type="primary"):
    with st.spinner("데이터 조회 중..."):
        df_wal = get_hrfco_water_level(sel_wal_code, start_date, end_date)
        df_qual = get_quality_data(sel_qual_code, start_date, end_date)
        
        if df_wal.empty or df_qual.empty:
            st.error("데이터를 가져오지 못했습니다. (해당 기간 데이터 없음)")
        else:
            df_merged = pd.merge_asof(
                df_wal, df_qual, on='datetime', direction='nearest', tolerance=pd.Timedelta('1H')
            )
            
            st.success(f"분석 완료! ({len(df_merged)}건)")
            
            # 차트
            fig, ax1 = plt.subplots(figsize=(12, 6))
            sns.lineplot(data=df_merged, x='datetime', y='water_level', ax=ax1, color='#007acc', label='수위(m)')
            ax1.set_ylabel('수위 (m)', color='#007acc')
            ax1.grid(True, alpha=0.3)
            
            ax2 = ax1.twinx()
            sns.lineplot(data=df_merged, x='datetime', y=target_q, ax=ax2, color='#ff7f0e', label=target_q, marker='o')
            ax2.set_ylabel(target_q, color='#ff7f0e')
            
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
            
            st.pyplot(fig)
            
            with st.expander("데이터 원본"):
                st.dataframe(df_merged)
