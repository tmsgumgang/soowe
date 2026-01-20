import streamlit as st
import pandas as pd
import requests
import time

# ---------------------------------------------------------
# 1. 설정 및 API 키
# ---------------------------------------------------------
st.set_page_config(page_title="전국 관측소 통합 조회 (한글)", layout="wide")
st.title("📋 전국 수위/수질 관측소 명단 (한글패치 Ver.)")
st.caption("암호 같은 영어 코드를 한글로 싹 바꿔서 보여드립니다.")

# API 키
HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E" # 한강홍수통제소
try:
    DATA_GO_KEY = st.secrets["public_api_key"]
except:
    DATA_GO_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

# [필수] 봇 차단 방지용 신분증 (헤더)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# ---------------------------------------------------------
# 2. 한강홍수통제소 (수위) 리스트 가져오기
# ---------------------------------------------------------
@st.cache_data
def get_hrfco_list_korean():
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list.json"
    
    try:
        response = requests.get(url, headers=HEADERS, verify=False, timeout=15)
        data = response.json()
        
        if 'content' in data:
            df = pd.DataFrame(data['content'])
            
            # 1. 영어 컬럼 -> 한글로 이름표 갈아끼우기
            kor_cols = {
                'wlobscd': '관측소코드',   # 중요!
                'obsnm': '관측소명',       # 중요!
                'agcnm': '관리기관',
                'addr': '주소',
                'etcaddr': '상세주소',
                'lat': '위도',
                'lon': '경도'
            }
            df = df.rename(columns=kor_cols)
            
            # 2. 보기 좋은 순서로 정리 (나머지 컬럼도 뒤에 붙임)
            main_cols = ['관측소명', '관측소코드', '주소', '관리기관']
            # 한글로 바뀐 컬럼 중 실제 존재하는 것만 선택
            final_cols = [c for c in main_cols if c in df.columns] + [c for c in df.columns if c not in main_cols]
            
            return df[final_cols], "성공"
        else:
            return None, "데이터 없음"
    except Exception as e:
        return None, f"에러: {e}"

# ---------------------------------------------------------
# 3. 환경공단 (수질) 리스트 가져오기
# ---------------------------------------------------------
@st.cache_data
def get_nier_list_korean():
    url = "http://apis.data.go.kr/1480523/WaterQualityService/getMsrstnList"
    params = {
        "serviceKey": DATA_GO_KEY,
        "numOfRows": "3000",
        "pageNo": "1",
        "returnType": "json"
    }
    
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=20)
        try:
            data = response.json()
            if 'getMsrstnList' in data and 'item' in data['getMsrstnList']:
                df = pd.DataFrame(data['getMsrstnList']['item'])
                
                # 1. 영어 -> 한글 변환
                kor_cols = {
                    'ptNo': '측정소코드',
                    'ptNm': '측정소명',
                    'addr': '주소',
                    'deptNm': '관리부서',
                    'wmyr': '년도',
                    'wmmd': '월일'
                }
                df = df.rename(columns=kor_cols)
                
                # 2. 컬럼 정리
                main_cols = ['측정소명', '측정소코드', '주소', '관리부서']
                final_cols = [c for c in main_cols if c in df.columns] + [c for c in df.columns if c not in main_cols]
                
                return df[final_cols], "성공"
            return None, "데이터 없음"
        except:
            return None, "응답 형식 오류"
    except Exception as e:
        return None, f"에러: {e}"

# ---------------------------------------------------------
# 4. 메인 화면
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["🌊 수위 관측소 (한강홍수통제소)", "🧪 수질 측정소 (환경공단)"])

# --- 탭 1: 수위 ---
with tab1:
    if st.button("수위 관측소 명단 조회", key="btn_w"):
        with st.spinner("불러오는 중..."):
            df, msg = get_hrfco_list_korean()
            if df is not None:
                st.success(f"✅ 총 {len(df)}개 발견! (영어 컬럼을 한글로 변환했습니다)")
                
                # 검색
                search = st.text_input("검색 (예: 평창, 송정, 1001602)", key="s_w")
                if search:
                    mask = df.astype(str).apply(lambda x: x.str.contains(search, na=False)).any(axis=1)
                    st.dataframe(df[mask], use_container_width=True, hide_index=True)
                else:
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    
                # 엑셀 다운로드
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 엑셀로 저장 (한글)", csv, "수위관측소_한글.csv", "text/csv")
            else:
                st.error(msg)

# --- 탭 2: 수질 ---
with tab2:
    if st.button("수질 측정소 명단 조회", key="btn_q"):
        with st.spinner("불러오는 중..."):
            df_q, msg_q = get_nier_list_korean()
            if df_q is not None:
                st.success(f"✅ 총 {len(df_q)}개 발견!")
                
                search_q = st.text_input("검색 (예: 이원, 대청)", key="s_q")
                if search_q:
                    mask = df_q.astype(str).apply(lambda x: x.str.contains(search_q, na=False)).any(axis=1)
                    st.dataframe(df_q[mask], use_container_width=True, hide_index=True)
                else:
                    st.dataframe(df_q, use_container_width=True, hide_index=True)
                    
                csv_q = df_q.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 엑셀로 저장 (한글)", csv_q, "수질측정소_한글.csv", "text/csv")
            else:
                st.error(msg_q)
