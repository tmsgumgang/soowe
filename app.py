import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import urllib3
import time
import glob

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="금강 수계 모니터링", layout="wide")
st.title("🌊 금강 수계 실시간 현황 (수심 자동 변환)")
st.caption("해발고도(EL.m)로 들어오는 댐 주변 데이터를 수심(m)으로 자동 변환하여 보여줍니다.")

HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"
HEADERS = {'User-Agent': 'Mozilla/5.0'}

# ---------------------------------------------------------
# [설정] 강바닥 높이 (영점 표고) 보정값
# ---------------------------------------------------------
# 이원교 해발고도가 28.28m일 때, 수심이 2~3m가 되려면
# 강바닥 높이를 약 25.5m 정도로 빼주면 됩니다.
ZERO_POINT_MAP = {
    # 관측소명에 이 단어가 포함되면 -> 이만큼 뺍니다.
    "이원": 25.5,  # 이원교 (추정치)
    "대청댐": 0,    # 댐은 그냥 해발고도 보는 게 맞음 (빼지 않음)
    # 필요하면 다른 지점도 추가 가능
}

# ---------------------------------------------------------
# [핵심] 코드 자동 보정 지도
# ---------------------------------------------------------
CODE_MAP = {
    "3009660": "3009665", # 갑천교
    "3009670": "3009675", # 원촌교
    "3008680": "3008685", # 이원교
    "3012640": "3012633", # 공주보 -> 공주(금강교)
}

def fetch_realtime_smart(original_code, station_name):
    # 1. 코드 보정
    target_code = CODE_MAP.get(str(original_code), str(original_code))
    
    # 2. 한국 시간
    now = datetime.utcnow() + timedelta(hours=9)
    s_str = (now - timedelta(hours=72)).strftime("%Y%m%d%H%M")
    e_str = now.strftime("%Y%m%d%H%M")
    
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list/1H/{target_code}/{s_str}/{e_str}.json"
    
    try:
        r = requests.get(url, headers=HEADERS, verify=False, timeout=2)
        if r.status_code == 200:
            data = r.json()
            if 'content' in data and data['content']:
                # 최신값
                for item in reversed(data['content']):
                    wl = item.get('wl')
                    if wl and str(wl).strip() != '':
                        val = float(wl)
                        
                        # [핵심 로직] 해발고도 -> 수심 변환
                        # 1. 이름으로 영점 찾기
                        offset = 0
                        is_converted = False
                        
                        for key, zero_h in ZERO_POINT_MAP.items():
                            if key in station_name:
                                if val > zero_h: # 현재 수위가 강바닥보다 높을 때만
                                    offset = zero_h
                                    is_converted = True
                                break
                        
                        # 2. 만약 맵에 없는데 값이 20m가 넘으면? (일단 EL.m으로 표시)
                        # 이원교는 위에서 처리됨
                        
                        final_val = val - offset
                        
                        return {
                            '원본수위': val,
                            '보정수위': round(final_val, 2),
                            '변환여부': is_converted,
                            '시간': item['ymdhm'],
                            '코드': target_code
                        }, "성공"
    except: pass
    return None, "실패"

# ---------------------------------------------------------
# 메인 UI
# ---------------------------------------------------------
files = glob.glob("*.csv")
if files:
    target = "station_list.csv" if "station_list.csv" in files else files[0]
    df = pd.read_csv(target, dtype=str)
    
    if st.button("🌊 수심 변환 조회 시작", type="primary"):
        results = []
        bar = st.progress(0)
        
        for i, row in df.iterrows():
            code = row.get('수위코드') or row.get('코드')
            name = row.get('관측소명')
            
            time.sleep(0.1)
            data, msg = fetch_realtime_smart(code, name)
            
            if data:
                t = data['시간']
                t_fmt = f"{t[4:6]}/{t[6:8]} {t[8:10]}:{t[10:12]}"
                
                # 비고란에 설명 추가
                note = ""
                display_val = data['보정수위']
                
                if data['변환여부']:
                    note = f"해발 {data['원본수위']}m - 강바닥 {ZERO_POINT_MAP.get('이원',0)}m"
                    unit = "수심(m) [변환됨]"
                elif data['원본수위'] > 20:
                    unit = "해발고도(EL.m)" # 댐 같은 경우
                else:
                    unit = "수심(m)"
                
                results.append({
                    "관측소명": name,
                    "수위 값": display_val,
                    "단위": unit,
                    "관측시간": t_fmt,
                    "비고": note
                })
            else:
                results.append({
                    "관측소명": name,
                    "수위 값": "-",
                    "단위": "-",
                    "관측시간": "-",
                    "비고": "점검중"
                })
            bar.progress((i+1)/len(df))
            
        st.dataframe(pd.DataFrame(results), use_container_width=True)
else:
    st.error("CSV 파일이 없습니다.")
