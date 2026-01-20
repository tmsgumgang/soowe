import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import urllib3

# SSL 경고 숨기기
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------
st.set_page_config(page_title="수위 현황판", layout="wide")
st.title("🌊 실시간 수위 현황 (접속 차단 해결판)")

# 한강홍수통제소 API 키
HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"

# [핵심] 서버 차단을 뚫기 위한 '신분증' (헤더)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ---------------------------------------------------------
# 1. CSV 파일 읽어오기
# ---------------------------------------------------------
@st.cache_data
def load_station_csv():
    try:
        # 코드를 문자열로 읽어야 안전합니다.
        df = pd.read_csv("station_list.csv", dtype={'수위코드': str, '수질코드': str})
        
        # 이전 CSV와 컬럼명이 다를 수 있어 표준화
        if '코드' in df.columns and '수위코드' not in df.columns:
            df.rename(columns={'코드': '수위코드'}, inplace=True)
            
        return df
    except Exception as e:
        return pd.DataFrame()

# ---------------------------------------------------------
# 2. API로 실시간 데이터 가져오기 (헤더 추가됨!)
# ---------------------------------------------------------
def get_realtime_data(station_code):
    """
    특정 코드(station_code)의 현재 수위를 가져옵니다.
    """
    if not station_code or pd.isna(station_code):
        return None

    # 현재 시간 기준 10분 전 데이터 조회
    now = datetime.now()
    before = now - timedelta(minutes=60) # 1시간 전 (넉넉하게)
    
    s_str = before.strftime("%Y%m%d%H%M")
    e_str = now.strftime("%Y%m%d%H%M")
    
    # 10분 단위 수위 데이터 API
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list/10M/{station_code}/{s_str}/{e_str}.json"
    
    try:
        # [수정] headers=HEADERS 추가하여 차단 방지
        response = requests.get(url, headers=HEADERS, verify=False, timeout=3)
        
        if response.status_code == 200:
            data = response.json()
            if 'content' in data:
                # 가장 최신 데이터 1개만 가져옴
                # content 리스트의 마지막이 최신 데이터임
                latest = data['content'][-1] 
                return {
                    '수위(m)': float(latest['wl']),
                    '관측시간': latest['ymdhm']
                }
    except:
        pass
    return None

# ---------------------------------------------------------
# 3. 메인 실행
# ---------------------------------------------------------

# CSV 로드
df_csv = load_station_csv()

if not df_csv.empty:
    st.info(f"📂 목록 파일(CSV) 로드 완료: 총 {len(df_csv)}개 지점")
    
    if st.button("실시간 수위 가져오기 (API 호출)", type="primary"):
        
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty() # 진행상황 텍스트
        
        total = len(df_csv)
        success_count = 0
        
        for i, row in df_csv.iterrows():
            # CSV 컬럼명 유연하게 처리
            code = row.get('수위코드') or row.get('코드')
            name = row.get('관측소명')
            addr = row.get('주소', '-')
            
            status_text.text(f"📡 접속 중: {name} ({code})...")
            
            # API 호출
            api_data = get_realtime_data(code)
            
            if api_data:
                results.append({
                    '관측소명': name,
                    '현재수위(m)': api_data['수위(m)'],
                    '관측시간': api_data['관측시간'],
                    '주소': addr
                })
                success_count += 1
            else:
                results.append({
                    '관측소명': name,
                    '현재수위(m)': "점검중/통신에러",
                    '관측시간': "-",
                    '주소': addr
                })
            
            # 진행률 업데이트
            progress_bar.progress((i + 1) / total)
            
        status_text.text("✅ 조회 완료!")
        
        # 결과 표출
        if results:
            df_result = pd.DataFrame(results)
            
            st.divider()
            c1, c2 = st.columns([1, 3])
            c1.metric("성공한 지점", f"{success_count} / {total}")
            
            st.subheader("📊 조회 결과")
            # 스타일링: 수위 데이터가 있는 행 강조 (선택사항)
            st.dataframe(df_result, use_container_width=True, hide_index=True)
            
            # 엑셀 다운로드
            csv_data = df_result.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 결과 엑셀로 저장", csv_data, "실시간수위_결과.csv")
            
        else:
            st.warning("조회된 데이터가 없습니다.")
            
else:
    st.error("GitHub에 'station_list.csv' 파일이 없습니다.")
    st.info("이전 단계에서 만든 CSV 파일을 GitHub에 업로드해주세요.")
