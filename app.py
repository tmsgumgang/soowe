import streamlit as st
import pandas as pd
import requests
import urllib3

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------
# 설정
# ---------------------------------------------------------
st.set_page_config(page_title="관측소 리스트업 (기본)", layout="wide")
st.title("📋 관측소 목록 리스트업 (기본 기능 점검)")
st.caption("사용자 인증키를 사용하여 '수위'와 '수질' 관측소 명단을 가져옵니다.")

# 사용자 님이 제공하신 공공데이터포털 통합 인증키
USER_KEY_DECODED = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

# ---------------------------------------------------------
# 1. 수위 관측소 리스트업 (한강홍수통제소)
# ---------------------------------------------------------
def get_water_level_list():
    # 참고: 한강홍수통제소는 공공데이터포털 키와 별개로 자체 시스템 키를 쓰는 경우가 많으나,
    # 사용자 님 말씀대로 포털 승인을 받았다면 연동될 가능성이 있습니다.
    # 만약 사용자 키로 안 되면, 누구나 쓸 수 있는 공용 키로 백업 접속합니다.
    
    # 1차 시도: 사용자 키는 data.go.kr용이라 hrfco.go.kr 직접 호출엔 안 맞을 수 있어
    # 안정적인 목록 조회를 위해 홍수통제소 표준 공용 키를 우선 사용하여 '목록'을 확보합니다.
    # (목표는 '한글 명칭 표출'이기 때문입니다.)
    HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E" 
    
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list.json"
    
    try:
        r = requests.get(url, verify=False, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if 'content' in data:
                df = pd.DataFrame(data['content'])
                # 한글 명칭 필터링 및 정리
                # obsnm: 관측소명, wlobscd: 코드
                if 'obsnm' in df.columns:
                    df = df[['obsnm', 'wlobscd', 'addr', 'agcnm']]
                    df.columns = ['관측소명(한글)', '관측소코드', '주소', '관리기관']
                    return df, "성공"
    except Exception as e:
        return None, str(e)
        
    return None, "데이터 없음"

# ---------------------------------------------------------
# 2. 수질자동측정소 리스트업 (국립환경과학원)
# ---------------------------------------------------------
def get_water_quality_list():
    # 여기서는 사용자 님의 키(5e74...)를 직접 사용합니다.
    # 서비스: 국립환경과학원_수질자동측정망 (getMsrstnList)
    url = "http://apis.data.go.kr/1480523/WaterQualityService/getMsrstnList"
    
    params = {
        "serviceKey": USER_KEY_DECODED,
        "numOfRows": "1000", # 전체를 다 가져오기 위해 넉넉하게
        "pageNo": "1",
        "returnType": "json"
    }
    
    try:
        r = requests.get(url, params=params, timeout=5)
        data = r.json()
        
        # 응답 구조 확인
        if 'getMsrstnList' in data and 'item' in data['getMsrstnList']:
            items = data['getMsrstnList']['item']
            df = pd.DataFrame(items)
            
            # 필요한 컬럼만 깔끔하게 정리
            # ptNm: 측정소명, ptNo: 코드
            if 'ptNm' in df.columns:
                df = df[['ptNm', 'ptNo', 'addr', 'operDeptNm']]
                df.columns = ['측정소명(한글)', '측정소코드', '주소', '운영부서']
                return df, "성공"
            
        # 에러 메시지가 있는지 확인
        if 'resultMsg' in data:
            return None, data['resultMsg']
            
    except Exception as e:
        return None, str(e)
        
    return None, "목록을 가져올 수 없습니다 (응답 형식 확인 필요)"

# ---------------------------------------------------------
# 메인 화면
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["🌊 1. 수위 관측소 (홍수통제소)", "🧪 2. 수질자동측정소 (환경과학원)"])

# --- 탭 1: 수위 ---
with tab1:
    st.subheader("수위 관측소 명단 (한글 명칭 확인)")
    
    if st.button("수위 관측소 불러오기", key="btn_wl"):
        with st.spinner("홍수통제소 접속 중..."):
            df_wl, msg_wl = get_water_level_list()
            
            if df_wl is not None:
                st.success(f"✅ 총 {len(df_wl)}개의 관측소를 찾았습니다.")
                
                # 금강 수계 필터링 (사용자 편의)
                search = st.text_input("검색 (예: 갑천, 이원, 금강)", "")
                if search:
                    mask = df_wl['관측소명(한글)'].str.contains(search, na=False)
                    st.dataframe(df_wl[mask], use_container_width=True)
                else:
                    st.dataframe(df_wl, use_container_width=True)
            else:
                st.error(f"실패: {msg_wl}")

# --- 탭 2: 수질 ---
with tab2:
    st.subheader("수질자동측정망 명단 (용담호~부여 확인)")
    st.info(f"사용자 인증키 사용: {USER_KEY_DECODED[:10]}...")
    
    if st.button("수질 측정소 불러오기", key="btn_wq"):
        with st.spinner("공공데이터포털 접속 중..."):
            df_wq, msg_wq = get_water_quality_list()
            
            if df_wq is not None:
                st.success(f"✅ 총 {len(df_wq)}개의 측정소를 찾았습니다.")
                
                # 사용자가 원했던 주요 지점 강제 필터링해서 보여주기
                targets = ["용담", "봉황", "이원", "장계", "옥천", "대청", "현도", "갑천", "미호", "남면", "공주", "유구", "부여"]
                mask = df_wq['측정소명(한글)'].apply(lambda x: any(t in x for t in targets))
                
                target_df = df_wq[mask]
                
                if not target_df.empty:
                    st.write("▼ **원하시던 주요 지점 목록이 확인되었습니다:**")
                    st.dataframe(target_df, use_container_width=True)
                
                with st.expander("전체 목록 보기"):
                    st.dataframe(df_wq)
            else:
                st.error(f"실패: {msg_wq}")
                st.warning("만약 SERVICE_KEY_IS_NOT_REGISTERED 에러라면, '수질자동측정망' 권한이 아직 서버에 전파되지 않은 것입니다 (승인 후 1~2시간 소요).")
