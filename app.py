import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import time

# ---------------------------------------------------------
# 설정
# ---------------------------------------------------------
st.set_page_config(page_title="수질자동측정소 조회", layout="wide")
st.title("🧪 금강 수계 수질자동측정소 데이터 조회")
st.caption("제공해주신 API 키로 '용담호, 봉황천' 등의 실시간 수질 데이터를 확인합니다.")

# 제공해주신 키
API_KEY_DECODED = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

# 금강 수계 자동측정소 예상 코드 범위 (S03001 ~ S03030)
# * S03은 금강 권역을 의미할 확률이 높습니다.
CODE_CANDIDATES = [f"S03{i:03d}" for i in range(1, 31)]

# ---------------------------------------------------------
# 데이터 조회 함수
# ---------------------------------------------------------
def fetch_water_quality(pt_no):
    url = "http://apis.data.go.kr/1480523/WaterQualityService/getWaterMeasuringList"
    
    # 최근 데이터를 보기 위해 날짜 설정
    now = datetime.now()
    wmyr = now.strftime("%Y")
    
    params = {
        "serviceKey": API_KEY_DECODED,
        "numOfRows": "10", # 최근 10개
        "pageNo": "1",
        "returnType": "json",
        "ptNo": pt_no,
        "wmyr": wmyr, 
        # wmmd는 생략하면 해당 연도 전체 혹은 최근 데이터를 줄 수 있음
    }
    
    try:
        res = requests.get(url, params=params, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if 'getWaterMeasuringList' in data and 'item' in data['getWaterMeasuringList']:
                items = data['getWaterMeasuringList']['item']
                if items:
                    # 리스트가 아니면 리스트로 변환
                    if isinstance(items, dict): items = [items]
                    return pd.DataFrame(items), "성공"
    except:
        pass
    return None, "데이터 없음"

# ---------------------------------------------------------
# 메인 UI
# ---------------------------------------------------------
st.info("💡 버튼을 누르면 '용담호, 장계, 이원' 등의 코드를 자동으로 찾아냅니다.")

if st.button("🚀 금강 수계 자동측정소 스캔 시작", type="primary"):
    
    found_stations = []
    bar = st.progress(0)
    status_text = st.empty()
    
    # 1. 코드 스캔
    for i, code in enumerate(CODE_CANDIDATES):
        status_text.text(f"스캔 중... {code}")
        
        df, msg = fetch_water_quality(code)
        
        if df is not None and not df.empty:
            # 측정소 이름 확인 (ptNm 필드)
            station_name = df.iloc[0].get('ptNm', '이름미상')
            
            # 우리가 찾는 금강 지점이 맞는지 확인
            target_names = ["용담", "봉황", "이원", "장계", "옥천", "대청", "현도", "갑천", "미호", "남면", "공주", "유구", "부여"]
            is_target = any(t in station_name for t in target_names)
            
            if is_target:
                found_stations.append({
                    "코드": code,
                    "측정소명": station_name,
                    "데이터": df
                })
        
        # 서버 부하 방지
        time.sleep(0.1)
        bar.progress((i + 1) / len(CODE_CANDIDATES))
    
    status_text.text("스캔 완료!")
    
    # 2. 결과 보여주기
    if found_stations:
        st.success(f"🎉 총 {len(found_stations)}개의 측정소를 찾았습니다!")
        
        # 탭 생성
        tabs = st.tabs([s['측정소명'] for s in found_stations])
        
        for i, tab in enumerate(tabs):
            station = found_stations[i]
            df = station['데이터']
            
            with tab:
                st.subheader(f"📍 {station['측정소명']} ({station['코드']})")
                
                # 필요한 항목만 추리기 (대소문자 무관하게 처리)
                cols_map = {
                    'ph': 'pH', 'wtep': '수온(℃)', 'ec': '전기전도도', 
                    'tur': '탁도(NTU)', 'do': 'DO(mg/L)', 'toc': 'TOC(mg/L)', 
                    'tn': 'T-N(mg/L)', 'tp': 'T-P(mg/L)',
                    'wmyr': '년', 'wmmd': '월일', 'wmht': '시간'
                }
                
                # 실제 데이터에 있는 컬럼만 선택
                available_cols = [c for c in df.columns if c.lower() in cols_map]
                df_view = df[available_cols].copy()
                df_view.columns = [cols_map.get(c.lower(), c) for c in df_view.columns]
                
                # 날짜 시간 만들기
                if '년' in df_view.columns and '월일' in df_view.columns:
                    df_view['일시'] = df_view['년'] + "-" + df_view['월일'].str[:2] + "-" + df_view['월일'].str[2:]
                    if '시간' in df_view.columns:
                         df_view['일시'] += " " + df_view['시간'].astype(str).str.zfill(4).str[:2] + ":00"
                    df_view = df_view.sort_values('일시')
                
                # 데이터 표
                st.dataframe(df_view, use_container_width=True)
                
                # 그래프 (항목 선택)
                metrics = [c for c in df_view.columns if c not in ['년', '월일', '시간', '일시', 'ptNo', 'ptNm']]
                if metrics:
                    sel_metric = st.selectbox(f"[{station['측정소명']}] 그래프 항목 선택", metrics, key=f"sel_{i}")
                    st.line_chart(df_view.set_index('일시')[sel_metric])
                else:
                    st.warning("그래프를 그릴 수치 데이터가 없습니다.")

    else:
        st.error("❌ 해당 API 키로 자동측정소 데이터를 찾지 못했습니다.")
        st.warning("""
        **가능한 원인:**
        1. 이 API 키는 '일반측정망(월간 데이터)' 전용일 수 있습니다.
        2. '수질자동측정망' 권한이 아직 승인되지 않았을 수 있습니다.
        """)
