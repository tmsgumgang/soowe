import streamlit as st
import pandas as pd
import requests
import json
import time

# ---------------------------------------------------------
# 1. 설정 및 API 키
# ---------------------------------------------------------
st.set_page_config(page_title="관측소 전체 리스트 조회 (통합)", layout="wide")
st.title("📋 전국 수위/수질 관측소 통합 조회기")

# 한강홍수통제소 키 (수위)
HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"

# 환경공단 키 (수질)
try:
    DATA_GO_KEY = st.secrets["public_api_key"]
except:
    DATA_GO_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

# [중요] 봇 차단 방지용 헤더 (신분증 역할)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# ---------------------------------------------------------
# 2. 기능 1: 수위 관측소 목록 (한강홍수통제소)
# ---------------------------------------------------------
def get_hrfco_list_korean():
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list.json"
    
    try:
        # 헤더를 반드시 포함해서 요청
        response = requests.get(url, headers=HEADERS, verify=False, timeout=15)
        
        if response.status_code != 200:
            return None, f"HTTP 에러: {response.status_code}"
            
        data = response.json()
        if 'content' in data:
            df = pd.DataFrame(data['content'])
            
            # [복구] 한글 컬럼 변환
            rename_map = {
                'wlobscd': '코드',
                'obsnm': '관측소명',
                'agcnm': '관리기관',
                'addr': '주소',
                'etcaddr': '나머지주소'
            }
            # 있는 컬럼만 바꾸기
            df = df.rename(columns=rename_map)
            
            # 필요한 컬럼만 깔끔하게 선택
            cols = ['관측소명', '코드', '주소', '관리기관']
            final_cols = [c for c in cols if c in df.columns]
            
            return df[final_cols], "성공"
        else:
            return None, "데이터 없음"
            
    except Exception as e:
        return None, f"통신 에러: {e}"

# ---------------------------------------------------------
# 3. 기능 2: 수질 측정소 목록 (환경공단)
# ---------------------------------------------------------
def get_nier_list_korean():
    url = "http://apis.data.go.kr/1480523/WaterQualityService/getMsrstnList"
    params = {
        "serviceKey": DATA_GO_KEY,
        "numOfRows": "3000", # 전국 데이터 한 번에 다 가져오기
        "pageNo": "1",
        "returnType": "json"
    }
    
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=20)
        
        # JSON 파싱 시도
        try:
            data = response.json()
            if 'getMsrstnList' in data and 'item' in data['getMsrstnList']:
                items = data['getMsrstnList']['item']
                df = pd.DataFrame(items)
                
                # [복구] 한글 컬럼 변환
                rename_map = {
                    'ptNo': '코드',
                    'ptNm': '측정소명',
                    'addr': '주소',
                    'deptNm': '관리부서'
                }
                df = df.rename(columns=rename_map)
                
                # 필요한 컬럼만 선택
                cols = ['측정소명', '코드', '주소', '관리부서']
                final_cols = [c for c in cols if c in df.columns]
                
                return df[final_cols], "성공"
            else:
                return None, "데이터 구조 다름"
        except:
            return None, f"응답 파싱 실패 (XML 에러 가능성): {response.text[:100]}"
            
    except Exception as e:
        return None, f"통신 에러: {e}"

# ---------------------------------------------------------
# 4. 메인 화면 (탭 구분)
# ---------------------------------------------------------
st.info("💡 팁: '검색' 기능을 이용해 '갑천', '이원' 등의 코드를 쉽게 찾으세요.")

tab1, tab2 = st.tabs(["🌊 수위 관측소 (한강홍수통제소)", "🧪 수질 측정소 (환경공단)"])

# --- 탭 1: 수위 ---
with tab1:
    if st.button("수위 관측소 조회하기", key="btn_wal"):
        with st.spinner("한강홍수통제소 데이터 가져오는 중..."):
            df_wal, msg = get_hrfco_list_korean()
            
            if df_wal is not None:
                st.success(f"✅ 총 {len(df_wal)}개 관측소 로드 완료")
                
                # [복구] 검색 기능
                search_w = st.text_input("수위 관측소 검색 (예: 공주, 갑천)", key="search_w")
                if search_w:
                    # 이름이나 주소에 키워드가 있으면 필터링
                    mask = df_wal['관측소명'].str.contains(search_w) | df_wal['주소'].str.contains(search_w, na=False)
                    df_show = df_wal[mask]
                else:
                    df_show = df_wal
                
                st.dataframe(df_show, use_container_width=True, hide_index=True)
                
                # 다운로드 버튼
                csv = df_show.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 목록 다운로드 (CSV)", csv, "수위관측소_목록.csv", "text/csv")
            else:
                st.error(f"실패: {msg}")

# --- 탭 2: 수질 ---
with tab2:
    if st.button("수질 측정소 조회하기", key="btn_qual"):
        with st.spinner("환경공단 데이터 가져오는 중... (시간이 조금 걸립니다)"):
            df_qual, msg_q = get_nier_list_korean()
            
            if df_qual is not None:
                st.success(f"✅ 총 {len(df_qual)}개 측정소 로드 완료")
                
                # [복구] 검색 기능
                search_q = st.text_input("수질 측정소 검색 (예: 이원, 대청)", key="search_q")
                if search_q:
                    mask = df_qual['측정소명'].str.contains(search_q) | df_qual['주소'].str.contains(search_q, na=False)
                    df_show_q = df_qual[mask]
                else:
                    df_show_q = df_qual
                
                st.dataframe(df_show_q, use_container_width=True, hide_index=True)
                
                # 다운로드 버튼
                csv_q = df_show_q.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 목록 다운로드 (CSV)", csv_q, "수질측정소_목록.csv", "text/csv")
            else:
                st.error(f"실패: {msg_q}")
