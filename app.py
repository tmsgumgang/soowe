import streamlit as st
import pandas as pd
import requests

# ---------------------------------------------------------
# 1. 설정 및 API 키
# ---------------------------------------------------------
st.set_page_config(page_title="관측소 코드 탐색기", layout="wide")

# API 키 설정 (Secrets에서 가져오거나, 없으면 코드에 있는 키 사용)
try:
    API_KEY = st.secrets["public_api_key"]
except:
    # 성주 님의 키 (로컬 테스트용 백업)
    API_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

# ---------------------------------------------------------
# 2. API 호출 함수
# ---------------------------------------------------------
def get_station_list(dam_code):
    """
    입력된 댐 코드(dam_code) 하위에 있는 수위 관측소 목록을 조회합니다.
    """
    # K-water 수위 관측소 목록 조회 API (Source: 기술문서 69번)
    url = "http://apis.data.go.kr/B500001/dam/excllncobsrvt/wal/wallist"
    
    params = {
        "serviceKey": API_KEY,
        "_type": "json",
        "damcode": dam_code
    }
    
    try:
        response = requests.get(url, params=params, verify=False)
        data = response.json()
        
        # 응답 구조 파싱
        if 'response' in data and 'body' in data['response']:
            items = data['response']['body']['items']
            if not items:
                return pd.DataFrame() # 데이터 없음
            
            # 리스트 추출
            item_list = items['item'] if 'item' in items else []
            if isinstance(item_list, dict):
                item_list = [item_list]
                
            return pd.DataFrame(item_list)
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"통신 오류: {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# 3. 메인 화면 (코드 찾기 UI)
# ---------------------------------------------------------
st.title("🔎 K-water 수위 관측소 코드 찾기")
st.markdown("""
데이터가 안 나오는 이유는 **'관측소 코드'**가 틀렸기 때문일 확률이 높습니다.
아래 버튼을 눌러 실제 존재하는 코드를 확인하세요.
""")

# 금강 수계 주요 댐/보 코드 후보군 (대권역 30, 10 등)
# 이 리스트는 K-water의 일반적인 코드 패턴을 기반으로 합니다.
dam_candidates = {
    "대청댐 (Daecheong)": "1003110",  # 대청댐은 보통 1003110 사용
    "용담댐 (Yongdam)": "1001110",
    "세종보 (Sejong-bo)": "3012120", 
    "공주보 (Gongju-bo)": "3012110",
    "백제보 (Baekje-bo)": "3012130",
    "금강하굿둑": "3011110"
}

# 사용자 선택
col1, col2 = st.columns([1, 2])

with col1:
    selected_name = st.radio("확인할 지점 선택", list(dam_candidates.keys()))
    target_dam_code = dam_candidates[selected_name]
    st.info(f"선택한 댐 코드: **{target_dam_code}**")

with col2:
    st.subheader("📋 조회 결과")
    
    if st.button("관측소 목록 조회하기", type="primary"):
        with st.spinner("K-water 서버에 물어보는 중..."):
            df_result = get_station_list(target_dam_code)
            
            if not df_result.empty:
                st.success(f"✅ '{selected_name}' 관련 관측소를 찾았습니다!")
                
                # 필요한 컬럼만 깔끔하게 표시
                # walobsrvtcode: 우리가 필요한 '수위관측소 코드'
                # obsrvtNm: 관측소 이름
                if 'walobsrvtcode' in df_result.columns:
                    display_df = df_result[['obsrvtNm', 'walobsrvtcode']]
                    st.dataframe(display_df, use_container_width=True)
                    
                    st.markdown("### 👉 중요: 아래 코드를 복사하세요!")
                    st.code(display_df.to_csv(index=False), language='csv')
                else:
                    st.write(df_result)
            else:
                st.warning(f"❌ '{target_dam_code}' 코드로는 조회된 관측소가 없습니다.")
                st.markdown("다른 지점을 선택하거나, 코드가 변경되었을 수 있습니다.")

# ---------------------------------------------------------
# 참고용 수동 조회
# ---------------------------------------------------------
with st.expander("🛠️ 댐 코드 직접 입력해서 찾기 (고급)"):
    manual_code = st.text_input("댐 코드 7자리 입력", "3003110")
    if st.button("직접 입력 조회"):
        df_manual = get_station_list(manual_code)
        if not df_manual.empty:
            st.dataframe(df_manual[['obsrvtNm', 'walobsrvtcode']])
        else:
            st.error("데이터 없음")
