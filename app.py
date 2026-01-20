import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import urllib3
import time
import glob

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------
# 설정: 대시보드 스타일
# ---------------------------------------------------------
st.set_page_config(page_title="금강 수계 상황실", layout="wide")

# 제목 (새로고침 버튼 포함)
c1, c2 = st.columns([4, 1])
c1.title("🌊 금강 수계 실시간 상황실")
if c2.button("🔄 현황 새로고침"):
    st.rerun()

st.markdown("---")

HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"
HEADERS = {'User-Agent': 'Mozilla/5.0'}

# ---------------------------------------------------------
# [사전 정의] 스마트 보정 데이터
# ---------------------------------------------------------
# 1. 코드가 틀렸을 때 자동으로 바꿔주는 지도
CODE_MAP = {
    "3009660": "3009665", # 갑천교
    "3009670": "3009675", # 원촌교
    "3008680": "3008685", # 이원교
    "3012640": "3012633", # 공주보 -> 공주(금강교)
}

# 2. 해발고도(EL.m)를 수심(m)으로 바꾸기 위한 강바닥 높이
ZERO_POINT_MAP = {
    "이원": 25.5,  # 이원교 보정값
    "대청": 0,     # 댐은 해발고도 유지
}

# 3. 파일이 없을 때 보여줄 기본 지점들
DEFAULT_STATIONS = [
    {"관측소명": "갑천(갑천교)", "코드": "3009665"},
    {"관측소명": "옥천(이원교)", "코드": "3008685"},
    {"관측소명": "공주시(금강교)", "코드": "3012633"},
    {"관측소명": "세종보", "코드": "3012650"},
]

# ---------------------------------------------------------
# 데이터 로직: 3시간치 데이터 가져오기
# ---------------------------------------------------------
@st.cache_data(ttl=600) # 10분 캐싱 (너무 자주 호출하면 차단되니까)
def get_3h_trend(station_name, original_code):
    # 1. 코드 보정
    code = CODE_MAP.get(str(original_code), str(original_code))
    
    # 2. 시간 설정 (최근 3시간 + 여유분)
    now = datetime.utcnow() + timedelta(hours=9)
    start = now - timedelta(hours=4) # 4시간 전부터 조회
    
    s_str = start.strftime("%Y%m%d%H%M")
    e_str = now.strftime("%Y%m%d%H%M")
    
    # 10분 단위 API (그래프용)
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list/10M/{code}/{s_str}/{e_str}.json"
    
    try:
        r = requests.get(url, headers=HEADERS, verify=False, timeout=2)
        if r.status_code == 200:
            data = r.json()
            if 'content' in data and data['content']:
                df = pd.DataFrame(data['content'])
                
                # 데이터 전처리
                df['datetime'] = pd.to_datetime(df['ymdhm'], format='%Y%m%d%H%M')
                df['wl'] = pd.to_numeric(df['wl'], errors='coerce')
                df = df.dropna(subset=['wl']) # 빈값 제거
                
                if df.empty: return None, "데이터 없음"
                
                # [수심 변환 로직 적용]
                offset = 0
                for key, val in ZERO_POINT_MAP.items():
                    if key in station_name:
                        # 수위가 보정값보다 클 때만 적용 (해발고도일 확률 높음)
                        if df['wl'].mean() > val:
                            offset = val
                        break
                
                df['adj_wl'] = df['wl'] - offset
                df = df.sort_values('datetime')
                
                # 최근 3시간만 필터링
                cutoff = now - timedelta(hours=3)
                df_final = df[df['datetime'] >= cutoff]
                
                if df_final.empty: return None, "최근 데이터 없음"
                
                # 현재 수위와 단위 정보
                current_val = df_final.iloc[-1]['adj_wl']
                unit = "수심(m)" if offset > 0 or current_val < 20 else "해발(EL.m)"
                
                return {
                    'df': df_final[['datetime', 'adj_wl']],
                    'current': current_val,
                    'unit': unit,
                    'last_time': df_final.iloc[-1]['datetime'].strftime("%H:%M")
                }, "성공"
                
    except Exception as e:
        return None, f"에러: {e}"
        
    return None, "통신 실패"

# ---------------------------------------------------------
# 메인 화면 구성
# ---------------------------------------------------------

# 1. 관측소 목록 준비
station_list = []
files = glob.glob("*.csv")
if files:
    target = "station_list.csv" if "station_list.csv" in files else files[0]
    try:
        df_csv = pd.read_csv(target, dtype=str)
        for _, row in df_csv.iterrows():
            code = row.get('수위코드') or row.get('코드')
            name = row.get('관측소명')
            station_list.append({"관측소명": name, "코드": code})
        st.caption(f"📂 '{target}' 파일 연동됨")
    except:
        station_list = DEFAULT_STATIONS
else:
    station_list = DEFAULT_STATIONS
    st.caption("📂 연동된 파일이 없어 '기본 지점'을 표시합니다.")

# 2. 대시보드 그리기 (2열 그리드)
cols = st.columns(2) # 2칸씩 배치

for i, station in enumerate(station_list):
    col = cols[i % 2] # 왼쪽/오른쪽 번갈아가며
    
    with col:
        with st.container(border=True): # 카드박스 형태로 감싸기
            st.subheader(f"📍 {station['관측소명']}")
            
            # 데이터 로딩
            data, msg = get_3h_trend(station['관측소명'], station['코드'])
            
            if data:
                # 1. 큰 숫자로 현재 수위 표시
                delta = None
                if len(data['df']) >= 2:
                    # 전 시간 대비 증감 계산
                    prev = data['df'].iloc[-2]['adj_wl']
                    diff = data['current'] - prev
                    delta = f"{diff:+.2f}m"
                
                st.metric(
                    label=f"현재 수위 ({data['last_time']} 기준)",
                    value=f"{data['current']:.2f} {data['unit']}",
                    delta=delta
                )
                
                # 2. 그래프 그리기 (X축: 시간, Y축: 보정수위)
                chart_data = data['df'].set_index('datetime')
                st.line_chart(chart_data, height=200, color="#0068c9")
                
            else:
                st.error(f"데이터 수신 실패 ({msg})")
                st.caption("잠시 후 '새로고침'을 눌러주세요.")
            
            time.sleep(0.1) # 서버 부하 방지
