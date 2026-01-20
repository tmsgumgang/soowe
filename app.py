import streamlit as st
import requests

st.set_page_config(page_title="API 키 정밀 진단")
st.title("🔑 API 키 정밀 테스트 (환경공단)")

# 1. 입력하신 키
USER_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

st.write(f"**테스트할 키:** `{USER_KEY}`")

# 2. 요청 보낼 주소 (수질 측정소 목록 조회)
url = "http://apis.data.go.kr/1480523/WaterQualityService/getMsrstnList"

# 3. 파이썬용 파라미터 (Decoding 키 그대로 사용)
params = {
    "serviceKey": USER_KEY,
    "numOfRows": "1",
    "pageNo": "1",
    "returnType": "json"  # JSON으로 달라고 요청
}

if st.button("서버 찔러보기 (테스트 시작)"):
    try:
        # User-Agent 헤더 추가 (봇 차단 방지)
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        st.subheader("📨 서버 응답 결과")
        st.write(f"**HTTP 상태 코드:** {response.status_code} (200이면 통신 성공)")
        
        # 내용물 확인
        raw_text = response.text
        
        if "<SERVICE_KEY_IS_NOT_REGISTERED>" in raw_text:
            st.error("🚨 결과: SERVICE_KEY_IS_NOT_REGISTERED")
            st.warning("👉 원인: 키는 맞는데, 아직 서버에 등록이 안 된 상태입니다. 1시간 뒤에 다시 해보세요!")
            
        elif "<OpenAPI_ServiceResponse>" in raw_text:
            st.code(raw_text, language="xml")
            st.error("🚨 결과: 인증 에러 발생 (상세 내용 위 참조)")
            
        elif "response" in raw_text or "getMsrstnList" in raw_text:
            st.success("✅ 성공! 키가 정상 작동 중입니다.")
            st.json(response.json())
            
        else:
            st.info("❓ 알 수 없는 응답입니다. 내용을 확인하세요:")
            st.code(raw_text)
            
    except Exception as e:
        st.error(f"❌ 통신 실패: {e}")
