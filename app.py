import streamlit as st
import pandas as pd
import requests
import urllib.parse
import time
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="에러 정밀 분석", layout="wide")
st.title("🩺 API 에러 정밀 해독기")
st.caption("서버가 보낸 'XML 에러 메시지'를 뜯어보고, 진짜 코드를 찾습니다.")

# 사용자 정보
USER_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"
ENCODED_KEY = urllib.parse.quote(USER_KEY)
BASE_URL = "https://apis.data.go.kr/1480523/WaterQualityService/getRealTimeWaterQualityList"

# ---------------------------------------------------------
# 테스트할 코드들 (WAMIS 코드 vs 공공데이터 S코드)
# ---------------------------------------------------------
TEST_TARGETS = [
    # 1. 사용자님이 원하시는 WAMIS 코드 (용담호)
    {"type": "WAMIS코드", "code": "2003660", "name": "용담호(WAMIS)"},
    # 2. 공공데이터포털 전용 코드 (금강 S코드 추정)
    {"type": "S코드", "code": "S03001", "name": "S코드 테스트1"},
    {"type": "S코드", "code": "S03002", "name": "S코드 테스트2"},
]

def analyze_response(station_code):
    # ptNo로 시도 (표준)
    params = f"?serviceKey={ENCODED_KEY}&numOfRows=1&pageNo=1&returnType=json&ptNo={station_code}"
    full_url = BASE_URL + params
    
    try:
        r = requests.get(full_url, verify=False, timeout=5)
        
        # 1. 상태코드 확인
        if r.status_code != 200:
            return f"HTTP 에러: {r.status_code}", False

        # 2. 내용 확인 (JSON vs XML)
        try:
            data = r.json()
            # 정상 JSON임
            if 'getRealTimeWaterQualityList' in data:
                return data, True
            else:
                return f"JSON은 왔으나 데이터 없음: {str(data)[:100]}", False
        except:
            # 3. JSON 파싱 실패 -> XML 에러 메시지 반환
            return f"XML 응답 (에러내용): {r.text}", False
            
    except Exception as e:
        return f"통신 에러: {e}", False

# ---------------------------------------------------------
# 메인 실행
# ---------------------------------------------------------
st.info("👇 아래 버튼을 누르면 서버가 보낸 '진짜 메시지'를 확인합니다.")

if st.button("🚀 정밀 진단 시작", type="primary"):
    
    for item in TEST_TARGETS:
        st.divider()
        st.subheader(f"🧪 테스트: {item['name']} ({item['code']})")
        
        result, is_success = analyze_response(item['code'])
        
        if is_success:
            st.success("✅ **성공! 데이터가 들어왔습니다.**")
            st.json(result) # 성공한 데이터 보여줌
        else:
            st.error("❌ **실패 (원인 분석)**")
            # 에러 메시지를 눈에 띄게 보여줌
            st.code(result, language='xml')
            
            # 에러 내용 해석
            if "SERVICE_KEY_IS_NOT_REGISTERED" in str(result):
                st.warning("👉 진단: 키 등록이 안 됨 (승인은 났지만 서버 반영 지연 중)")
            elif "NODATA_ERROR" in str(result):
                st.warning("👉 진단: 코드가 틀림 (이 코드는 데이터가 없음)")
            elif "INVALID_REQUEST_PARAMETER" in str(result):
                st.warning("👉 진단: 파라미터 이름 틀림 (ptNo 대신 다른 걸 써야 할 수도?)")
