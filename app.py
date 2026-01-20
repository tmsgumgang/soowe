import streamlit as st
import pandas as pd
import requests

# ---------------------------------------------------------
# 1. 설정
# ---------------------------------------------------------
st.set_page_config(page_title="한강홍수통제소 코드 찾기")
st.title("🔎 관측소 '진짜 코드' 찾기")

HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"

# ---------------------------------------------------------
# 2. 전체 목록 조회 함수
# ---------------------------------------------------------
@st.cache_data
def get_all_stations():
    # 한강홍수통제소 수위 관측소 전체 목록 조회 URL
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list.json"
    
    try:
        response = requests.get(url, verify=False)
        data = response.json()
        
        # content 리스트 안에 관측소 정보가 들어있음
        if 'content' in data:
            df = pd.DataFrame(data['content'])
            # 필요한 컬럼만 선택 (코드, 이름, 주소)
            # wlobscd: 수위관측소코드, obsnm: 관측소명
            if 'wlobscd' in df.columns:
                return df[['obsnm', 'wlobscd', 'addr']]
            else:
                return df # 컬럼명이 다를 경우 전체 반환
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"목록 가져오기 실패: {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# 3. 메인 화면
# ---------------------------------------------------------
st.info("API 서버에 등록된 모든 관측소를 가져옵니다. 잠시만 기다리세요...")

df = get_all_stations()

if not df.empty:
    st.success(f"총 {len(df)}개의 관측소를 찾았습니다!")
    
    # 검색 기능
    keyword = st.text_input("검색할 지점명 (예: 공주, 갑천, 이원, 대청)", "갑천")
    
    if keyword:
        # 이름(obsnm)이나 주소(addr)에 키워드가 있는 행 필터링
        mask = df['obsnm'].str.contains(keyword) | df['addr'].str.contains(keyword, na=False)
        result = df[mask]
        
        if not result.empty:
            st.write(f"👇 **'{keyword}' 검색 결과 ({len(result)}건)**")
            st.dataframe(result, use_container_width=True)
            
            st.markdown("---")
            st.markdown("### 💡 발견된 코드를 확인하세요!")
            st.markdown("위 표의 **`wlobscd` (숫자 7자리)**가 진짜 코드입니다.")
        else:
            st.warning("검색 결과가 없습니다.")
else:
    st.error("관측소 목록을 가져오지 못했습니다. (API 키 확인 필요)")
