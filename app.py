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
# 기본 설정
# ---------------------------------------------------------
st.set_page_config(page_title="금강 수계 실시간 모니터링", layout="wide")
st.title("🌊 금강 수계 실시간 수위 (코드 검증 & 조회)")
st.caption("실시간 데이터가 안 나온다면? '코드 찾기' 탭에서 진짜 코드를 확인하세요!")

HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"
HEADERS = {'User-Agent': 'Mozilla/5.0'}

# ---------------------------------------------------------
# [기능 1] 모든 관측소 목록 가져오기 (코드 찾기용)
# ---------------------------------------------------------
@st.cache_data
def get_all_stations():
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list.json"
    try:
        res = requests.get(url, headers=HEADERS, verify=False, timeout=5)
        data = res.json()
        if 'content' in data:
            df = pd.DataFrame(data['content'])
            # 보기 좋게 컬럼 정리
            df = df.rename(columns={
                'wlobscd': '표준코드', 
                'obsnm': '관측소명', 
                'addr': '주소',
                'agcnm': '관리기관'
            })
            return df[['관측소명', '표준코드', '주소', '관리기관']]
    except:
        pass
    return pd.DataFrame()

# ---------------------------------------------------------
# [기능 2] 실시간(10분) 데이터 조회
# ---------------------------------------------------------
def fetch_realtime(code):
    if not code: return None, "코드없음"
    
    # 한국 시간 기준
    now = datetime.utcnow() + timedelta(hours=9)
    
    # [1차 시도] 진짜 실시간 = 10분 단위 (최근 2시간)
    # 이 API가 성공해야 "실시간"입니다.
    res_10m = try_api(code, '10M', now, 2)
    if res_10m: return res_10m, "🟢 실시간(10분)"
    
    # [2차 시도] 차선책 = 1시간 단위 (최근 24시간)
    # 10분 데이터가 없으면 이거라도 보여줍니다.
    res_1h = try_api(code, '1H', now, 24)
    if res_1h: return res_1h, "🟡 최근값(1시간)"
    
    return None, "❌ 데이터 없음"

def try_api(code, unit, now, hours):
    start = now - timedelta(hours=hours)
    s_str = start.strftime("%Y%m%d%H%M")
    e_str = now.strftime("%Y%m%d%H%M")
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list/{unit}/{code}/{s_str}/{e_str}.json"
    
    try:
        r = requests.get(url, headers=HEADERS, verify=False, timeout=2)
        if r.status_code == 200:
            data = r.json()
            if 'content' in data and data['content']:
                # 최신순으로 뒤집어서 유효한 값 찾기
                for item in reversed(data['content']):
                    if item.get('wl') and str(item['wl']).strip() != '':
                        return {'수위': item['wl'], '시간': item['ymdhm']}
    except: pass
    return None

# ---------------------------------------------------------
# [공통] CSV 파일 로드
# ---------------------------------------------------------
def load_csv():
    files = glob.glob("*.csv")
    if not files: return pd.DataFrame(), None
    
    # station_list.csv 우선, 없으면 최신 파일
    target = "station_list.csv" if "station_list.csv" in files else files[0]
    
    try:
        df = pd.read_csv(target, dtype=str)
        return df, target
    except:
        return pd.DataFrame(), None

# ---------------------------------------------------------
# 메인 UI
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["🔍 1. 진짜 코드 찾기 (필수)", "🌊 2. 실시간 모니터링"])

# --- 탭 1: 코드 찾기 ---
with tab1:
    st.markdown("### 🕵️‍♀️ 관측소 이름으로 '진짜 코드'를 찾으세요")
    st.info("API 에러(920)가 뜨는 이유는 엑셀 파일의 코드가 틀렸기 때문입니다. 여기서 검색한 코드를 엑셀에 붙여넣으세요!")
    
    if st.button("전체 관측소 목록 불러오기"):
        with st.spinner("한강홍수통제소 서버 접속 중..."):
            all_stations = get_all_stations()
            if not all_stations.empty:
                st.session_state['all_stations'] = all_stations
                st.success(f"총 {len(all_stations)}개 관측소 로드 완료!")
            else:
                st.error("목록을 가져오지 못했습니다.")
    
    if 'all_stations' in st.session_state:
        search = st.text_input("검색어 (예: 갑천, 이원, 공주)", "")
        if search:
            mask = st.session_state['all_stations'].apply(lambda x: x.astype(str).str.contains(search)).any(axis=1)
            result = st.session_state['all_stations'][mask]
            st.dataframe(result, use_container_width=True)
            st.warning("☝️ 위 표에 나온 **'표준코드'**가 정답입니다. 이 코드를 엑셀 파일의 '수위코드' 란에 적으세요.")

# --- 탭 2: 모니터링 ---
with tab2:
    st.markdown("### 📊 엑셀 파일 연동 실시간 조회")
    
    df_csv, fname = load_csv()
    
    if df_csv.empty:
        st.error("CSV 파일이 없습니다.")
    else:
        st.success(f"📂 사용 중인 파일: `{fname}` ({len(df_csv)}개 지점)")
        
        if st.button("실시간 데이터 조회 시작", type="primary"):
            results = []
            bar = st.progress(0)
            
            for i, row in df_csv.iterrows():
                # 코드 컬럼 찾기
                code = row.get('수위코드') or row.get('코드') or row.get('관측소코드')
                name = row.get('관측소명')
                
                # 조회
                data, status = fetch_realtime(code)
                time.sleep(0.1) # 서버 보호
                
                if data:
                    t = data['시간'] # YYYYMMDDHHMM
                    t_show = f"{t[8:10]}:{t[10:12]}" # HH:MM
                    
                    results.append({
                        '관측소명': name,
                        '현재수위(m)': data['수위'],
                        '관측시간': t_show,
                        '상태': status,
                        '사용코드': code
                    })
                else:
                    results.append({
                        '관측소명': name,
                        '현재수위(m)': "-",
                        '관측시간': "-",
                        '상태': status, # 여기에 에러 원인 표시됨
                        '사용코드': code
                    })
                
                bar.progress((i+1)/len(df_csv))
            
            # 결과 표시
            st.dataframe(pd.DataFrame(results), use_container_width=True)
            st.caption("✅ '실시간(10분)'이 뜨면 성공! '데이터 없음'이면 코드를 다시 확인하세요.")
