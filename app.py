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
# 설정
# ---------------------------------------------------------
st.set_page_config(page_title="금강 수계 정밀 스캐너", layout="wide")
st.title("🕵️‍♀️ 수위 관측소 '코드 스캐너' & 데이터 조회")
st.caption("작동하지 않는 관측소? 주변 코드를 정밀 스캔해서 찾아냅니다.")

HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"
HEADERS = {'User-Agent': 'Mozilla/5.0'}

# ---------------------------------------------------------
# [핵심] 코드 스캐너 (주변 번호 탐색)
# ---------------------------------------------------------
def scan_codes(base_code, range_limit=20):
    """
    기준 코드(base_code)의 앞뒤 range_limit만큼을 다 찔러봅니다.
    """
    try:
        base = int(base_code)
    except:
        return [], "숫자만 입력하세요."
    
    # 탐색 범위 설정 (예: 3012640 -> 3012620 ~ 3012660)
    start_code = base - range_limit
    end_code = base + range_limit
    
    found_list = []
    
    # 진행률 바
    progress_text = st.empty()
    bar = st.progress(0)
    total = end_code - start_code + 1
    
    # 한국 시간 (최근 1시간 데이터 유무로 활성 상태 판단)
    now = datetime.utcnow() + timedelta(hours=9)
    s_str = (now - timedelta(hours=24)).strftime("%Y%m%d%H%M") # 넉넉히 24시간 전
    e_str = now.strftime("%Y%m%d%H%M")
    
    for i, code in enumerate(range(start_code, end_code + 1)):
        str_code = str(code)
        url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list/1H/{str_code}/{s_str}/{e_str}.json"
        
        try:
            # 타임아웃 짧게 (0.5초) 해서 빨리 넘김
            r = requests.get(url, headers=HEADERS, verify=False, timeout=0.5)
            if r.status_code == 200:
                data = r.json()
                if 'content' in data and data['content']:
                    # 살아있는 코드 발견!
                    last_data = data['content'][-1]
                    found_list.append({
                        "코드": str_code,
                        "관측소명": f"📍 발견됨! (수위: {last_data.get('wl', '-')}m)",
                        "최근관측": last_data.get('ymdhm', '-'),
                        "비고": "✅ 활성 상태"
                    })
        except:
            pass
        
        # 진행률 업데이트
        if i % 5 == 0:
            progress_text.text(f"스캔 중... {str_code}")
            bar.progress((i + 1) / total)
            time.sleep(0.05) # 서버 부하 방지
            
    progress_text.text("스캔 완료!")
    bar.progress(1.0)
    
    return found_list

# ---------------------------------------------------------
# 데이터 조회
# ---------------------------------------------------------
def fetch_realtime(code):
    if not code: return None, "코드없음"
    now = datetime.utcnow() + timedelta(hours=9)
    # 1시간 단위 (최근 3일)
    s_str = (now - timedelta(hours=72)).strftime("%Y%m%d%H%M")
    e_str = now.strftime("%Y%m%d%H%M")
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list/1H/{code}/{s_str}/{e_str}.json"
    
    try:
        r = requests.get(url, headers=HEADERS, verify=False, timeout=2)
        if r.status_code == 200:
            data = r.json()
            if 'content' in data and data['content']:
                for item in reversed(data['content']):
                    wl = item.get('wl')
                    if wl and str(wl).strip() != '':
                        return {'수위': float(wl), '시간': item['ymdhm']}, "성공"
    except: pass
    return None, "실패"

# ---------------------------------------------------------
# 메인 UI
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["📡 1. 코드 정밀 스캐너", "🌊 2. 데이터 조회"])

# 탭 1: 스캐너
with tab1:
    st.subheader("숨겨진 진짜 코드를 찾아라")
    st.markdown("""
    - **공주보**가 안 되면? 👉 `3012640` 입력 후 스캔 (주변 탐색)
    - **세종보**가 안 되면? 👉 `3012650` 입력 후 스캔
    - **원촌교**가 안 되면? 👉 `3009670` 입력 후 스캔
    """)
    
    c1, c2 = st.columns([1, 1])
    target_base = c1.text_input("기준 코드 입력 (예: 3012640)", "3012640")
    range_val = c2.slider("탐색 범위 (+/-)", 10, 50, 20)
    
    if st.button("🛰️ 스캔 시작", type="primary"):
        results = scan_codes(target_base, range_val)
        
        if results:
            st.success(f"🎉 총 {len(results)}개의 활성 코드를 찾았습니다!")
            st.dataframe(pd.DataFrame(results), use_container_width=True)
            st.info("위 표에서 수위 값이 정상적으로 나오는 코드를 복사해서 엑셀에 넣으세요.")
        else:
            st.warning("⚠️ 범위 내에서 활성 코드를 찾지 못했습니다. 기준 코드를 바꿔보세요.")

# 탭 2: 조회
with tab2:
    st.subheader("엑셀 파일 기반 조회")
    
    # 파일 로드
    files = glob.glob("*.csv")
    if files:
        target = "station_list.csv" if "station_list.csv" in files else files[0]
        st.caption(f"연동 파일: {target}")
        
        if st.button("데이터 조회"):
            df = pd.read_csv(target, dtype=str)
            res_list = []
            
            for i, row in df.iterrows():
                code = row.get('수위코드') or row.get('코드')
                name = row.get('관측소명')
                
                data, msg = fetch_realtime(code)
                time.sleep(0.1)
                
                wl_val = data['수위'] if data else 0
                # 20m가 넘으면 해발고도(EL.m)일 확률이 높음 (비고에 표시)
                note = "수심(m)"
                if wl_val > 20: note = "해발고도(EL.m)"
                if not data: note = "점검중"
                
                res_list.append({
                    "관측소명": name,
                    "코드": code,
                    "수위": wl_val if data else "-",
                    "단위": note,
                    "시간": data['시간'] if data else "-"
                })
            
            st.dataframe(pd.DataFrame(res_list), use_container_width=True)
    else:
        st.error("CSV 파일이 없습니다.")
