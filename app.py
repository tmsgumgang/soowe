import streamlit as st
import requests
import json

# API 키
try:
    API_KEY = st.secrets["public_api_key"]
except:
    API_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

st.title("🔧 공주보/세종보 응답 뜯어보기")

# 확인하고 싶은 댐 코드들
targets = {
    "대청댐 (성공예상)": "1003110",
    "공주보 (실패원인확인)": "3012110",
    "세종보": "3012120",
    "백제보": "3012130"
}

selected_name = st.selectbox("확인할 지점", list(targets.keys()))
target_code = targets[selected_name]

if st.button("서버에 요청 보내기"):
    url = "http://apis.data.go.kr/B500001/dam/excllncobsrvt/wal/wallist"
    params = {
        "serviceKey": API_KEY,
        "_type": "json",
        "damcode": target_code
    }
    
    st.write(f"📡 요청 코드: `{target_code}`")
    
    try:
        response = requests.get(url, params=params, verify=False)
        
        # 1. 상태 코드 확인
        st.write(f"**HTTP 상태:** {response.status_code}")
        
        # 2. 원본 응답(Raw Text) 출력
        st.subheader("📨 서버가 보낸 원본 메시지")
        st.code(response.text)
        
        # 3. JSON 구조 분석
        data = response.json()
        items = data['response']['body']['items']
        
        if not items:
            st.error("결과: items가 비어있습니다. (데이터 없음)")
        else:
            st.success("결과: 데이터가 있습니다!")
            st.json(items)
            
    except Exception as e:
        st.error(f"에러 발생: {e}")
