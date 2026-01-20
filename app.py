import streamlit as st
import pandas as pd
import requests
import urllib.parse
import time

st.set_page_config(page_title="API 주소 정밀 탐지", layout="wide")
st.title("🕵️‍♂️ 수질자동측정망 '진짜 주소' 찾기")
st.caption("404 에러를 해결하기 위해, 가능한 모든 API 주소 패턴을 테스트합니다.")

# 사용자 키
USER_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"
ENCODED_KEY = urllib.parse.quote(USER_KEY)

# ---------------------------------------------------------
# 테스트할 주소 후보군 (가능성 높은 순서)
# ---------------------------------------------------------
# S03001: 용담호로 추정되는 코드
TEST_CODE = "S03001" 

CANDIDATE_URLS = [
    # 1. 실시간 수질 데이터 (가장 유력)
    ("getRealTimeWaterQualityList", "http://apis.data.go.kr/1480523/WaterQualityService/getRealTimeWaterQualityList"),
    
    # 2. 측정 정보 조회 (일반)
    ("getMeasuringList", "http://apis.data.go.kr/1480523/WaterQualityService/getMeasuringList"),
    
    # 3. 측정소 목록 조회
    ("getMsrstnList", "http://apis.data.go.kr/1480523/WaterQualityService/getMsrstnList"),
    
    # 4. 방사성 물질 조회 (혹시나 서비스 ID 확인용)
    ("getRadioActiveMaterList", "http://apis.data.go.kr/1480523/WaterQualityService/getRadioActiveMaterList"),
    
    # 5. 수생태 측정망 (다른 서비스 ID 가능성)
    ("getBioMsrstnList", "http://apis.data.go.kr/1480523/WaterQualityService/getBioMsrstnList"),
]

# ---------------------------------------------------------
# 메인 로직
# ---------------------------------------------------------
if st.button("🚀 주소 스캔 시작 (정답 찾기)", type="primary"):
    
    st.write("### 📡 스캔 결과 로그")
    found_url = None
    
    for name, url in CANDIDATE_URLS:
        # URL 조립
        full_url = f"{url}?serviceKey={ENCODED_KEY}&numOfRows=1&pageNo=1&returnType=json&ptNo={TEST_CODE}"
        
        try:
            r = requests.get(full_url, timeout=5)
            status = r.status_code
            
            if status == 200:
                try:
                    data = r.json()
                    st.success(f"✅ **[200 OK] {name}** - 접속 성공!")
                    st.json(data) # 데이터 내용 보여주기
                    found_url = url
                    break # 정답 찾으면 중단
                except:
                    st.warning(f"⚠️ **[200 OK] {name}** - 접속은 됐는데 JSON이 아님 (XML 에러 가능성)")
                    st.code(r.text[:200], language="xml")
                    
            elif status == 404:
                st.error(f"❌ **[404 Not Found] {name}** - 주소 틀림")
            elif status == 500:
                st.error(f"❌ **[500 Error] {name}** - 서버 내부 오류 (키 문제일 수 있음)")
                
        except Exception as e:
            st.error(f"🚫 통신 오류: {e}")
            
        time.sleep(0.5)
        
    st.divider()
    
    if found_url:
        st.success(f"🎉 **찾아낸 정답 주소:** `{found_url}`")
        st.info("이제 이 주소로 데이터를 조회하면 됩니다!")
    else:
        st.error("😢 모든 주소가 404입니다. 공공데이터포털의 '상세 기능' 명세를 다시 확인해야 합니다.")
        st.markdown("""
        **[체크리스트]**
        1. 공공데이터포털 > 마이페이지 > 활용신청현황 > **[국립환경과학원_수질자동측정망]** 클릭
        2. 상세설명에 적힌 **'오퍼레이션 명(Operation Name)'**이 무엇인지 확인해주세요.
           (예: `getRealTimeWaterQualityList`, `getAutoMeasuringList` 등)
        """)
