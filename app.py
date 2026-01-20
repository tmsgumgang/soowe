import streamlit as st
import pandas as pd
import requests
import time

# ---------------------------------------------------------
# 1. 설정
# ---------------------------------------------------------
st.set_page_config(page_title="관측소 명단 (한글)", layout="wide")
st.title("📋 전국 관측소 '한글 이름표' 조회기")
st.caption("영어 코드(wlobscd)와 약어(wl)를 알기 쉬운 한글로 바꿨습니다.")

# API 키
HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E" # 수위
try:
    DATA_GO_KEY = st.secrets["public_api_key"]
except:
    DATA_GO_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

HEADERS = {'User-Agent': 'Mozilla/5.0'}

# ---------------------------------------------------------
# 2. 수위 관측소 (한강홍수통제소) - 이름표 붙이기
# ---------------------------------------------------------
def get_hrfco_stations():
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list.json"
    
    try:
        response = requests.get(url, headers=HEADERS, verify=False, timeout=10)
        data = response.json()
        
        if 'content' in data:
            df = pd.DataFrame(data['content'])
            
            # [핵심] 영어 컬럼 -> 한글로 강제 변환
            # API가 주는 원래 이름: wlobscd(코드), obsnm(이름), addr(주소)
            df = df.rename(columns={
                'obsnm': '관측소명',      # 여기가 핵심! 이름을 한글 컬럼으로
                'wlobscd': '코드',
                'addr': '주소',
                'agcnm': '관리기관',
                'lat': '위도',
                'lon': '경도'
            })
            
            # 화면에 보여줄 순서 정리 (이름이 제일 먼저 나오게)
            cols = ['관측소명', '코드', '주소', '관리기관']
            # 데이터에 없는 컬럼은 빼고 선택
            final_cols = [c for c in cols if c in df.columns]
            
            return df[final_cols], "성공"
        else:
            return None, "데이터 없음"
    except Exception as e:
        return None, str(e)

# ---------------------------------------------------------
# 3. 수질 측정소 (환경공단) - 이름표 붙이기
# ---------------------------------------------------------
def get_nier_stations():
    url = "http://apis.data.go.kr/1480523/WaterQualityService/getMsrstnList"
    params = {"serviceKey": DATA_GO_KEY, "numOfRows": "3000", "pageNo": "1", "returnType": "json"}
    
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=15)
        
        # JSON 파싱
        try:
            data = response.json()
            items = data['getMsrstnList']['item']
            df = pd.DataFrame(items)
            
            # [핵심] 영어 컬럼 -> 한글로 강제 변환
            # API가 주는 원래 이름: ptNm(이름), ptNo(코드)
            df = df.rename(columns={
                'ptNm': '측정소명',    # 이름
                'ptNo': '코드',       # 코드
                'addr': '주소',
                'deptNm': '관리부서'
            })
            
            cols = ['측정소명', '코드', '주소', '관리부서']
            final_cols = [c for c in cols if c in df.columns]
            
            return df[final_cols], "성공"
        except:
            return None, "응답 형식 에러"
    except Exception as e:
        return None, str(e)

# ---------------------------------------------------------
# 4. 메인 화면
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["🌊 수위 관측소 (이름 확인)", "🧪 수질 측정소 (이름 확인)"])

# 탭 1: 수위
with tab1:
    if st.button("수위 관측소 명단 보기", type="primary"):
        with st.spinner("이름표 붙이는 중..."):
            df, msg = get_hrfco_stations()
            if df is not None:
                st.success(f"✅ {len(df)}개 관측소의 이름을 가져왔습니다.")
                
                # 검색창
                search = st.text_input("이름 검색 (예: 공주, 갑천)", key="s1")
                if search:
                    mask = df['관측소명'].str.contains(search) | df['주소'].str.contains(search, na=False)
                    st.dataframe(df[mask], use_container_width=True, hide_index=True)
                else:
                    st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.error(f"실패: {msg}")

# 탭 2: 수질
with tab2:
    if st.button("수질 측정소 명단 보기", type="primary"):
        with st.spinner("이름표 붙이는 중..."):
            df_q, msg_q = get_nier_stations()
            if df_q is not None:
                st.success(f"✅ {len(df_q)}개 측정소의 이름을 가져왔습니다.")
                
                search_q = st.text_input("이름 검색 (예: 이원, 대청)", key="s2")
                if search_q:
                    mask = df_q['측정소명'].str.contains(search_q) | df_q['주소'].str.contains(search_q, na=False)
                    st.dataframe(df_q[mask], use_container_width=True, hide_index=True)
                else:
                    st.dataframe(df_q, use_container_width=True, hide_index=True)
            else:
                st.error(f"실패: {msg_q}")
