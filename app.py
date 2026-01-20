import streamlit as st
import pandas as pd
import requests
import json

# API 키 설정
try:
    API_KEY = st.secrets["public_api_key"]
except:
    API_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

st.title("🔎 수질 측정소 검색 (디버깅 모드)")

if st.button("전체 목록에서 검색"):
    url = "http://apis.data.go.kr/1480523/WaterQualityService/getMsrstnList"
    params = {
        "serviceKey": API_KEY,
        "numOfRows": "100",  # 일단 100개만 요청해봅니다
        "pageNo": "1",
        "returnType": "json" # JSON 요청
    }
    
    with st.spinner("데이터를 가져오는 중..."):
        try:
            response = requests.get(url, params=params, timeout=10)
            
            # 1. 상태 코드 확인
            if response.status_code != 200:
                st.error(f"❌ 서버 접속 실패! 상태 코드: {response.status_code}")
                st.stop()

            # 2. 원본 텍스트 확인 (여기서 에러 원인이 보입니다)
            raw_text = response.text.strip()
            
            # 만약 빈 문자열이면
            if not raw_text:
                st.error("❌ 서버가 아무런 내용도 보내지 않았습니다. (Empty Response)")
                st.stop()
                
            # JSON 파싱 시도
            try:
                data = response.json()
                items = data['getMsrstnList']['item']
                df = pd.DataFrame(items)
                
                # 검색 로직
                target_keywords = ['이원', '갑천', '대청', '금강']
                mask = df['ptNm'].str.contains('|'.join(target_keywords))
                filtered_df = df[mask]
                
                if not filtered_df.empty:
                    st.success(f"성공! {len(filtered_df)}개 발견")
                    st.dataframe(filtered_df[['ptNm', 'ptNo', 'addr']])
                else:
                    st.warning("검색 결과가 없습니다.")
                    
            except json.JSONDecodeError:
                # 🚨 여기가 문제의 원인입니다!
                st.error("❌ 서버가 JSON이 아닌 데이터를 보냈습니다.")
                st.warning("▼ 서버가 보낸 실제 내용 (XML 에러 메시지일 확률 높음)")
                st.code(raw_text, language='xml') # 내용을 화면에 출력
                
        except Exception as e:
            st.error(f"알 수 없는 에러 발생: {e}")
