import streamlit as st
import pandas as pd
import requests
import time

# ---------------------------------------------------------
# 1. 설정 및 API 키
# ---------------------------------------------------------
st.set_page_config(page_title="관측소 전체 조회 (한글버전)", layout="wide")
st.title("📋 관측소 데이터 조회 (이름 & 한글 컬럼 적용)")

HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"

# 봇 차단 방지 헤더
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# ---------------------------------------------------------
# 2. 핵심 기능: 관측소 '이름표' 만들기
# ---------------------------------------------------------
@st.cache_data
def get_station_map():
    """
    모든 관측소 목록을 가져와서 {코드: 이름} 형태의 사전(Dictionary)을 만듭니다.
    """
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list.json"
    
    try:
        response = requests.get(url, headers=HEADERS, verify=False, timeout=10)
        data = response.json()
        
        if 'content' in data:
            df = pd.DataFrame(data['content'])
            # 코드(wlobscd)와 이름(obsnm)만 추출해서 짝을 지음
            # 예: {'1001602': '소양강댐', ...}
            station_dict = dict(zip(df['wlobscd'], df['obsnm']))
            
            # 추가로 주소 정보도 있으면 좋음
            addr_dict = dict(zip(df['wlobscd'], df['addr']))
            
            return station_dict, addr_dict
        else:
            return {}, {}
            
    except Exception:
        return {}, {}

# ---------------------------------------------------------
# 3. 데이터 가져오기 (이름표 붙이기 포함)
# ---------------------------------------------------------
def get_hrfco_data_korean():
    # 전체 관측소 데이터 조회 (현재 시점)
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list.json"
    
    try:
        # 1. 이름표(Map) 먼저 챙기기
        name_map, addr_map = get_station_map()
        
        # 2. 데이터 가져오기
        response = requests.get(url, headers=HEADERS, verify=False, timeout=10)
        data = response.json()
        
        if 'content' in data:
            df = pd.DataFrame(data['content'])
            
            # 3. 영어 컬럼을 한글로 바꾸기 (직관적으로!)
            # 필요한 컬럼만 선택해서 이름 변경
            df = df.rename(columns={
                'wlobscd': '코드',
                'obsnm': '관측소명',  # API가 이름을 주기도 함
                'ymdhm': '관측일시',
                'wl': '수위(m)',
                'fw': '유량',
                'addr': '주소'
            })
            
            # 만약 API가 '관측소명'을 안 줬다면, 아까 만든 이름표(name_map)로 채워넣기
            if '관측소명' not in df.columns:
                 df['관측소명'] = df['코드'].map(name_map)
            
            # 날짜 보기 좋게 꾸미기 (202601202200 -> 2026-01-20 22:00)
            df['관측일시'] = pd.to_datetime(df['관측일시'], format='%Y%m%d%H%M', errors='coerce')
            
            # 보기 좋은 순서로 컬럼 정렬
            cols = ['관측소명', '수위(m)', '관측일시', '주소', '코드']
            # 실제 데이터에 있는 컬럼만 선택 (에러 방지)
            final_cols = [c for c in cols if c in df.columns]
            
            return df[final_cols]
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"에러 발생: {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# 4. 화면 출력
# ---------------------------------------------------------
st.info("🔄 최신 수위 데이터를 불러오는 중입니다... (이름 자동 변환)")

df_result = get_hrfco_data_korean()

if not df_result.empty:
    st.success(f"✅ 총 {len(df_result)}개 관측소 데이터 확보!")
    
    # 1. 검색창
    keyword = st.text_input("검색 (예: 갑천, 이원, 공주)", "")
    
    if keyword:
        # 이름이나 주소에 키워드가 있는 것만 필터링
        mask = df_result['관측소명'].str.contains(keyword) | df_result['주소'].str.contains(keyword, na=False)
        display_df = df_result[mask]
    else:
        display_df = df_result
    
    # 2. 표 보여주기
    st.dataframe(
        display_df, 
        use_container_width=True,
        hide_index=True  # 0,1,2... 인덱스 숨기기 (깔끔하게)
    )
    
    # 3. 엑셀 다운로드 버튼 (한글 컬럼 적용됨)
    csv = display_df.to_csv(index=False).encode('utf-8-sig') # 한글 깨짐 방지
    st.download_button(
        "📥 엑셀(CSV)로 다운로드",
        csv,
        "수위관측소_한글목록.csv",
        "text/csv",
        key='download-csv'
    )
else:
    st.error("데이터를 가져오지 못했습니다.")
