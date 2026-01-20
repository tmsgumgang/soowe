import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# ---------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------
st.set_page_config(page_title="수위 현황판", layout="wide")
st.title("🌊 실시간 수위 현황 (CSV 이름 연동)")

# 한강홍수통제소 API 키
HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"

# ---------------------------------------------------------
# [절차 2] CSV 파일 읽어오기 (코드 + 이름)
# ---------------------------------------------------------
@st.cache_data
def load_station_csv():
    try:
        # 코드를 문자열(str)로 읽어야 비교가 정확합니다.
        df = pd.read_csv("station_list.csv", dtype={'코드': str})
        return df
    except Exception as e:
        st.error(f"CSV 파일을 읽지 못했습니다: {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# [절차 1] API 통해 실시간 수위값 불러오기
# ---------------------------------------------------------
def get_realtime_data(station_code):
    """
    특정 코드(station_code)의 현재 수위를 API로 가져옵니다.
    """
    # 현재 시간 기준 10분 전 데이터 조회
    now = datetime.now()
    before = now - timedelta(minutes=20) # 넉넉하게 20분 전
    
    s_str = before.strftime("%Y%m%d%H%M")
    e_str = now.strftime("%Y%m%d%H%M")
    
    # 10분 단위 수위 데이터 API
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list/10M/{station_code}/{s_str}/{e_str}.json"
    
    try:
        response = requests.get(url, verify=False, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'content' in data:
                # 가장 최신 데이터 1개만 가져옴
                latest = data['content'][-1] 
                return {
                    '코드': str(station_code),
                    '수위(m)': float(latest['wl']),
                    '관측시간': latest['ymdhm']
                }
    except:
        pass
    return None

# ---------------------------------------------------------
# [절차 3] 메인 실행: 코드명 매칭 및 표출
# ---------------------------------------------------------

# 1. CSV 로드 (여기에 한글 이름이 있음)
df_csv = load_station_csv()

if not df_csv.empty:
    st.success(f"📂 목록 파일(CSV) 로드 완료: 총 {len(df_csv)}개 지점")
    
    if st.button("실시간 수위 가져오기 (API 호출)"):
        
        results = []
        progress_bar = st.progress(0)
        
        # CSV에 있는 지점만큼 반복하며 API 호출
        for i, row in df_csv.iterrows():
            code = row['코드']
            name = row['관측소명'] # CSV에 있는 한글 이름
            
            # API 찔러서 수위값(wl) 가져오기
            api_data = get_realtime_data(code)
            
            if api_data:
                # [핵심] API 데이터 + CSV 한글 이름 합치기
                results.append({
                    '관측소명': name,        # CSV에서 가져온 한글
                    '현재수위(m)': api_data['수위(m)'], # API에서 가져온 값
                    '관측시간': api_data['관측시간'],
                    '주소': row['주소']
                })
            else:
                # API 데이터가 없어도 목록엔 표시 (수위만 비움)
                results.append({
                    '관측소명': name,
                    '현재수위(m)': "측정불가",
                    '관측시간': "-",
                    '주소': row['주소']
                })
            
            # 진행률 바 업데이트
            progress_bar.progress((i + 1) / len(df_csv))
            
        # 결과 표출
        if results:
            df_result = pd.DataFrame(results)
            st.divider()
            st.subheader("📊 조회 결과")
            # 보기 좋게 인덱스 숨기고 출력
            st.dataframe(df_result, use_container_width=True, hide_index=True)
        else:
            st.warning("조회된 데이터가 없습니다.")
            
else:
    st.warning("GitHub에 'station_list.csv' 파일이 있는지 확인해주세요.")
