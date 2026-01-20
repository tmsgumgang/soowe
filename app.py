import streamlit as st
import pandas as pd
import requests
import urllib3
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import platform

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------
# 1. 기본 설정
# ---------------------------------------------------------
st.set_page_config(page_title="금강 수계 통합 분석", layout="wide")

# 한글 폰트
try:
    system_name = platform.system()
    if system_name == 'Darwin': plt.rc('font', family='AppleGothic') 
    elif system_name == 'Windows': plt.rc('font', family='Malgun Gothic') 
    else: plt.rc('font', family='NanumGothic')
    plt.rc('axes', unicode_minus=False)
except: pass

# API 키
HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"
try:
    DATA_GO_KEY = st.secrets["public_api_key"]
except:
    DATA_GO_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

# ---------------------------------------------------------
# 2. [핵심] CSV 파일에서 목록 불러오기
# ---------------------------------------------------------
@st.cache_data(ttl=600)
def get_station_list_from_csv():
    """
    GitHub에 올려둔 station_list.csv 파일을 읽어옵니다.
    1176개를 다 넣지 않고, 필요한 파일만 관리하면 되어 효율적입니다.
    """
    # ⚠️ 중요: 본인의 GitHub Raw 파일 주소로 바꿔야 할 수도 있습니다.
    # 일단 로컬에 파일이 있다고 가정하고 읽습니다. (GitHub 배포 시 자동 인식)
    try:
        df = pd.read_csv("station_list.csv", encoding='utf-8') # 또는 'cp949'
        return df
    except Exception as e:
        # 파일이 없을 경우를 대비한 비상용 데이터
        st.warning(f"CSV 파일을 찾지 못해 기본 목록을 사용합니다. ({e})")
        data = [
            {'관측소명': '대전시(갑천교)', '수위코드': '3009660', '수질코드': '2014A20', '주소': '비상용 데이터'},
            {'관측소명': '옥천군(이원교)', '수위코드': '3008680', '수질코드': '1003A07', '주소': '비상용 데이터'},
            {'관측소명': '공주보', '수위코드': '3012640', '수질코드': '2015A30', '주소': '비상용 데이터'},
        ]
        return pd.DataFrame(data)

# ---------------------------------------------------------
# 3. 데이터 조회 로직
# ---------------------------------------------------------
@st.cache_data(ttl=600)
def get_data(wal_code, qual_code, start, end):
    
    # [1] 수위 (한강홍수통제소)
    s_str = start.strftime("%Y%m%d") + "0000"
    e_str = end.strftime("%Y%m%d") + "2359"
    url_wal = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list/1H/{wal_code}/{s_str}/{e_str}.json"
    
    df_wal = pd.DataFrame()
    try:
        res = requests.get(url_wal, headers=HEADERS, verify=False, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if 'content' in data:
                df_wal = pd.DataFrame(data['content'])
                df_wal['datetime'] = pd.to_datetime(df_wal['ymdhm'], format='%Y%m%d%H%M')
                df_wal['water_level'] = pd.to_numeric(df_wal['wl'], errors='coerce')
                df_wal = df_wal[['datetime', 'water_level']].sort_values('datetime')
    except: pass

    # [2] 수질 (환경공단)
    url_qual = "http://apis.data.go.kr/1480523/WaterQualityService/getWaterMeasuringList"
    qual_items = []
    curr = start
    while curr <= end:
        params = {
            "serviceKey": DATA_GO_KEY, "numOfRows": "100", "pageNo": "1", "returnType": "json",
            "ptNo": str(qual_code), # 문자열 변환 안전장치
            "wmyr": curr.strftime("%Y"), "wmmd": curr.strftime("%m%d")
        }
        try:
            r = requests.get(url_qual, params=params, headers=HEADERS, timeout=3)
            q_data = r.json()
            if 'getWaterMeasuringList' in q_data and 'item' in q_data['getWaterMeasuringList']:
                items = q_data['getWaterMeasuringList']['item']
                if isinstance(items, dict): items = [items]
                qual_items.extend(items)
        except: pass
        curr += timedelta(days=1)
    
    df_qual = pd.DataFrame()
    if qual_items:
        df_qual = pd.DataFrame(qual_items)
        df_qual['hour_str'] = df_qual['wmht'].astype(str).str.zfill(2)
        df_qual['date_str'] = df_qual['wmyr'] + "-" + df_qual['wmmd'].str[:2] + "-" + df_qual['wmmd'].str[2:]
        df_qual['datetime'] = pd.to_datetime(df_qual['date_str'] + " " + df_qual['hour_str'] + ":00", errors='coerce')
        
        mapping = {'ph': 'pH', 'do': 'DO', 'toc': 'TOC', 'tn': 'TN', 'tp': 'TP'}
        for k, v in mapping.items():
            if k in df_qual.columns: df_qual[v] = pd.to_numeric(df_qual[k], errors='coerce')
        
        df_qual = df_qual.dropna(subset=['datetime']).sort_values('datetime')

    return df_wal, df_qual

# ---------------------------------------------------------
# 4. 메인 UI
# ---------------------------------------------------------
st.title("🌊 금강 수계 통합 모니터링 (CSV 연동)")

with st.sidebar:
    st.header("1️⃣ 지점 선택")
    
    # CSV 파일 읽기
    station_df = get_station_list_from_csv()
    
    if not station_df.empty:
        # 드롭다운
        s_name = st.selectbox("관측소", station_df['관측소명'])
        
        # 선택된 행 찾기
        row = station_df[station_df['관측소명'] == s_name].iloc[0]
        sel_wal = row['수위코드']
        sel_qual = row['수질코드']
        
        st.success(f"선택: {s_name}")
        st.caption(f"주소: {row['주소']}")
    else:
        st.error("관측소 목록을 불러올 수 없습니다.")
        st.stop()
        
    st.divider()
    target_q = st.selectbox("수질 항목", ["TOC", "TP", "TN", "DO", "pH"])
    start_date = st.date_input("시작", datetime.now() - timedelta(days=3))
    end_date = st.date_input("종료", datetime.now())

if st.button("데이터 조회", type="primary"):
    with st.spinner("데이터 분석 중..."):
        df_wal, df_qual = get_data(sel_wal, sel_qual, start_date, end_date)
        
        if df_wal.empty and df_qual.empty:
            st.error("데이터가 없습니다.")
        else:
            # 병합
            if not df_wal.empty and not df_qual.empty:
                df_merged = pd.merge_asof(df_wal, df_qual, on='datetime', direction='nearest', tolerance=pd.Timedelta('1H'))
            elif not df_wal.empty:
                df_merged = df_wal
            else:
                df_merged = df_qual
                
            # 차트
            fig, ax1 = plt.subplots(figsize=(12, 5))
            
            if 'water_level' in df_merged.columns:
                sns.lineplot(data=df_merged, x='datetime', y='water_level', ax=ax1, color='blue', label='수위')
                ax1.set_ylabel('수위(m)', color='blue')
                
            if target_q in df_merged.columns:
                ax2 = ax1.twinx()
                sns.lineplot(data=df_merged, x='datetime', y=target_q, ax=ax2, color='green', label=target_q)
                ax2.set_ylabel(target_q, color='green')
            
            st.pyplot(fig)
            st.dataframe(df_merged)
