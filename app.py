import streamlit as st
import pandas as pd
import requests

# API 키 설정
try:
    API_KEY = st.secrets["public_api_key"]
except:
    API_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

st.title("🔎 수질 측정소 검색 (이원/갑천)")

if st.button("전체 목록에서 검색"):
    # numOfRows를 500으로 늘려서 전체 목록을 다 가져옵니다.
    url = "http://apis.data.go.kr/1480523/WaterQualityService/getMsrstnList"
    params = {
        "serviceKey": API_KEY,
        "numOfRows": "500",  # 넉넉하게 조회
        "pageNo": "1",
        "returnType": "json"
    }
    
    with st.spinner("전국 측정소를 뒤지는 중..."):
        try:
            response = requests.get(url, params=params)
            data = response.json()
            items = data['getMsrstnList']['item']
            df = pd.DataFrame(items)
            
            # '이원' 또는 '갑천'이 포함된 측정소만 필터링
            target_keywords = ['이원', '갑천', '대청', '금강']
            # ptNm(측정소명)에 키워드가 포함된 행 찾기
            mask = df['ptNm'].str.contains('|'.join(target_keywords))
            filtered_df = df[mask]
            
            if not filtered_df.empty:
                st.success(f"찾았습니다! 총 {len(filtered_df)}개 발견")
                st.dataframe(filtered_df[['ptNm', 'ptNo', 'addr']]) # 이름, 코드, 주소
            else:
                st.warning("검색 결과가 없습니다.")
                
        except Exception as e:
            st.error(f"에러 발생: {e}")
