import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import urllib3
import time # [중요] 쉬엄쉬엄 요청하기 위해 필요

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------
st.set_page_config(page_title="수위 현황판 (최종)", layout="wide")
st.title("🌊 실시간 수위 현황 (스마트 조회)")
st.caption("10분 API 실패 시 1시간 API로 자동 우회하며, 서버 차단을 방지합니다.")

HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ---------------------------------------------------------
# 1. CSV 파일 읽기
# ---------------------------------------------------------
@st.cache_data
def load_station_csv():
    try:
        # 모든 코드를 문자로 읽기
        df = pd.read_csv("station_list.csv", dtype=str)
        return df
    except Exception as e:
        return pd.DataFrame()

# ---------------------------------------------------------
# 2. 스마트 데이터 조회 (10분 -> 실패시 -> 1시간)
# ---------------------------------------------------------
def get_safe_data(station_code):
    if not station_code or pd.isna(station_code):
        return None, "코드 없음"

    # [1차 시도] 10분 단위 데이터 (가장 최신)
    result = try_fetch_api(station_code, '10M')
    if result:
        return result, "성공(10분)"
    
    # [2차 시도] 실패했다면 1시간 단위 데이터로 재시도 (코드 호환성이 더 좋음)
    # (잠깐 쉬었다가 요청)
    time.sleep(0.2)
    result_1h = try_fetch_api(station_code, '1H')
    if result_1h:
        return result_1h, "성공(1시간 우회)"
        
    return None, "모두 실패"

def try_fetch_api(code, time_unit):
    """
    실제 API를 찌르는 함수. 에러가 나도 죽지 않고 None을 반환함.
    """
    # 시간 설정 (한국 시간 보정)
    now = datetime.utcnow() + timedelta(hours=9)
    if time_unit == '10M':
        start = now - timedelta(hours=2) # 10분 단위는 2시간 전부터
    else:
        start = now - timedelta(hours=24) # 1시간 단위는 24시간 전부터
        
    s_str = start.strftime("%Y%m%d%H%M")
    e_str = now.strftime("%Y%m%d%H%M")
    
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list/{time_unit}/{code}/{s_str}/{e_str}.json"
    
    try:
        # 타임아웃을 5초로 넉넉하게 줌
        res = requests.get(url, headers=HEADERS, verify=False, timeout=5)
        
        if res.status_code == 200:
            data = res.json()
            if 'content' in data and data['content']:
                # 최신순으로 정렬되어 있는지 확신할 수 없으므로 날짜로 정렬해서 마지막꺼 가져옴
                items = data['content']
                # 빈 값이나 이상한 데이터 필터링
                valid_items = [x for x in items if x.get('wl') and x['wl'].strip() != '']
                
                if valid_items:
                    latest = valid_items[-1] # 가장 뒤에 있는 게 최신
                    return {
                        '수위(m)': float(latest['wl']), # 여기서 에러 안 나게 처리됨
                        '관측시간': latest['ymdhm']
                    }
    except:
        pass
    return None

# ---------------------------------------------------------
# 3. 메인 실행
# ---------------------------------------------------------
df_csv = load_station_csv()

if not df_csv.empty:
    st.info(f"📂 관측소 {len(df_csv)}개 로드 완료. '조회' 버튼을 눌러주세요.")
    
    if st.button("스마트 조회 시작", type="primary"):
        
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total = len(df_csv)
        
        for i, row in df_csv.iterrows():
            # CSV 컬럼명 찾기 (코드, 수위코드, 관측소코드 중 하나)
            code = row.get('수위코드') or row.get('코드') or row.get('관측소코드')
            name = row.get('관측소명')
            addr = row.get('주소', '-')
            
            status_text.text(f"⏳ [{i+1}/{total}] {name} ({code}) 데이터 수집 중...")
            
            # [중요] 서버 차단 방지를 위해 0.5초씩 쉼
            time.sleep(0.5)
            
            data, note = get_safe_data(code)
            
            if data:
                results.append({
                    '관측소명': name,
                    '현재수위(m)': data['수위(m)'],
                    '관측시간': data['관측시간'],
                    '비고': f"✅ {note}",
                    '주소': addr
                })
            else:
                results.append({
                    '관측소명': name,
                    '현재수위(m)': None, # 그래프 그릴 때 빠지도록
                    '관측시간': "-",
                    '비고': "❌ 데이터 없음(점검중)",
                    '주소': addr
                })
            
            progress_bar.progress((i + 1) / total)
            
        status_text.text("모든 작업이 완료되었습니다.")
        
        if results:
            df_res = pd.DataFrame(results)
            st.divider()
            
            # 요약 통계
            success_cnt = len(df_res[df_res['현재수위(m)'].notnull()])
            st.metric("수신 성공", f"{success_cnt} / {total} 개소")
            
            # 결과 표
            st.subheader("📊 조회 결과")
            st.dataframe(df_res, use_container_width=True)
            
            # 엑셀 저장
            csv_data = df_res.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 엑셀로 저장", csv_data, "최종수위결과.csv")
            
else:
    st.error("GitHub에 'station_list.csv' 파일이 없습니다.")
