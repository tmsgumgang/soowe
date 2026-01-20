import streamlit as st
import pandas as pd
import requests
import json
import time
import urllib3

# SSL 경고 메시지 숨기기 (깔끔한 로그를 위해)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------
# 1. 설정 및 API 키
# ---------------------------------------------------------
st.set_page_config(page_title="관측소 전체 리스트 조회 (Raw Data)", layout="wide")
st.title("📋 전국 수위/수질 관측소 통합 조회 (원본 보기)")
st.caption("API가 제공하는 모든 컬럼을 필터링 없이 그대로 보여줍니다.")

# 한강홍수통제소 키 (수위)
HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"

# 환경공단 키 (수질)
try:
    DATA_GO_KEY = st.secrets["public_api_key"]
except:
    DATA_GO_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

# [중요] 봇 차단 방지용 헤더
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# ---------------------------------------------------------
# 2. 기능 1: 수위 관측소 목록 (필터링 제거)
# ---------------------------------------------------------
def get_hrfco_list_raw():
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list.json"
    
    try:
        response = requests.get(url, headers=HEADERS, verify=False, timeout=15)
        
        if response.status_code != 200:
            return None, f"HTTP 에러: {response.status_code}"
            
        data = response.json()
        if 'content' in data:
            df = pd.DataFrame(data['content'])
            
            # [수정] 한글 변환을 시도는 하되, 컬럼을 삭제하지는 않음!
            # API 필드명이 바뀔 수 있으므로 원본을 유지합니다.
            rename_map = {
                'wlobscd': '코드(wlobscd)',
                'obsnm': '관측소명(obsnm)',
                'agcnm': '관리기관',
                'addr': '주소',
                'etcaddr': '나머지주소'
            }
            # 에러 방지를 위해 rename 시도
            df = df.rename(columns=rename_map)
            
            # [핵심] 필터링 로직 삭제 -> 모든 컬럼 반환
            return df, "성공"
        else:
            return None, "데이터 없음 (Content 비어있음)"
            
    except Exception as e:
        return None, f"통신 에러: {e}"

# ---------------------------------------------------------
# 3. 기능 2: 수질 측정소 목록 (필터링 제거)
# ---------------------------------------------------------
def get_nier_list_raw():
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
                items = data['getMsrstnList']['item']
                df = pd.DataFrame(items)
                
                # [수정] 한글 변환 시도 (필터링 X)
                rename_map = {
                    'ptNo': '코드(ptNo)',
                    'ptNm': '측정소명(ptNm)',
                    'addr': '주소',
                    'deptNm': '관리부서'
                }
                df = df.rename(columns=rename_map)
                
                # [핵심] 모든 컬럼 반환
                return df, "성공"
            else:
                return None, "데이터 구조 다름"
        except:
            return None, f"응답 파싱 실패: {response.text[:100]}"
            
    except Exception as e:
        return None, f"통신 에러: {e}"

# ---------------------------------------------------------
# 4. 메인 화면
# ---------------------------------------------------------
st.info("📢 이제 데이터가 숨겨지지 않고 **전부** 나옵니다. 표를 옆으로 스크롤해서 '이름'이 있는지 확인해보세요.")

tab1, tab2 = st.tabs(["🌊 수위 관측소 (한강홍수통제소)", "🧪 수질 측정소 (환경공단)"])

# --- 탭 1: 수위 ---
with tab1:
    if st.button("수위 관측소 전체 조회", key="btn_wal"):
        with st.spinner("데이터 가져오는 중..."):
            df_wal, msg = get_hrfco_list_raw()
            
            if df_wal is not None:
                st.success(f"✅ 총 {len(df_wal)}개 관측소 로드 완료")
                
                # 검색 기능 강화 (모든 컬럼에서 검색)
                search_w = st.text_input("검색어 입력 (예: 공주, 갑천)", key="search_w")
                if search_w:
                    # 데이터프레임 전체를 문자열로 바꿔서 검색 (어디에 있든 찾음)
                    mask = df_wal.astype(str).apply(lambda x: x.str.contains(search_w, na=False)).any(axis=1)
                    df_show = df_wal[mask]
                else:
                    df_show = df_wal
                
                st.dataframe(df_show, use_container_width=True)
                
                # 다운로드
                csv = df_show.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 전체 목록 엑셀 다운로드", csv, "수위관측소_전체.csv", "text/csv")
            else:
                st.error(f"실패: {msg}")

# --- 탭 2: 수질 ---
with tab2:
    if st.button("수질 측정소 전체 조회", key="btn_qual"):
        with st.spinner("데이터 가져오는 중..."):
            df_qual, msg_q = get_nier_list_raw()
            
            if df_qual is not None:
                st.success(f"✅ 총 {len(df_qual)}개 측정소 로드 완료")
                
                search_q = st.text_input("검색어 입력 (예: 이원, 대청)", key="search_q")
                if search_q:
                    mask = df_qual.astype(str).apply(lambda x: x.str.contains(search_q, na=False)).any(axis=1)
                    df_show_q = df_qual[mask]
                else:
                    df_show_q = df_qual
                
                st.dataframe(df_show_q, use_container_width=True)
                
                csv_q = df_show_q.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 전체 목록 엑셀 다운로드", csv_q, "수질측정소_전체.csv", "text/csv")
            else:
                st.error(f"실패: {msg_q}")
