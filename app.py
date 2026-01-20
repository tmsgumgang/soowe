import streamlit as st
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="API 연결 진단")
st.title("🩺 한강홍수통제소 API 정밀 진단")

# 사용자가 입력한 키
HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"

# 테스트할 지점 (가장 확실한 '공주보' 사용)
TEST_CODE = "3012640" 
TEST_NAME = "공주보 수위국"

if st.button("진단 시작 (서버 응답 뜯어보기)"):
    # 1. 요청 URL 만들기 (최근 1시간 데이터)
    now = datetime.now()
    start = now - timedelta(hours=1)
    
    # 포맷: YYYYMMDDHHMM
    s_str = start.strftime("%Y%m%d%H%M")
    e_str = now.strftime("%Y%m%d%H%M")
    
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list/10M/{TEST_CODE}/{s_str}/{e_str}.json"
    
    st.write("📡 **요청 보낸 주소 (URL):**")
    st.code(url.replace(HRFCO_KEY, "API_KEY_HIDDEN")) # 키는 가려서 보여줌
    
    try:
        # 2. 서버에 요청 보내기
        response = requests.get(url, verify=False)
        
        st.write(f"🚦 **HTTP 상태 코드:** {response.status_code}")
        
        # 3. 응답 내용 확인
        st.subheader("📨 서버가 보낸 원본 메시지:")
        raw_text = response.text
        
        if not raw_text:
            st.error("❌ 응답이 완전히 비어있습니다. (IP 차단 가능성)")
        else:
            # HTML/XML 에러인지 JSON인지 확인
            if "<" in raw_text and ">" in raw_text:
                 st.code(raw_text, language='xml') # XML/HTML 에러
                 st.warning("⚠️ XML이나 HTML이 왔습니다. 키 오류거나 주소 오류일 수 있습니다.")
            elif "{" in raw_text:
                 st.code(raw_text, language='json') # JSON 응답
                 st.success("✅ JSON 응답이 왔습니다. 내용을 확인하세요.")
            else:
                 st.code(raw_text)
                 
    except Exception as e:
        st.error(f"❌ 통신 오류 발생: {e}")
