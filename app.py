import streamlit as st
import pandas as pd
import requests
import urllib.parse

st.set_page_config(page_title="API 정밀 진단", layout="wide")
st.title("🔧 공공데이터포털 API 정밀 진단기")

# 사용자 제공 인증키 (Decoded)
USER_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

# ---------------------------------------------------------
# 1. 수질자동측정망 (국립환경과학원) 진단
# ---------------------------------------------------------
def debug_water_quality():
    url = "http://apis.data.go.kr/1480523/WaterQualityService/getMsrstnList"
    
    # 공공데이터포털은 키 인코딩에 매우 민감합니다.
    # Case A: 디코딩된 키 그대로 전송
    params = {
        "serviceKey": USER_KEY,
        "numOfRows": "100",
        "pageNo": "1",
        "returnType": "json"
    }
    
    try:
        r = requests.get(url, params=params, timeout=10)
        
        st.write(f"**[응답 상태코드]**: {r.status_code}")
        
        try:
            # JSON 파싱 시도
            data = r.json()
            st.success("✅ JSON 파싱 성공!")
            
            # 목록 추출
            if 'getMsrstnList' in data and 'item' in data['getMsrstnList']:
                items = data['getMsrstnList']['item']
                df = pd.DataFrame(items)
                st.dataframe(df[['ptNo', 'ptNm', 'addr']], use_container_width=True)
                return
            else:
                st.warning("JSON은 왔지만 목록이 비어있습니다.")
                st.json(data)
                
        except ValueError:
            # JSON이 아님 -> XML 에러 메시지일 확률 99%
            st.error("❌ JSON 파싱 실패 (서버가 XML 에러를 보냈습니다)")
            st.code(r.text, language="xml") # 에러 내용을 그대로 보여줌
            
            # 에러 내용 분석
            if "SERVICE_KEY_IS_NOT_REGISTERED" in r.text:
                st.error("👉 진단: 키가 아직 등록되지 않았다고 합니다. (포털 서버 동기화 지연)")
            elif "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in r.text:
                st.error("👉 진단: 일일 트래픽 초과 혹은 계정 문제")
            elif "SERVICE ACCESS DENIED" in r.text:
                st.error("👉 진단: 해당 서비스(자동측정망) 신청이 안 된 상태")
            
    except Exception as e:
        st.error(f"통신 에러: {e}")

# ---------------------------------------------------------
# 2. 수위 관측소 (한강홍수통제소) 진단
# ---------------------------------------------------------
def debug_water_level():
    # 한강홍수통제소 직접 호출 (차단 확인용)
    url = "http://api.hrfco.go.kr/F09631CC-1CFB-4C55-8329-BE03A787011E/waterlevel/list.json"
    
    try:
        r = requests.get(url, timeout=5)
        st.success("✅ 접속 성공 (IP 차단 아님)")
        st.json(r.json())
    except Exception as e:
        st.error(f"❌ 접속 실패: {e}")
        if "ConnectionReset" in str(e) or "104" in str(e):
            st.error("""
            👉 **진단: IP 차단 (Firewall Blocking)**
            한강홍수통제소 서버가 Streamlit Cloud 서버의 접속을 막고 있습니다.
            이건 키 문제가 아닙니다. 
            (해결책: 로컬 PC에서 돌리거나, IP 우회 기술이 필요합니다.)
            """)

# ---------------------------------------------------------
# 실행 버튼
# ---------------------------------------------------------
c1, c2 = st.columns(2)

with c1:
    st.subheader("🧪 1. 수질자동측정망 (용담호 등)")
    if st.button("수질 API 테스트"):
        debug_water_quality()

with c2:
    st.subheader("🌊 2. 수위 관측소 (갑천 등)")
    if st.button("수위 API 테스트"):
        debug_water_level()
