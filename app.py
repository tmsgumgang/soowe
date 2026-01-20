import streamlit as st
import pandas as pd
import requests
import json

# ---------------------------------------------------------
# 1. API 키 및 설정
# ---------------------------------------------------------
st.set_page_config(page_title="관측소 전체 리스트 조회", layout="wide")
st.title("📋 API 제공 관측소 전체 리스트 확인")

# 한강홍수통제소 키
HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"

# 환경공단 키 (Secrets 또는 기존 키)
try:
    DATA_GO_KEY = st.secrets["public_api_key"]
except:
    DATA_GO_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

# 봇 차단 방지용 헤더 (필수!)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# ---------------------------------------------------------
# 2. 한강홍수통제소 (수위) 리스트 가져오기
# ---------------------------------------------------------
def get_hrfco_list():
    # 전체 목록 조회 URL
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list.json"
    
    try:
        response = requests.get(url, headers=HEADERS, verify=False, timeout=10)
        
        # 응답 확인
        if response.status_code != 200:
            return None, f"HTTP 에러: {response.status_code}"
            
        data = response.json()
        if 'content' in data:
            df = pd.DataFrame(data['content'])
            # 보기 좋게 컬럼 정리 (관측소명, 코드, 주소)
            if 'obsnm' in df.columns:
                return df[['obsnm', 'wlobscd', 'addr', 'etcaddr']], "성공"
            else:
                return df, "성공(컬럼명 다름)"
        else:
            return None, "데이터 없음 (Content 필드 누락)"
            
    except Exception as e:
        return None, f"통신 에러: {e}"

# ---------------------------------------------------------
# 3. 환경공단 (수질) 리스트 가져오기
# ---------------------------------------------------------
def get_nier_list():
    url = "http://apis.data.go.kr/1480523/WaterQualityService/getMsrstnList"
    params = {
        "serviceKey": DATA_GO_KEY,
        "numOfRows": "2000", # 최대한 많이 가져오기
        "pageNo": "1",
        "returnType": "json"
    }
    
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=10)
        
        # 텍스트로 먼저 받아서 에러인지 확인
        raw_text = response.text.strip()
        
        if response.status_code != 200:
            return None, f"HTTP 에러: {response.status_code}"
            
        try:
            data = json.loads(raw_text)
            if 'getMsrstnList' in data and 'item' in data['getMsrstnList']:
                items = data['getMsrstnList']['item']
                df = pd.DataFrame(items)
                # 보기 좋게 정리 (측정소명, 코드, 주소)
                if 'ptNm' in df.columns:
                    return df[['ptNm', 'ptNo', 'addr']], "성공"
                return df, "성공"
            else:
                return None, "JSON 구조가 예상과 다름"
        except json.JSONDecodeError:
            # JSON이 아니면 XML 에러 메시지일 확률 100%
            return None, f"API 에러 메시지 수신: {raw_text[:200]}"
            
    except Exception as e:
        return None, f"통신 에러: {e}"

# ---------------------------------------------------------
# 4. 화면 출력
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["🌊 한강홍수통제소 (수위)", "🧪 환경공단 (수질)"])

# --- 탭 1: 수위 관측소 ---
with tab1:
    if st.button("수위 관측소 전체 불러오기"):
        with st.spinner("한강홍수통제소 서버에 접속 중..."):
            df_wal, msg_wal = get_hrfco_list()
            
            if df_wal is not None:
                st.success(f"✅ 총 {len(df_wal)}개의 수위 관측소를 가져왔습니다.")
                st.dataframe(df_wal, use_container_width=True)
                
                # 검색 기능
                search = st.text_input("수위 관측소 검색 (예: 갑천, 이원, 공주)", key="search_wal")
                if search:
                    res = df_wal[df_wal['obsnm'].str.contains(search) | df_wal['addr'].str.contains(search, na=False)]
                    st.write(f"🔍 검색 결과 ({len(res)}건)")
                    st.dataframe(res)
            else:
                st.error(f"❌ 목록 조회 실패: {msg_wal}")

# --- 탭 2: 수질 측정소 ---
with tab2:
    if st.button("수질 측정소 전체 불러오기"):
        with st.spinner("환경공단 서버에 접속 중..."):
            df_qual, msg_qual = get_nier_list()
            
            if df_qual is not None:
                st.success(f"✅ 총 {len(df_qual)}개의 수질 측정소를 가져왔습니다.")
                st.dataframe(df_qual, use_container_width=True)
                
                # 검색 기능
                search_q = st.text_input("수질 측정소 검색 (예: 대청, 이원)", key="search_qual")
                if search_q:
                    res_q = df_qual[df_qual['ptNm'].str.contains(search_q) | df_qual['addr'].str.contains(search_q, na=False)]
                    st.write(f"🔍 검색 결과 ({len(res_q)}건)")
                    st.dataframe(res_q)
            else:
                st.error(f"❌ 목록 조회 실패: {msg_qual}")
                st.info("💡 팁: 'API 에러 메시지'가 뜨면, 공공데이터포털에서 '국립환경과학원 수질자동측정망' 활용 신청이 완료되었는지 확인해야 합니다.")
