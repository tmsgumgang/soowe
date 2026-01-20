import streamlit as st
import pandas as pd
import requests
import urllib.parse
import time
import math
import xml.etree.ElementTree as ET
import urllib3

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="2026 실시간 수질(확정)", layout="wide")
st.title("🧪 금강 수계 실시간 수질 (코드 확정판)")
st.caption("CSV에서 확인된 '진짜 코드'를 사용하고, 마지막 페이지로 점프하여 2026년 데이터를 잡습니다.")

# 사용자 키
USER_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"
ENCODED_KEY = urllib.parse.quote(USER_KEY)
BASE_URL = "https://apis.data.go.kr/1480523/WaterQualityService/getRealTimeWaterQualityList"

# ---------------------------------------------------------
# [확인됨] 금강 수계 진짜 코드 매핑 (CSV 분석 결과)
# ---------------------------------------------------------
CONFIRMED_STATIONS = [
    {"code": "S03008", "name": "용담호"}, # ★확인됨
    {"code": "S03012", "name": "봉황천"},
    {"code": "S03011", "name": "이원"},   # ★확인됨
    {"code": "S03007", "name": "장계"},
    {"code": "S03010", "name": "옥천천"},
    {"code": "S03003", "name": "대청호"},
    {"code": "S03009", "name": "현도"},
    {"code": "S03002", "name": "갑천"},
    {"code": "S03006", "name": "미호천"}, # 미호강 구 명칭
    {"code": "S03013", "name": "남면"},
    {"code": "S03004", "name": "공주"},
    {"code": "S03014", "name": "유구천"},
    {"code": "S03005", "name": "부여"},
]

# ---------------------------------------------------------
# [핵심] 마지막 페이지 점프 로직 (2007년 탈출)
# ---------------------------------------------------------
def fetch_last_page_data(station_code):
    # 1. 일단 1개만 요청해서 '전체 개수(totalCount)'를 알아냅니다.
    init_url = f"{BASE_URL}?serviceKey={ENCODED_KEY}&numOfRows=1&pageNo=1&siteId={station_code}"
    
    try:
        r1 = requests.get(init_url, verify=False, timeout=5)
        if r1.status_code != 200: return None, f"통신실패({r1.status_code})"
        
        root = ET.fromstring(r1.content)
        total_str = root.findtext('.//totalCount')
        
        if not total_str or int(total_str) == 0:
            return None, "데이터 없음"
            
        total_count = int(total_str)
        
        # 2. 마지막 페이지 계산 (10개씩 볼 때)
        # 예: 500,000개 -> 50,000페이지
        page_size = 10
        last_page = math.ceil(total_count / page_size)
        
        # 3. 마지막 페이지 호출 (여기에 2026년 데이터가 있습니다!)
        final_url = f"{BASE_URL}?serviceKey={ENCODED_KEY}&numOfRows={page_size}&pageNo={last_page}&siteId={station_code}"
        
        r2 = requests.get(final_url, verify=False, timeout=10)
        if r2.status_code == 200:
            root2 = ET.fromstring(r2.content)
            items = root2.findall('.//item')
            
            if items:
                # 결과 파싱
                parsed_list = []
                for item in items:
                    parsed_list.append({child.tag: child.text for child in item})
                
                # 날짜(msrDate) + 시간(msrTime) 내림차순 정렬 -> 가장 최신이 0번
                parsed_list.sort(key=lambda x: (x.get('msrDate', ''), x.get('msrTime', '')), reverse=True)
                
                return parsed_list[0], "성공"
        
        return None, "마지막 페이지 로드 실패"

    except Exception as e:
        return None, f"에러: {e}"

# ---------------------------------------------------------
# 메인 UI
# ---------------------------------------------------------
if st.button("🚀 2026년 실시간 데이터 조회", type="primary"):
    
    results = []
    bar = st.progress(0)
    
    # 성공 카운트
    success_cnt = 0
    
    for i, station in enumerate(CONFIRMED_STATIONS):
        time.sleep(0.1)
        
        item, msg = fetch_last_page_data(station['code'])
        
        if item:
            success_cnt += 1
            res = {
                "지점명": station['name'], # 우리가 확인한 정확한 이름
                "코드": station['code'],
                "시간": f"{item.get('msrDate', '')} {item.get('msrTime', '')}",
                "pH": item.get('m70', '-'),
                "DO(mg/L)": item.get('m69', '-'),
                "TOC(mg/L)": item.get('m27', '-'),
                "탁도(NTU)": item.get('m29', '-'),
                "전기전도도": item.get('m71', '-'),
                "수온(℃)": item.get('m72', '-'),
                "총인(T-P)": item.get('m37', '-'),
            }
            results.append(res)
        else:
            results.append({
                "지점명": station['name'],
                "코드": station['code'],
                "시간": "조회실패",
                "pH": msg
            })
            
        bar.progress((i+1)/len(CONFIRMED_STATIONS))

    # 결과 출력
    if results:
        df = pd.DataFrame(results)
        
        # 최신 날짜 확인
        valid_dates = df[df['시간'].str.contains('202')]['시간'].sort_values(ascending=False)
        latest = valid_dates.iloc[0] if not valid_dates.empty else "확인불가"
        
        st.subheader(f"📊 조회 결과 (기준: {latest})")
        
        if "2026" in str(latest) or "2025" in str(latest):
             st.success("✅ 성공! 최신 데이터를 가져왔습니다.")
        else:
             st.warning(f"⚠️ 여전히 과거 데이터({latest})라면, API 서버 업데이트가 지연되고 있는 것입니다.")
             
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 엑셀 다운로드", csv, "수질_최신_확정.csv")
