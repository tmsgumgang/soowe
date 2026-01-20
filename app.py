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
st.set_page_config(page_title="금강 수계 최종 모니터링", layout="wide")
st.title("🌊 금강 수계 실시간 현황판 (스마트 보정)")
st.caption("사용자가 찾아낸 '진짜 코드'를 바탕으로 데이터를 자동으로 찾아옵니다.")

HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"
HEADERS = {'User-Agent': 'Mozilla/5.0'}

# ---------------------------------------------------------
# [핵심] 코드 자동 보정 지도 (성주님이 찾은 드래곤볼)
# ---------------------------------------------------------
# 엑셀에 왼쪽 코드가 적혀있으면 -> 오른쪽(진짜) 코드로 바꿔서 조회함
CODE_MAP = {
    # [대전/갑천]
    "3009660": "3009665", # 갑천교 (표준 -> 실시간용)
    "3009670": "3009675", # 원촌교 추정
    
    # [옥천/이원]
    "3008680": "3008685", # 이원교
    "3008655": "3008655", # 옥천대교 (그대로)
    
    # [공주/부여/세종]
    "3012640": "3012633", # 공주보 -> 공주(금강교) 인근 코드로 대체
    "3012630": "3012633", # 공주 금강교 -> 3012633 사용
    "3012620": "3012620", # 백제보 (그대로)
}

# ---------------------------------------------------------
# 데이터 조회 (해발고도/수심 자동 구분)
# ---------------------------------------------------------
def fetch_realtime_smart(original_code):
    # 1. 자동 보정 (매핑된 게 있으면 그걸 쓰고, 없으면 원래 거 씀)
    target_code = CODE_MAP.get(str(original_code), str(original_code))
    
    # 한국 시간
    now = datetime.utcnow() + timedelta(hours=9)
    
    # API 호출 (1시간 단위, 최근 3일)
    # * 10분 단위보다 1시간 단위가 훨씬 안정적임
    s_str = (now - timedelta(hours=72)).strftime("%Y%m%d%H%M")
    e_str = now.strftime("%Y%m%d%H%M")
    
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list/1H/{target_code}/{s_str}/{e_str}.json"
    
    try:
        r = requests.get(url, headers=HEADERS, verify=False, timeout=2)
        if r.status_code == 200:
            data = r.json()
            if 'content' in data and data['content']:
                # 최신순 탐색
                for item in reversed(data['content']):
                    wl = item.get('wl')
                    if wl and str(wl).strip() != '':
                        return {
                            '수위': float(wl),
                            '시간': item['ymdhm'],
                            '사용코드': target_code
                        }, "성공"
    except: pass
    
    return None, f"실패(코드:{target_code})"

# ---------------------------------------------------------
# 메인 UI
# ---------------------------------------------------------
# 파일 로드
files = glob.glob("*.csv")
target_file = None
if files:
    # station_list.csv 우선, 없으면 최신 파일
    target_file = "station_list.csv" if "station_list.csv" in files else files[0]

if target_file:
    df = pd.read_csv(target_file, dtype=str)
    st.info(f"📂 연동 파일: {target_file} (총 {len(df)}개 지점)")
    
    if st.button("🚀 실시간 데이터 조회 (자동 보정 적용)", type="primary"):
        
        results = []
        bar = st.progress(0)
        
        for i, row in df.iterrows():
            # 코드 & 이름 읽기
            raw_code = row.get('수위코드') or row.get('코드') or row.get('관측소코드')
            name = row.get('관측소명')
            
            # 서버 보호용 딜레이
            time.sleep(0.1)
            
            data, msg = fetch_realtime_smart(raw_code)
            
            if data:
                val = data['수위']
                t = data['시간']
                t_fmt = f"{t[4:6]}/{t[6:8]} {t[8:10]}:{t[10:12]}"
                
                # [단위 자동 판단]
                # 20m 이상이면 보통 해발고도(EL.m), 그 밑이면 수심(m)
                unit_type = "수심(m)"
                if val > 20: 
                    unit_type = "해발고도(EL.m)"
                
                results.append({
                    "관측소명": name,
                    "수위 값": val,
                    "단위": unit_type, # 여기서 해발고도인지 알려줌!
                    "관측시간": t_fmt,
                    "상태": "✅ 수신",
                    "보정된 코드": data['사용코드']
                })
            else:
                results.append({
                    "관측소명": name,
                    "수위 값": "-",
                    "단위": "-",
                    "관측시간": "-",
                    "상태": "❌ 점검중",
                    "보정된 코드": msg.split(':')[-1].replace(')','')
                })
            
            bar.progress((i+1)/len(df))
            
        # 결과 출력
        res_df = pd.DataFrame(results)
        st.dataframe(res_df, use_container_width=True)
        
        # 다운로드
        csv = res_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 조회 결과 다운로드", csv, "실시간수위_최종.csv")

else:
    st.error("CSV 파일이 없습니다. GitHub에 파일을 올려주세요.")
