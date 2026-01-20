import streamlit as st
import pandas as pd
import requests
import urllib.parse

st.set_page_config(page_title="관측소 명단 확보", layout="wide")
st.title("📋 관측소 명단 리스트업 (2단계)")

# 사용자 인증키 (Decoded)
USER_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

# ---------------------------------------------------------
# 1. [성공] 수위 관측소 (데이터 파싱 및 필터링)
# ---------------------------------------------------------
@st.cache_data
def load_water_level_list():
    # 1단계에서 성공한 그 주소 그대로 사용
    HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list.json"
    
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if 'content' in data:
            df = pd.DataFrame(data['content'])
            # 보기 좋게 컬럼 정리
            # obsnm:관측소명, wlobscd:코드, agcnm:관리기관, addr:주소
            if 'obsnm' in df.columns:
                df = df[['obsnm', 'wlobscd', 'addr', 'agcnm']]
                df.columns = ['관측소명', '코드', '주소', '관리기관']
                return df
    except:
        pass
    return pd.DataFrame()

# ---------------------------------------------------------
# 2. [수정] 수질자동측정망 (404 에러 해결 시도)
# ---------------------------------------------------------
def load_water_quality_list_fixed():
    # 404 에러 원인: 키 인코딩 문제일 가능성 99%
    # 해결책: params 딕셔너리를 쓰지 않고, URL에 키를 직접 문자열로 박아넣음
    
    base_url = "http://apis.data.go.kr/1480523/WaterQualityService/getMsrstnList"
    
    # 1. 키를 URL 인코딩 (공공데이터포털은 인코딩된 키를 원함)
    encoded_key = urllib.parse.quote(USER_KEY)
    
    # 2. 완성된 URL 수동 조립
    query_url = f"{base_url}?serviceKey={encoded_key}&numOfRows=100&pageNo=1&returnType=json"
    
    try:
        r = requests.get(query_url, timeout=10)
        
        if r.status_code == 200:
            try:
                data = r.json()
                if 'getMsrstnList' in data and 'item' in data['getMsrstnList']:
                    items = data['getMsrstnList']['item']
                    df = pd.DataFrame(items)
                    # 필요한 컬럼만
                    if 'ptNm' in df.columns:
                        df = df[['ptNm', 'ptNo', 'addr']]
                        df.columns = ['측정소명', '코드', '주소']
                        return df, "성공"
            except:
                return None, "JSON 변환 실패 (키 인증은 됐으나 데이터가 XML임)"
        elif r.status_code == 404:
            return None, "여전히 404 (주소 오류)"
        elif r.status_code == 500:
            return None, "500 에러 (서버 내부 오류 - 키 문제일 수음)"
            
    except Exception as e:
        return None, str(e)
        
    return None, f"상태코드: {r.status_code}"

# ---------------------------------------------------------
# 메인 화면
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["🌊 수위 관측소 (성공)", "🧪 수질 측정소 (재시도)"])

# 탭 1: 수위 (이미 성공했으므로 예쁘게 보여주기만 하면 됨)
with tab1:
    st.subheader("✅ 수위 관측소 명단 (한강홍수통제소)")
    
    df_wl = load_water_level_list()
    if not df_wl.empty:
        # 우리가 원하는 '갑천', '이원' 등이 있는지 검색 기능 제공
        search = st.text_input("수위 관측소 검색", "갑천")
        
        if search:
            mask = df_wl['관측소명'].str.contains(search)
            st.dataframe(df_wl[mask], use_container_width=True)
        else:
            st.dataframe(df_wl, use_container_width=True)
        
        st.success(f"총 {len(df_wl)}개의 관측소 데이터를 확보했습니다.")
    else:
        st.error("데이터를 가져오지 못했습니다.")

# 탭 2: 수질 (404 잡기)
with tab2:
    st.subheader("🛠️ 수질 측정소 명단 (용담호~부여)")
    
    if st.button("수질 목록 가져오기 (강제 주입 방식)"):
        df_wq, msg = load_water_quality_list_fixed()
        
        if df_wq is not None:
            st.success("🎉 드디어 뚫렸습니다! 목록을 확인하세요.")
            
            # 주요 지점 확인
            targets = ["용담", "봉황", "이원", "장계", "옥천", "대청", "현도", "갑천", "미호", "남면", "공주", "유구", "부여"]
            mask = df_wq['측정소명'].apply(lambda x: any(t in x for t in targets))
            target_df = df_wq[mask]
            
            if not target_df.empty:
                st.write("##### 🎯 주요 관심 지점 (확인됨)")
                st.dataframe(target_df, use_container_width=True)
            
            with st.expander("전체 목록 보기"):
                st.dataframe(df_wq)
        else:
            st.error(f"실패: {msg}")
            st.info("여전히 404라면, '국립환경과학원' API 서버 주소가 변경되었거나 일시적 점검일 수 있습니다.")
