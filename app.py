import streamlit as st
import requests
import pandas as pd
import urllib3
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="진짜 코드 찾기", layout="wide")
st.title("🕵️‍♂️ 수위 관측소 '진짜 코드' 발굴기")
st.caption("표준 코드가 안 먹힐 때, API가 반응하는 실제 코드를 찾아냅니다.")

HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"
HEADERS = {'User-Agent': 'Mozilla/5.0'}

# ---------------------------------------------------------
# 우리가 찾아야 할 지점들의 '코드 후보군'
# ---------------------------------------------------------
# (표준코드, 구형코드, 인근지점 코드 등을 모두 포함)
CANDIDATES = {
    "갑천(갑천교)": ["3009660", "3009665", "3009635"], # 635는 가수원교
    "갑천(원촌교)": ["3009670", "3009675"],
    "옥천(이원교)": ["3008680", "3008685", "3008655"], # 655는 옥천대교
    "공주보": ["3012640", "3012641", "3012642"],
    "세종보": ["3012650", "3012651"],
    "백제보": ["3012620", "3012621"],
    "대청댐": ["1003660", "1003661", "1003602"],
}

def check_code_alive(code):
    """
    이 코드가 API에서 살아있는지 확인 (1시간 데이터로 테스트)
    """
    # URL: 최근 3시간 데이터 요청
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list/1H/{code}/202601201800/202601202100.json"
    try:
        r = requests.get(url, headers=HEADERS, verify=False, timeout=2)
        if r.status_code == 200:
            data = r.json()
            # 내용물이 있고 에러 메시지가 없어야 함
            if 'content' in data and data['content']:
                return True, data['content'][0]['wl'] # 수위값 리턴
            if 'message' in data:
                return False, data['message']
    except:
        pass
    return False, "통신실패"

# ---------------------------------------------------------
# 메인 실행
# ---------------------------------------------------------
if st.button("🔍 진짜 코드 찾기 시작", type="primary"):
    
    results = []
    bar = st.progress(0)
    total = sum(len(codes) for codes in CANDIDATES.values())
    current = 0
    
    for name, codes in CANDIDATES.items():
        st.write(f"Testing {name}...")
        found = False
        
        for code in codes:
            # 서버 부하 방지
            time.sleep(0.1)
            
            is_alive, msg = check_code_alive(code)
            
            if is_alive:
                results.append({
                    "지점명": name,
                    "✅ 작동하는 코드": code,
                    "현재 수위": msg,
                    "상태": "성공"
                })
                found = True
                break # 찾았으면 다음 지점으로
            else:
                # 실패 로그 (디버깅용)
                # results.append({"지점명": name, "코드": code, "상태": f"실패({msg})"})
                pass
            
            current += 1
            bar.progress(min(current / total, 1.0))
            
        if not found:
             results.append({
                "지점명": name,
                "✅ 작동하는 코드": "❌ 없음",
                "현재 수위": "-",
                "상태": "모든 후보 실패"
            })

    st.divider()
    st.subheader("🎉 발굴 결과")
    st.dataframe(pd.DataFrame(results), use_container_width=True)
    st.info("위 표에서 '작동하는 코드'를 복사해서 엑셀 파일의 코드를 바꿔주세요!")
