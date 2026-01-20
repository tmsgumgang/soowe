import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import urllib3

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------
st.set_page_config(page_title="수위 현황판 (디버깅)", layout="wide")
st.title("🌊 실시간 수위 현황 (한국시간 보정판)")

# 한강홍수통제소 API 키
HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ---------------------------------------------------------
# 1. CSV 파일 읽기
# ---------------------------------------------------------
@st.cache_data
def load_station_csv():
    try:
        # 코드는 문자로 읽어야 함
        df = pd.read_csv("station_list.csv", dtype={'수위코드': str, '수질코드': str, '코드': str})
        # 컬럼명 통일 (코드 -> 수위코드)
        if '코드' in df.columns and '수위코드' not in df.columns:
            df['수위코드'] = df['코드']
        return df
    except Exception as e:
        return pd.DataFrame()

# ---------------------------------------------------------
# 2. 실시간 데이터 (한국 시간 적용 + 에러 추적)
# ---------------------------------------------------------
def get_realtime_data_debug(station_code):
    if not station_code or pd.isna(station_code):
        return None, "코드 없음"

    # [핵심] 서버 시간(UTC)을 한국 시간(KST)으로 강제 변환
    # Streamlit Cloud는 UTC 기준이므로 9시간을 더해야 한국 시간이 됨
    now_utc = datetime.utcnow()
    now_kst = now_utc + timedelta(hours=9)
    
    # 최근 3시간 데이터 요청 (범위를 넓혀서 하나라도 걸리게 함)
    end_dt = now_kst
    start_dt = end_dt - timedelta(hours=3)
    
    s_str = start_dt.strftime("%Y%m%d%H%M")
    e_str = end_dt.strftime("%Y%m%d%H%M")
    
    # 10분 단위 API URL
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list/10M/{station_code}/{s_str}/{e_str}.json"
    
    try:
        response = requests.get(url, headers=HEADERS, verify=False, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if 'content' in data:
                content = data['content']
                if content:
                    # 데이터가 있으면 최신값 반환
                    latest = content[-1] 
                    return {
                        '수위(m)': float(latest['wl']),
                        '관측시간': latest['ymdhm'],
                        '상태': '정상'
                    }, "성공"
                else:
                    return None, "데이터 리스트 비어있음 (Empty List)"
            else:
                return None, f"응답에 'content' 키 없음. 원본: {str(data)[:50]}..."
        else:
            return None, f"HTTP 에러: {response.status_code}"
            
    except Exception as e:
        return None, f"통신 에러: {e}"

# ---------------------------------------------------------
# 3. 메인 실행
# ---------------------------------------------------------
df_csv = load_station_csv()

if not df_csv.empty:
    st.info(f"📂 관측소 목록 {len(df_csv)}개를 불러왔습니다.")
    
    if st.button("수위 조회 시작 (한국시간 적용)", type="primary"):
        
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 디버깅용 로그 (화면에 에러 원인을 보여주기 위함)
        error_logs = []
        
        total = len(df_csv)
        
        for i, row in df_csv.iterrows():
            code = row.get('수위코드') or row.get('코드')
            name = row.get('관측소명')
            addr = row.get('주소', '-')
            
            status_text.text(f"📡 {name}({code}) 조회 중...")
            
            # 조회
            data, msg = get_realtime_data_debug(code)
            
            if data:
                results.append({
                    '관측소명': name,
                    '현재수위(m)': data['수위(m)'],
                    '관측시간': data['관측시간'],
                    '상태': '✅ 정상',
                    '주소': addr
                })
            else:
                results.append({
                    '관측소명': name,
                    '현재수위(m)': 0.0, # 그래프용 기본값
                    '관측시간': '-',
                    '상태': f"❌ 실패 ({msg})", # 실패 원인을 표에 적음
                    '주소': addr
                })
                error_logs.append(f"[{name}] {msg}")
            
            progress_bar.progress((i + 1) / total)
            
        status_text.text("조회 완료.")
        
        if results:
            df_res = pd.DataFrame(results)
            st.divider()
            
            # 1. 정상 데이터만 보기 좋게 필터링
            st.subheader("📊 조회 결과")
            st.dataframe(df_res, use_container_width=True)
            
            # 2. 엑셀 다운로드
            csv_data = df_res.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 결과 엑셀 다운로드", csv_data, "수위분석결과.csv")
            
            # 3. [중요] 왜 안됐는지 알려주는 진단 리포트
            if error_logs:
                with st.expander("🚨 에러 원인 상세 보기 (개발자용)"):
                    st.warning("일부 지점에서 데이터를 가져오지 못했습니다. 아래 이유를 확인하세요.")
                    for log in error_logs:
                        st.write(log)
                    st.info("팁: 'Empty List'라면 해당 시간에 관측된 데이터가 없는 것이고, 'HTTP 에러'라면 서버 문제입니다.")
else:
    st.error("GitHub에 'station_list.csv' 파일이 없습니다.")
