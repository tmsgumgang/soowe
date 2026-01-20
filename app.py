import streamlit as st
import pandas as pd
import requests
import urllib.parse
import time
import xml.etree.ElementTree as ET
import urllib3
from datetime import datetime

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="2026 실시간 수질", layout="wide")
st.title("🧪 금강 수계 '진짜' 실시간 데이터 (2026년)")
st.caption("연도(2026)를 명시하여 2달 전 데이터가 아닌, '오늘 현재' 데이터를 가져옵니다.")

# 사용자 키
USER_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"
ENCODED_KEY = urllib.parse.quote(USER_KEY)
BASE_URL = "https://apis.data.go.kr/1480523/WaterQualityService/getRealTimeWaterQualityList"

# ---------------------------------------------------------
# [핵심] 2026년 데이터 강제 조회 함수
# ---------------------------------------------------------
def fetch_2026_realtime(station_code):
    # 오늘 날짜 계산 (월, 일)
    now = datetime.now()
    current_year = now.strftime("%Y") # 2026
    current_month = now.strftime("%m") # 01
    
    # [수정] wmyr(연도) 파라미터 추가! 이게 없으면 옛날 것만 줍니다.
    # numOfRows=10: 최신순으로 정렬해서 10개만 가져오기
    params = f"?serviceKey={ENCODED_KEY}&numOfRows=10&pageNo=1&siteId={station_code}&wmyr={current_year}"
    full_url = BASE_URL + params
    
    try:
        r = requests.get(full_url, verify=False, timeout=5)
        
        if r.status_code == 200:
            try:
                root = ET.fromstring(r.content)
                items = root.findall('.//item')
                
                if items:
                    # 날짜/시간 기준으로 내림차순 정렬 (최신 -> 과거)
                    # API가 가끔 정렬 안 된 데이터를 줄 때가 있어 안전장치 추가
                    parsed_items = []
                    for item in items:
                        d = {child.tag: child.text for child in item}
                        parsed_items.append(d)
                    
                    # msrDate(날짜) + msrTime(시간) 기준 정렬
                    parsed_items.sort(key=lambda x: (x.get('msrDate', ''), x.get('msrTime', '')), reverse=True)
                    
                    # 가장 최신 것 리턴
                    return parsed_items[0], "성공"
                else:
                    # 2026년 데이터가 없으면?
                    return None, f"2026년 데이터 없음"
            except Exception as e:
                return None, f"파싱 에러: {e}"
        else:
            return None, f"HTTP {r.status_code}"
            
    except Exception as e:
        return None, f"통신 에러: {e}"

# ---------------------------------------------------------
# 메인 UI
# ---------------------------------------------------------
# 금강 수계 S코드 스캔 (S03001 ~ S03020)
SCAN_CODES = [f"S03{i:03d}" for i in range(1, 21)]

if st.button("🚀 2026년 최신 데이터 조회", type="primary"):
    
    results = []
    bar = st.progress(0)
    status = st.empty()
    
    success_cnt = 0
    
    for i, code in enumerate(SCAN_CODES):
        status.text(f"스캔 중... {code}")
        time.sleep(0.1)
        
        item, msg = fetch_2026_realtime(code)
        
        if item:
            success_cnt += 1
            # 결과 저장
            res = {
                "코드": code,
                "지점명": item.get('siteName', '-'),
                "시간": f"{item.get('msrDate', '')} {item.get('msrTime', '')}",
                "수온(℃)": item.get('m72', '-'),    # 수온
                "pH": item.get('m70', '-'),        # pH
                "DO(mg/L)": item.get('m69', '-'),  # DO
                "탁도(NTU)": item.get('m29', '-'), # 탁도
                "TOC(mg/L)": item.get('m27', '-'), # TOC
                "전기전도도": item.get('m71', '-'), # EC
                "총인(T-P)": item.get('m37', '-'),  # T-P
            }
            results.append(res)
            
        bar.progress((i+1)/len(SCAN_CODES))
        
    status.text("조회 완료")

    if results:
        df = pd.DataFrame(results)
        
        # [중요] 날짜 확인
        dates = df['시간'].sort_values(ascending=False).unique()
        latest_date = dates[0] if len(dates) > 0 else "없음"
        
        st.subheader(f"📊 조회 결과 (최신 기준: {latest_date})")
        
        if "2026" in str(latest_date):
            st.success(f"✅ 드디어 **2026년 데이터**를 잡았습니다!")
        else:
            st.warning(f"⚠️ 아직도 날짜가 {latest_date} 입니다. API 서버에 2026년 데이터가 안 올라온 것일 수 있습니다.")
            
        st.dataframe(df, use_container_width=True)
        
        # 다운로드
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 엑셀 다운로드", csv, "수질_2026_최신.csv")
        
    else:
        st.error("데이터를 하나도 못 가져왔습니다. (2026년 파라미터를 넣었더니 응답이 없음)")
