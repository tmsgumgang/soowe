import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# ---------------------------------------------------------
# 1. 설정
# ---------------------------------------------------------
st.set_page_config(page_title="실시간 수위 조회 테스트")

# 한강홍수통제소 API 키
HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"

# ---------------------------------------------------------
# 2. 지점 목록 (수동 정의)
# ---------------------------------------------------------
def get_station_list():
    # 7자리 표준 코드 (한강홍수통제소 기준)
    return {
        "공주보 수위국": "3012640",
        "세종보 수위국": "3012650",
        "백제보 수위국": "3012620",
        "대전 갑천 (갑천교)": "3009660",
        "옥천 이원 (이원교)": "3008680",
        "대청댐 (본체)": "1003660"
    }

# ---------------------------------------------------------
# 3. API 호출 함수 (10분 단위 데이터)
# ---------------------------------------------------------
def get_realtime_water_level(station_code):
    """
    최근 24시간의 10분 단위 수위 데이터를 가져옵니다.
    """
    # 시간 설정 (현재 시간 ~ 24시간 전)
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(hours=24)
    
    # API 포맷 (YYYYMMDDHHMM)
    s_str = start_dt.strftime("%Y%m%d%H%M")
    e_str = end_dt.strftime("%Y%m%d%H%M")
    
    # 10분 단위(10M) API 호출 URL
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list/10M/{station_code}/{s_str}/{e_str}.json"
    
    try:
        # SSL 인증서 검증 무시 (verify=False)
        response = requests.get(url, verify=False)
        data = response.json()
        
        if 'content' in data:
            items = data['content']
            df = pd.DataFrame(items)
            
            # 컬럼 전처리
            # ymdhm: 시간, wl: 수위(m)
            df['datetime'] = pd.to_datetime(df['ymdhm'], format='%Y%m%d%H%M')
            df['수위(m)'] = pd.to_numeric(df['wl'], errors='coerce')
            
            # 최신순 정렬
            return df[['datetime', '수위(m)']].sort_values('datetime', ascending=True)
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"통신 에러: {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# 4. 메인 화면
# ---------------------------------------------------------
st.title("💧 실시간 수위 데이터 확인")
st.caption(f"API Key: {HRFCO_KEY[:5]}... (한강홍수통제소)")

# 사이드바: 지점 선택
stations = get_station_list()
selected_name = st.sidebar.selectbox("지점 선택", list(stations.keys()))
selected_code = stations[selected_name]

st.sidebar.info(f"선택된 코드: {selected_code}")

if st.button("수위 읽어오기", type="primary"):
    with st.spinner(f"'{selected_name}' 접속 중..."):
        df = get_realtime_water_level(selected_code)
        
        if not df.empty:
            # 1. 최신 수위 표시 (Metric)
            last_row = df.iloc[-1]
            current_level = last_row['수위(m)']
            current_time = last_row['datetime'].strftime("%H시 %M분")
            
            st.metric(label=f"현재 수위 ({current_time} 기준)", value=f"{current_level} m")
            
            # 2. 그래프 그리기
            st.line_chart(df, x='datetime', y='수위(m)', color='#007acc')
            
            # 3. 데이터 표
            with st.expander("상세 데이터 보기"):
                st.dataframe(df.sort_values('datetime', ascending=False)) # 최신순 보기
                
        else:
            st.error("데이터를 가져오지 못했습니다. 코드가 맞는지 확인해주세요.")
